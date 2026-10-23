import re
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user_jwt, require_scope
_auth = require_scope("pii-vault")
from core.fpe import generate_fpe
from core.quota import check_and_increment, product_quota
from core.security import decrypt_vault_key, decrypt_value, encrypt_value
from models.user import User
from models.vault import UsageLog, VaultEntry

router = APIRouter()

PRODUCT = "pii_vault"


# ── Schemas ───────────────────────────────────────────────────────────────────

class TokenEntry(BaseModel):
    token: str
    value: str
    entity_type: str
    subject_id: str | None = None


class StoreRequest(BaseModel):
    entries: list[TokenEntry] = Field(max_length=10_000)


class StoreResponse(BaseModel):
    stored: int


class LookupRequest(BaseModel):
    tokens: list[str] = Field(max_length=10_000)


class LookupResponse(BaseModel):
    values: dict[str, str | None]


class SubjectTokenItem(BaseModel):
    token: str
    entity_type: str
    created_at: str


class SubjectResponse(BaseModel):
    subject_id: str
    tokens: list[SubjectTokenItem]


class DeleteSubjectResponse(BaseModel):
    deleted_count: int


class StatsResponse(BaseModel):
    total_entries: int
    monthly_usage: int
    monthly_period: str | None
    quota: int


class ScanRequest(BaseModel):
    text: str = Field(max_length=100_000)
    entities: list[str] | None = Field(default=None, max_length=20)
    use_llm: bool = False


class EntitySummaryItem(BaseModel):
    entity_type: str
    count: int


class ScanResponse(BaseModel):
    safe_text: str
    pii_detected: bool
    redacted_count: int
    entity_summary: list[EntitySummaryItem]


class TokenizeRequest(BaseModel):
    text: str = Field(max_length=100_000)
    entities: list[str] | None = Field(default=None, max_length=20)
    format_preserving: bool = True
    subject_id: str | None = Field(default=None, max_length=255)
    use_llm: bool = False  # enable LLM fallback for entity types with 0 regex matches


class TokenizeEntity(BaseModel):
    original: str
    replacement: str
    entity_type: str
    start: int
    end: int


class TokenizeResponse(BaseModel):
    text: str                          # de-identified text
    entities: list[TokenizeEntity]
    stored: int


class DetokenizeRequest(BaseModel):
    text: str = Field(max_length=100_000)


class DetokenizeResponse(BaseModel):
    text: str


# ── Quota helper ──────────────────────────────────────────────────────────────

def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def _check_and_increment_quota(user: User, units: int, db: AsyncSession) -> None:
    await check_and_increment(user, units, db, product=PRODUCT)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/tokens", response_model=StoreResponse)
async def store_tokens(
    body: StoreRequest,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """Store token↔value mappings in the hosted vault. Called by HostedVault.flush()."""
    if not body.entries:
        return StoreResponse(stored=0)

    await _check_and_increment_quota(user, len(body.entries), db)

    user_fernet_key = decrypt_vault_key(user.vault_encryption_key)
    stored = 0

    for entry in body.entries:
        encrypted = encrypt_value(entry.value, user_fernet_key)
        result = await db.execute(
            select(VaultEntry).where(
                VaultEntry.user_id == user.id,
                VaultEntry.token == entry.token,
            )
        )
        existing = result.scalar_one_or_none()
        if not existing:
            db.add(VaultEntry(
                user_id=user.id,
                token=entry.token,
                encrypted_value=encrypted,
                entity_type=entry.entity_type,
                subject_id=entry.subject_id,
            ))
            stored += 1

    db.add(UsageLog(
        user_id=user.id,
        product=PRODUCT,
        operation="store",
        units=len(body.entries),
    ))
    await db.commit()
    return StoreResponse(stored=stored)


@router.post("/tokens/lookup", response_model=LookupResponse)
async def lookup_tokens(
    body: LookupRequest,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve original values for a list of tokens. Called by HostedVault.batch_retrieve()."""
    if not body.tokens:
        return LookupResponse(values={})

    result = await db.execute(
        select(VaultEntry).where(
            VaultEntry.user_id == user.id,
            VaultEntry.token.in_(body.tokens),
        )
    )
    entries = result.scalars().all()
    user_fernet_key = decrypt_vault_key(user.vault_encryption_key)

    values: dict[str, str | None] = {t: None for t in body.tokens}
    for entry in entries:
        try:
            values[entry.token] = decrypt_value(entry.encrypted_value, user_fernet_key)
        except Exception:
            values[entry.token] = None

    db.add(UsageLog(
        user_id=user.id,
        product=PRODUCT,
        operation="dehydrate",
        units=len(body.tokens),
    ))
    await db.commit()
    return LookupResponse(values=values)


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def list_subject(
    subject_id: str,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VaultEntry).where(
            VaultEntry.user_id == user.id,
            VaultEntry.subject_id == subject_id,
        )
    )
    entries = result.scalars().all()
    return SubjectResponse(
        subject_id=subject_id,
        tokens=[
            SubjectTokenItem(
                token=e.token,
                entity_type=e.entity_type,
                created_at=e.created_at.isoformat(),
            )
            for e in entries
        ],
    )


@router.delete("/subjects/{subject_id}", response_model=DeleteSubjectResponse)
async def delete_subject(
    subject_id: str,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """DSAR deletion — remove all vault entries linked to a data subject."""
    result = await db.execute(
        delete(VaultEntry).where(
            VaultEntry.user_id == user.id,
            VaultEntry.subject_id == subject_id,
        ).returning(VaultEntry.id)
    )
    deleted_count = len(result.fetchall())
    await db.commit()
    return DeleteSubjectResponse(deleted_count=deleted_count)


# ── FPE entity detection patterns ─────────────────────────────────────────────

_ENTITY_PATTERNS: list[tuple[str, str]] = [
    ("EMAIL",       r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
    ("SSN",         r"\b\d{3}-\d{2}-\d{4}\b"),
    # IP_ADDRESS before PHONE to prevent dot-separated IPs matching phone patterns
    ("IP_ADDRESS",  r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"),
    # Credit card: Visa/MC/Amex/Discover/JCB — digits optionally separated by spaces or hyphens
    ("CREDIT_CARD", (
        r"\b(?:"
        r"4[0-9]{3}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{1,4}"   # Visa 13-16
        r"|5[1-5][0-9]{2}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}" # MC 5[1-5]
        r"|2(?:2[2-9][1-9]|[3-6]\d{2}|7(?:[01]\d|20))[0-9]{12}"         # MC 2221-2720
        r"|3[47][0-9]{2}[\s\-]?[0-9]{6}[\s\-]?[0-9]{5}"                 # Amex
        r"|6(?:011|5[0-9]{2})[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}" # Discover
        r"|622(?:1(?:2[6-9]|[3-9]\d)|[2-8]\d{2}|9(?:[01]\d|2[0-5]))[0-9]{12}" # UnionPay 622
        r"|35(?:2[89]|[3-8]\d)[0-9]{12}"                                 # JCB
        r")\b"
    )),
    # Phone: US/Canada, international with +CC, European spaced, and dot/space grouped formats
    ("PHONE", (
        r"(?:"
        r"\+?1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"               # US/Canada +1 or bare
        r"|\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}"                            # bare US (xxx) xxx-xxxx
        r"|\+[1-9]\d{0,2}[-.\s]?\d{1,4}(?:[-.\s]\d{1,4}){2,5}"          # international +CC
        r"|\b\d{4}[.\s]\d{3}[.\s]\d{3}[.\s]\d{4}\b"                      # 4.3.3.4 synthetic
        r"|\b\d{3}[.\s]\d{3}[.\s]\d{4}\b"                                # 3.3.4 (no country)
        r"|\b\d{2}[.\s]\d{2}[.\s]\d{2}[.\s]\d{2}[.\s]\d{2}\b"           # FR: 01.23.45.67.89
        r")"
    )),
]

_ALL_ENTITY_TYPES = {e for e, _ in _ENTITY_PATTERNS}


def _luhn_valid(digits: str) -> bool:
    """Luhn algorithm — validates a digit-only string as a plausible card number."""
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _detect_entities(text: str, entities: list[str] | None) -> list[tuple[str, str, int, int]]:
    """Return list of (entity_type, original, start, end) sorted by start position."""
    active = entities or list(_ALL_ENTITY_TYPES)
    found: list[tuple[str, str, int, int]] = []
    covered: set[int] = set()

    for entity_type, pattern in _ENTITY_PATTERNS:
        if entity_type not in active:
            continue
        for m in re.finditer(pattern, text):
            span = set(range(m.start(), m.end()))
            if span & covered:
                continue
            # Luhn validation for credit cards — reject implausible matches
            if entity_type == "CREDIT_CARD":
                digits = re.sub(r"\D", "", m.group())
                if not _luhn_valid(digits):
                    continue
            covered |= span
            found.append((entity_type, m.group(), m.start(), m.end()))

    found.sort(key=lambda x: x[2])
    return found


async def _llm_detect_missing(
    text: str, missing_types: list[str]
) -> list[tuple[str, str, int, int]]:
    """LLM fallback: find entity types that regex missed. Returns (type, value, start, end)."""
    from core.llm import llm_json_complete

    _type_desc = {
        "PHONE": "phone numbers in any format (including non-standard or dot-separated)",
        "CREDIT_CARD": "credit card numbers",
        "SSN": "social security numbers in any format",
        "EMAIL": "email addresses",
        "IP_ADDRESS": "IP addresses",
    }
    descriptions = "; ".join(f"{t}: {_type_desc.get(t, t)}" for t in missing_types)

    prompt = (
        f"Extract all instances of the following sensitive information types from the text below.\n"
        f"Types: {descriptions}\n"
        f"Text: {text[:3000]}\n\n"
        f'Return JSON only: {{"entities": [{{"type": "PHONE|CREDIT_CARD|SSN|EMAIL|IP_ADDRESS", "value": "exact text"}}]}}\n'
        f"Only return entities of the requested types. Preserve the exact characters from the text."
    )
    try:
        result = await llm_json_complete(prompt, max_tokens=500, timeout=20.0, product="pii_vault")
        entities = result.get("entities", [])
        found: list[tuple[str, str, int, int]] = []
        for ent in entities:
            etype = str(ent.get("type", "")).upper()
            value = str(ent.get("value", ""))
            if etype not in missing_types or not value:
                continue
            start = text.find(value)
            if start >= 0:
                found.append((etype, value, start, start + len(value)))
        return found
    except Exception:
        return []


# ── Scan (detect + redact, no vault storage) ─────────────────────────────────

@router.post("/scan", response_model=ScanResponse)
async def scan(
    body: ScanRequest,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Detect PII in text and return a redacted version.

    Unlike /tokenize, no vault storage and no reversibility — PII is replaced with
    [REDACTED_<TYPE>] placeholders. Designed for sanitizing text before LLM inference.
    Costs 1 quota unit per call regardless of entity count.
    """
    if not body.text.strip():
        return ScanResponse(safe_text=body.text, pii_detected=False, redacted_count=0, entity_summary=[])

    detected = _detect_entities(body.text, body.entities)

    if body.use_llm:
        found_types = {d[0] for d in detected}
        active_types = set(body.entities or _ALL_ENTITY_TYPES)
        missing_types = list(active_types - found_types)
        if missing_types:
            llm_found = await _llm_detect_missing(body.text, missing_types)
            covered: set[int] = set()
            for d in detected:
                covered |= set(range(d[2], d[3]))
            for ent in llm_found:
                span = set(range(ent[2], ent[3]))
                if not (span & covered):
                    detected.append(ent)
                    covered |= span
            detected.sort(key=lambda x: x[2])

    if not detected:
        return ScanResponse(safe_text=body.text, pii_detected=False, redacted_count=0, entity_summary=[])

    await _check_and_increment_quota(user, 1, db)

    # Tally by type
    counts: dict[str, int] = {}
    for entity_type, _, _, _ in detected:
        counts[entity_type] = counts.get(entity_type, 0) + 1

    # Replace from right to left so earlier offsets stay valid
    chars = list(body.text)
    replaced_originals: set[str] = set()
    for entity_type, original, start, end in reversed(detected):
        chars[start:end] = list(f"[REDACTED_{entity_type}]")
        replaced_originals.add(original)

    db.add(UsageLog(user_id=user.id, product=PRODUCT, operation="scan", units=1))
    await db.commit()

    return ScanResponse(
        safe_text="".join(chars),
        pii_detected=True,
        redacted_count=len(replaced_originals),
        entity_summary=[EntitySummaryItem(entity_type=et, count=c) for et, c in counts.items()],
    )


# ── Hosted tokenize / detokenize ──────────────────────────────────────────────

@router.post("/tokenize", response_model=TokenizeResponse)
async def tokenize(
    body: TokenizeRequest,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Detect PII in *text*, replace with format-preserving fakes, store mappings.
    Returns the de-identified text + entity list.
    """
    if not body.text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "text must not be empty")

    detected = _detect_entities(body.text, body.entities)

    if body.use_llm:
        found_types = {d[0] for d in detected}
        active_types = set(body.entities or _ALL_ENTITY_TYPES)
        missing_types = list(active_types - found_types)
        if missing_types:
            llm_found = await _llm_detect_missing(body.text, missing_types)
            covered = set()
            for d in detected:
                covered |= set(range(d[2], d[3]))
            for ent in llm_found:
                span = set(range(ent[2], ent[3]))
                if not (span & covered):
                    detected.append(ent)
                    covered |= span
            detected.sort(key=lambda x: x[2])

    if not detected:
        return TokenizeResponse(text=body.text, entities=[], stored=0)

    await _check_and_increment_quota(user, len(detected), db)

    vault_key_bytes = decrypt_vault_key(user.vault_encryption_key).encode()
    user_fernet_key = decrypt_vault_key(user.vault_encryption_key)

    result_entities: list[TokenizeEntity] = []
    replacement_map: dict[str, str] = {}  # original → replacement

    # De-duplicate originals so same value always gets same replacement
    for entity_type, original, start, end in detected:
        if original not in replacement_map:
            if body.format_preserving:
                replacement = generate_fpe(entity_type, original, vault_key_bytes)
            else:
                replacement = f"[{entity_type}:{str(_uuid.uuid4())[:8]}]"
            replacement_map[original] = replacement

            # Store mapping in vault (replacement → encrypted original)
            token = replacement_map[original]
            existing = await db.execute(
                select(VaultEntry).where(
                    VaultEntry.user_id == user.id,
                    VaultEntry.token == token,
                )
            )
            if not existing.scalar_one_or_none():
                encrypted = encrypt_value(original, user_fernet_key)
                db.add(VaultEntry(
                    user_id=user.id,
                    token=token,
                    encrypted_value=encrypted,
                    entity_type=entity_type,
                    subject_id=body.subject_id,
                ))

    # Build de-identified text (replace from right to left to keep offsets valid)
    chars = list(body.text)
    for entity_type, original, start, end in reversed(detected):
        repl = replacement_map[original]
        chars[start:end] = list(repl)

    db.add(UsageLog(user_id=user.id, product=PRODUCT, operation="tokenize", units=len(detected)))
    await db.commit()

    deidentified = "".join(chars)
    for entity_type, original, start, end in detected:
        repl = replacement_map[original]
        result_entities.append(TokenizeEntity(
            original=original,
            replacement=repl,
            entity_type=entity_type,
            start=start,
            end=end,
        ))

    return TokenizeResponse(
        text=deidentified,
        entities=result_entities,
        stored=len(set(replacement_map)),
    )


@router.post("/detokenize", response_model=DetokenizeResponse)
async def detokenize(
    body: DetokenizeRequest,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Reverse a tokenized text — look up stored FPE replacements by token value
    and substitute back the original values.
    """
    if not body.text.strip():
        return DetokenizeResponse(text=body.text)

    # Extract candidate tokens from the text to avoid a full table scan.
    # FPE tokens match the same character classes as the originals they replaced,
    # so we use the same patterns to find them efficiently.
    candidate_tokens: set[str] = set()
    for _, pattern in _ENTITY_PATTERNS:
        for m in re.finditer(pattern, body.text):
            candidate_tokens.add(m.group())

    if not candidate_tokens:
        return DetokenizeResponse(text=body.text)

    rows = await db.execute(
        select(VaultEntry).where(
            VaultEntry.user_id == user.id,
            VaultEntry.token.in_(list(candidate_tokens)),
        ).limit(1_000)
    )
    entries = rows.scalars().all()

    if not entries:
        return DetokenizeResponse(text=body.text)

    user_fernet_key = decrypt_vault_key(user.vault_encryption_key)
    text = body.text

    for entry in entries:
        if entry.token in text:
            try:
                original = decrypt_value(entry.encrypted_value, user_fernet_key)
                text = text.replace(entry.token, original)
            except Exception:
                pass

    return DetokenizeResponse(text=text)


@router.get("/me/stats", response_model=StatsResponse)
async def me_stats(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """JWT-authenticated stats — used by the dashboard (no API key required)."""
    count_result = await db.execute(
        select(func.count()).where(VaultEntry.user_id == user.id)
    )
    total = count_result.scalar() or 0
    period = _current_period()
    monthly = user.monthly_token_count if user.monthly_period == period else 0
    return StatsResponse(
        total_entries=total,
        monthly_usage=monthly,
        monthly_period=user.monthly_period,
        quota=product_quota("pii_vault", user),
    )


@router.get("/stats", response_model=StatsResponse)
async def stats(
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    count_result = await db.execute(
        select(func.count()).where(VaultEntry.user_id == user.id)
    )
    total = count_result.scalar() or 0

    period = _current_period()
    if user.monthly_period != period:
        monthly = 0
    else:
        monthly = user.monthly_token_count

    return StatsResponse(
        total_entries=total,
        monthly_usage=monthly,
        monthly_period=user.monthly_period,
        quota=product_quota("pii_vault", user),
    )
