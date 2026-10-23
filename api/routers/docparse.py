import json
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy import extract as sa_extract
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.quota import check_and_increment, product_quota, schema_slots
from core.database import AsyncSessionLocal, get_db
from core.dependencies import get_current_user_jwt, require_scope
from core.email import send_job_completed
from core.webhooks import WebhookURLError, post_webhook, validate_webhook_url
from models.docparse_job import DocparseJob
from models.docparse_schema import DocParseSchema
from models.user import User
from models.vault import UsageLog

_auth = require_scope("docparse")

router = APIRouter()

PRODUCT = "docparse"

# ── Built-in schema definitions ───────────────────────────────────────────────

_BUILTIN_SCHEMAS: dict[str, list[dict]] = {
    "invoice": [
        {"name": "invoice_number", "description": "Invoice or bill number", "type": "string", "required": True},
        {"name": "invoice_date",   "description": "Date the invoice was issued (ISO 8601)", "type": "date", "required": True},
        {"name": "due_date",       "description": "Payment due date (ISO 8601)", "type": "date"},
        {"name": "vendor_name",    "description": "Name of the vendor or seller", "type": "string", "required": True},
        {"name": "vendor_address", "description": "Vendor's full mailing address", "type": "string"},
        {"name": "buyer_name",     "description": "Name of the buyer or bill-to party", "type": "string"},
        {"name": "total_amount",   "description": "Total amount due (numeric, no currency symbol)", "type": "number", "required": True},
        {"name": "currency",       "description": "Three-letter currency code (e.g. USD, EUR)", "type": "string"},
        {"name": "line_items",     "description": "List of line items as strings", "type": "list"},
    ],
    "loan_application": [
        {"name": "applicant_name",   "description": "Full legal name of the applicant", "type": "string", "required": True},
        {"name": "loan_amount",      "description": "Requested loan amount (numeric)", "type": "number", "required": True},
        {"name": "loan_purpose",     "description": "Purpose of the loan", "type": "string"},
        {"name": "annual_income",    "description": "Applicant's annual income (numeric)", "type": "number"},
        {"name": "employment_status","description": "Employment status (employed / self-employed / unemployed)", "type": "string"},
        {"name": "credit_score",     "description": "Applicant's credit score (numeric)", "type": "number"},
        {"name": "collateral",       "description": "Description of any collateral offered", "type": "string"},
    ],
    "w2": [
        {"name": "employee_name",   "description": "Employee's full name", "type": "string", "required": True},
        {"name": "employer_name",   "description": "Employer's name", "type": "string", "required": True},
        {"name": "tax_year",        "description": "Tax year (4-digit)", "type": "string", "required": True},
        {"name": "wages",           "description": "Box 1: Wages, tips, other compensation (numeric)", "type": "number"},
        {"name": "federal_tax",     "description": "Box 2: Federal income tax withheld (numeric)", "type": "number"},
        {"name": "social_security_wages", "description": "Box 3: Social security wages (numeric)", "type": "number"},
        {"name": "ssn_last4",       "description": "Last 4 digits of employee SSN", "type": "string"},
    ],
    "nda": [
        {"name": "party_a",         "description": "Name of the first party (disclosing party)", "type": "string", "required": True},
        {"name": "party_b",         "description": "Name of the second party (receiving party)", "type": "string", "required": True},
        {"name": "effective_date",  "description": "Date the NDA becomes effective (ISO 8601)", "type": "date"},
        {"name": "duration_years",  "description": "Duration of confidentiality obligation in years (numeric)", "type": "number"},
        {"name": "governing_law",   "description": "Jurisdiction / governing law", "type": "string"},
        {"name": "scope",           "description": "Brief description of what information is covered", "type": "string"},
    ],
    "contract": [
        {"name": "parties",         "description": "List of all contracting parties", "type": "list", "required": True},
        {"name": "effective_date",  "description": "Contract start date (ISO 8601)", "type": "date"},
        {"name": "expiration_date", "description": "Contract end date (ISO 8601)", "type": "date"},
        {"name": "contract_value",  "description": "Total contract value (numeric)", "type": "number"},
        {"name": "governing_law",   "description": "Governing jurisdiction or law", "type": "string"},
        {"name": "renewal_terms",   "description": "Auto-renewal or renewal conditions", "type": "string"},
        {"name": "termination_notice", "description": "Required notice period for termination", "type": "string"},
    ],
}

_SCHEMA_NAMES = Literal["invoice", "loan_application", "w2", "nda", "contract"]


# ── LLM extraction ────────────────────────────────────────────────────────────

def _build_prompt(text: str, fields: list[dict]) -> str:
    field_lines = "\n".join(
        f"- {f['name']}: {f.get('description', f['name'])}"
        + (f" (return as {f['type']})" if f.get("type") and f["type"] not in ("string", "str") else "")
        for f in fields
    )
    return (
        "You are a precise document extraction specialist.\n"
        "Extract the following fields from the document below.\n"
        "Return a JSON object where each key is a field name and the value is the extracted text "
        "exactly as it appears in the document. Use null for any field not found.\n\n"
        f"Fields:\n{field_lines}\n\n"
        f"Document:\n{text[:12000]}"
    )


async def _llm_extract(text: str, fields: list[dict]) -> dict[str, dict[str, Any]]:
    from core.llm import llm_json_complete
    try:
        prompt = _build_prompt(text, fields)
        return await llm_json_complete(prompt, max_tokens=2048, timeout=30.0, product="docparse")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM extraction failed: {exc}") from exc


async def _ocr_image(image_base64: str, media_type: str) -> str:
    """OCR a document image via GPT-4o-mini vision, returns extracted text."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OpenAI API key not configured.")
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{image_base64}"},
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Extract all text from this document image. "
                                    "Preserve layout, numbers, and structure faithfully. "
                                    "Output only the extracted text, nothing else."
                                ),
                            },
                        ],
                    }],
                    "max_tokens": 4096,
                },
            )
        if resp.status_code != 200:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"OCR request failed ({resp.status_code}).")
        body = resp.json()
        return body["choices"][0]["message"]["content"] or ""
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"OCR failed: {exc}") from exc


async def _ocr_llamaparse(image_base64: str, media_type: str) -> str:
    """OCR a document image via LlamaParse, returns extracted text."""
    import asyncio
    import base64 as _b64

    api_key = settings.LLAMA_PARSE_API_KEY
    if not api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "LlamaParse API key not configured.")

    ext = "jpg" if "jpeg" in media_type else media_type.split("/")[-1]
    image_bytes = _b64.b64decode(image_base64)

    async with httpx.AsyncClient(timeout=90.0) as client:
        # Upload job
        upload_resp = await client.post(
            "https://api.cloud.llamaindex.ai/api/parsing/upload",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (f"document.{ext}", image_bytes, media_type)},
            data={"language": "en"},
        )
        if upload_resp.status_code not in (200, 201):
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"LlamaParse upload failed ({upload_resp.status_code}): {upload_resp.text[:200]}",
            )
        job_id = upload_resp.json().get("id") or upload_resp.json().get("job_id")
        if not job_id:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LlamaParse: no job_id in upload response.")

        # Poll for completion (max 45s, 3s intervals)
        for _ in range(15):
            await asyncio.sleep(3.0)
            status_resp = await client.get(
                f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if status_resp.status_code != 200:
                continue
            job_status = status_resp.json().get("status", "")
            if job_status == "SUCCESS":
                result_resp = await client.get(
                    f"https://api.cloud.llamaindex.ai/api/parsing/job/{job_id}/result/text",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if result_resp.status_code == 200:
                    return result_resp.json().get("text", "") or result_resp.json().get("markdown", "")
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LlamaParse: result retrieval failed.")
            if job_status in ("ERROR", "FAILED"):
                raise HTTPException(status.HTTP_502_BAD_GATEWAY, "LlamaParse: job failed.")

    raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "LlamaParse: OCR timed out after 45s.")


# ── Schemas ───────────────────────────────────────────────────────────────────

class FieldSpec(BaseModel):
    name: str
    description: str
    type: str = "string"
    required: bool = False


class ExtractRequest(BaseModel):
    text: str | None = None
    image_base64: str | None = None
    image_media_type: str = "image/jpeg"
    ocr_provider: Literal["openai", "llamaparse"] = "openai"
    schema_name: str | None = None
    fields: list[FieldSpec] | None = None


class FieldValue(BaseModel):
    value: Any
    confidence: float


class ExtractResponse(BaseModel):
    schema_name: str
    fields: dict[str, FieldValue]


class StatsResponse(BaseModel):
    monthly_usage: int
    monthly_period: str
    quota: int


class JobRequest(BaseModel):
    text: str
    schema_name: str | None = None
    fields: list[FieldSpec] | None = None
    webhook_url: str | None = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    schema_name: str
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None


# ── Quota helper ──────────────────────────────────────────────────────────────

async def _check_and_increment_quota(user: User, db: AsyncSession) -> None:
    await check_and_increment(user, 1, db, product=PRODUCT)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/extract", response_model=ExtractResponse)
async def extract(
    body: ExtractRequest,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    if not body.text and not body.image_base64:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide either text or image_base64.")

    # OCR image to text when image is provided
    text = body.text or ""
    if body.image_base64:
        if body.ocr_provider == "llamaparse":
            text = await _ocr_llamaparse(body.image_base64, body.image_media_type)
        else:
            text = await _ocr_image(body.image_base64, body.image_media_type)

    if not text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "text must not be empty")

    if body.schema_name:
        if body.schema_name not in _BUILTIN_SCHEMAS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Unknown schema '{body.schema_name}'. Available: {list(_BUILTIN_SCHEMAS)}",
            )
        fields = _BUILTIN_SCHEMAS[body.schema_name]
        schema_label = body.schema_name
    elif body.fields:
        fields = [f.model_dump() for f in body.fields]
        schema_label = "custom"
    else:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Provide either schema_name or fields.",
        )

    await _check_and_increment_quota(user, db)

    raw = await _llm_extract(text, fields)

    # Normalise — ensure every field in schema is present
    result_fields: dict[str, FieldValue] = {}
    for f in fields:
        name = f["name"]
        entry = raw.get(name)
        if isinstance(entry, dict) and "value" in entry:
            # Legacy nested format: {"value": ..., "confidence": ...}
            result_fields[name] = FieldValue(
                value=entry.get("value"),
                confidence=min(1.0, max(0.0, float(entry.get("confidence", 0.9)))),
            )
        else:
            # Flat value — derive confidence from presence
            result_fields[name] = FieldValue(value=entry, confidence=0.0 if entry is None else 0.9)

    db.add(UsageLog(user_id=user.id, product=PRODUCT, operation="extract", units=1))
    await db.commit()

    return ExtractResponse(schema_name=schema_label, fields=result_fields)


# ── Background task ───────────────────────────────────────────────────────────

async def _process_job(job_id: _uuid.UUID, fields: list[dict], schema_label: str) -> None:
    from models.user import User as _User
    async with AsyncSessionLocal() as db:
        row = await db.execute(select(DocparseJob).where(DocparseJob.id == job_id))
        job = row.scalar_one_or_none()
        if not job:
            return
        user_row = await db.execute(select(_User).where(_User.id == job.user_id))
        user_email = getattr(user_row.scalar_one_or_none(), "email", None)

        job.status = "processing"
        await db.commit()

        try:
            raw = await _llm_extract(job.text, fields)

            result_fields: dict[str, Any] = {}
            for f in fields:
                name = f["name"]
                entry = raw.get(name)
                if isinstance(entry, dict) and "value" in entry:
                    result_fields[name] = {
                        "value": entry.get("value"),
                        "confidence": min(1.0, max(0.0, float(entry.get("confidence", 0.9)))),
                    }
                else:
                    result_fields[name] = {"value": entry, "confidence": 0.0 if entry is None else 0.9}

            job.status = "completed"
            job.result_json = json.dumps(result_fields)
            job.completed_at = datetime.now(timezone.utc)

            db.add(UsageLog(user_id=job.user_id, product=PRODUCT, operation="extract_async", units=1))
            await db.commit()

            if job.webhook_url:
                payload = {
                    "job_id": str(job.id),
                    "status": "completed",
                    "schema_name": schema_label,
                    "fields": result_fields,
                    "completed_at": job.completed_at.isoformat(),
                }
                await post_webhook(job.webhook_url, payload)

            if user_email:
                import asyncio
                asyncio.create_task(send_job_completed(user_email, str(job.id), schema_label, "completed"))

        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            if job.webhook_url:
                await post_webhook(job.webhook_url, {
                    "job_id": str(job.id),
                    "status": "failed",
                    "error": str(exc),
                })

            if user_email:
                import asyncio
                asyncio.create_task(send_job_completed(user_email, str(job.id), schema_label, "failed"))


def _job_response(job: DocparseJob) -> JobResponse:
    result = None
    if job.result_json:
        try:
            result = json.loads(job.result_json)
        except Exception:
            pass
    return JobResponse(
        job_id=str(job.id),
        status=job.status,
        schema_name=job.schema_name or "custom",
        result=result,
        error=job.error,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


# ── Async job endpoints ───────────────────────────────────────────────────────

@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    body: JobRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    if body.webhook_url:
        try:
            await validate_webhook_url(body.webhook_url)
        except (WebhookURLError, OSError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid webhook_url: {exc}")
    if not body.text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "text must not be empty")

    if body.schema_name:
        if body.schema_name not in _BUILTIN_SCHEMAS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Unknown schema '{body.schema_name}'. Available: {list(_BUILTIN_SCHEMAS)}",
            )
        fields = _BUILTIN_SCHEMAS[body.schema_name]
        schema_label = body.schema_name
    elif body.fields:
        fields = [f.model_dump() for f in body.fields]
        schema_label = "custom"
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide either schema_name or fields.")

    await _check_and_increment_quota(user, db)

    job = DocparseJob(
        user_id=user.id,
        status="pending",
        schema_name=schema_label,
        fields_json=json.dumps(fields) if body.fields else None,
        text=body.text,
        webhook_url=body.webhook_url,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(_process_job, job.id, fields, schema_label)

    return _job_response(job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    try:
        jid = _uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    row = await db.execute(
        select(DocparseJob).where(and_(DocparseJob.id == jid, DocparseJob.user_id == user.id))
    )
    job = row.scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found.")
    return _job_response(job)


@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(DocparseJob)
        .where(DocparseJob.user_id == user.id)
        .order_by(DocparseJob.created_at.desc())
        .limit(20)
    )
    return [_job_response(j) for j in rows.scalars()]


@router.get("/me/stats", response_model=StatsResponse)
async def me_stats(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """JWT-authenticated stats — used by the dashboard."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(func.coalesce(func.sum(UsageLog.units), 0)).where(
            and_(
                UsageLog.user_id == user.id,
                UsageLog.product == PRODUCT,
                sa_extract("year", UsageLog.created_at) == now.year,
                sa_extract("month", UsageLog.created_at) == now.month,
            )
        )
    )
    return StatsResponse(
        monthly_usage=int(result.scalar() or 0),
        monthly_period=now.strftime("%Y-%m"),
        quota=product_quota("docparse", user),
    )


@router.get("/stats", response_model=StatsResponse)
async def stats(
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(func.coalesce(func.sum(UsageLog.units), 0)).where(
            and_(
                UsageLog.user_id == user.id,
                UsageLog.product == PRODUCT,
                sa_extract("year", UsageLog.created_at) == now.year,
                sa_extract("month", UsageLog.created_at) == now.month,
            )
        )
    )
    monthly = int(result.scalar() or 0)
    return StatsResponse(
        monthly_usage=monthly,
        monthly_period=now.strftime("%Y-%m"),
        quota=product_quota("docparse", user),
    )


# ── Custom schemas ─────────────────────────────────────────────────────────────

class SchemaFieldSpec(BaseModel):
    name: str
    description: str
    type: str = "string"
    required: bool = False


class SchemaCreate(BaseModel):
    name: str
    description: str | None = None
    fields: list[SchemaFieldSpec]


class SchemaResponse(BaseModel):
    id: str
    name: str
    description: str | None
    fields: list[dict]
    created_at: str
    updated_at: str


def _schema_to_response(s: DocParseSchema) -> SchemaResponse:
    return SchemaResponse(
        id=str(s.id),
        name=s.name,
        description=s.description,
        fields=json.loads(s.fields_json),
        created_at=s.created_at.isoformat(),
        updated_at=s.updated_at.isoformat(),
    )


@router.get("/schemas", response_model=list[SchemaResponse])
async def list_schemas(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """List user's custom extraction schemas."""
    rows = await db.execute(
        select(DocParseSchema)
        .where(DocParseSchema.user_id == user.id)
        .order_by(DocParseSchema.created_at.desc())
    )
    return [_schema_to_response(s) for s in rows.scalars()]


@router.post("/schemas", response_model=SchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_schema(
    body: SchemaCreate,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """Create a named extraction schema (limited number of slots per account)."""
    slot_limit = schema_slots(user)
    count_result = await db.execute(
        select(func.count(DocParseSchema.id)).where(DocParseSchema.user_id == user.id)
    )
    count = int(count_result.scalar() or 0)
    if count >= slot_limit:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Schema slot limit reached ({slot_limit}). To request more slots, contact {settings.CONTACT_EMAIL}.",
        )

    schema = DocParseSchema(
        user_id=user.id,
        org_id=user.org_id,
        name=body.name.strip(),
        description=body.description,
        fields_json=json.dumps([f.model_dump() for f in body.fields]),
    )
    db.add(schema)
    await db.commit()
    return _schema_to_response(schema)


@router.get("/schemas/{schema_id}", response_model=SchemaResponse)
async def get_schema(
    schema_id: str,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    try:
        sid = _uuid.UUID(schema_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found.")
    row = await db.execute(
        select(DocParseSchema).where(DocParseSchema.id == sid, DocParseSchema.user_id == user.id)
    )
    schema = row.scalar_one_or_none()
    if not schema:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found.")
    return _schema_to_response(schema)


@router.patch("/schemas/{schema_id}", response_model=SchemaResponse)
async def update_schema(
    schema_id: str,
    body: SchemaCreate,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    try:
        sid = _uuid.UUID(schema_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found.")
    row = await db.execute(
        select(DocParseSchema).where(DocParseSchema.id == sid, DocParseSchema.user_id == user.id)
    )
    schema = row.scalar_one_or_none()
    if not schema:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found.")
    schema.name = body.name.strip()
    schema.description = body.description
    schema.fields_json = json.dumps([f.model_dump() for f in body.fields])
    await db.commit()
    return _schema_to_response(schema)


@router.delete("/schemas/{schema_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schema(
    schema_id: str,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    try:
        sid = _uuid.UUID(schema_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found.")
    row = await db.execute(
        select(DocParseSchema).where(DocParseSchema.id == sid, DocParseSchema.user_id == user.id)
    )
    schema = row.scalar_one_or_none()
    if not schema:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schema not found.")
    await db.delete(schema)
    await db.commit()


@router.get("/schemas-info")
async def schemas_info(user: User = Depends(get_current_user_jwt), db: AsyncSession = Depends(get_db)):
    """Return schema slot usage for the current user."""
    count_result = await db.execute(
        select(func.count(DocParseSchema.id)).where(DocParseSchema.user_id == user.id)
    )
    used = int(count_result.scalar() or 0)
    return {"used": used, "limit": schema_slots(user)}
