from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from core.admin_security import verify_admin_session
from core.config import settings
from core.database import get_db
from core.email import _send as send_raw
from core.quota import _LIMIT_COLUMN, product_quota, schema_slots
from models.organization import Organization
from models.org_member import OrgMember
from models.support_ticket import SupportTicket
from models.user import User

router = APIRouter(dependencies=[Depends(verify_admin_session)])

_PRODUCTS = ("pii_vault", "evalforge", "guardrail", "docparse", "llm_judge")


def _limits(account) -> dict:
    """Effective monthly limits, and whether each one is a per-account override."""
    out = {p: {"limit": product_quota(p, account), "custom": getattr(account, _LIMIT_COLUMN[p]) is not None} for p in _PRODUCTS}
    out["schema_slots"] = {"limit": schema_slots(account), "custom": account.schema_slots is not None}
    return out


def _uuid_or_400(value: str):
    import uuid as _uuid
    try:
        return _uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    """User and organisation counts."""
    total = (await db.execute(select(func.count()).select_from(User))).scalar()
    total_orgs = (await db.execute(select(func.count()).select_from(Organization))).scalar()
    return {"users": {"total": total}, "orgs": total_orgs}


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    limit: int = Query(default=200, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all users with quota usage, newest first."""
    users = (await db.execute(select(User).order_by(User.created_at.desc()).limit(limit))).scalars().all()

    def _quota_for(u: User) -> dict:
        return {
            "pii":      {"used": u.pii_tokens_mo,       "limit": product_quota("pii_vault", u), "topup": u.pii_topup},
            "eval":     {"used": u.eval_runs_mo,         "limit": product_quota("evalforge", u), "topup": u.eval_topup},
            "guardrail":{"used": u.guardrail_checks_mo,  "limit": product_quota("guardrail", u), "topup": u.guardrail_topup},
            "doc":      {"used": u.doc_pages_mo,         "limit": product_quota("docparse", u),  "topup": u.doc_topup},
        }

    return {
        "total": len(users),
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "org_id": str(u.org_id) if u.org_id else None,
                "monthly_period": u.monthly_period,
                "monthly_token_count": u.monthly_token_count,
                "quota": _quota_for(u),
                "custom_limits": any(getattr(u, c) is not None for c in _LIMIT_COLUMN.values()) or u.schema_slots is not None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.get("/users/{user_id}")
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single user's full profile."""
    user = await db.get(User, _uuid_or_400(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": str(user.id),
        "email": user.email,
        "org_id": str(user.org_id) if user.org_id else None,
        "monthly_period": user.monthly_period,
        "monthly_token_count": user.monthly_token_count,
        "pii_tokens_mo": user.pii_tokens_mo,
        "eval_runs_mo": user.eval_runs_mo,
        "guardrail_checks_mo": user.guardrail_checks_mo,
        "doc_pages_mo": user.doc_pages_mo,
        "llm_judge_calls_mo": user.llm_judge_calls_mo,
        "pii_topup": user.pii_topup,
        "eval_topup": user.eval_topup,
        "guardrail_topup": user.guardrail_topup,
        "doc_topup": user.doc_topup,
        "limits": _limits(user),
        "quota_warned_80": user.quota_warned_80,
        "quota_warned_95": user.quota_warned_95,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


class LimitsUpdate(BaseModel):
    """Monthly limits for one account. Omitted fields are unchanged; null resets to the default."""
    pii_limit: Optional[int] = Field(default=None, ge=0)
    eval_limit: Optional[int] = Field(default=None, ge=0)
    guardrail_limit: Optional[int] = Field(default=None, ge=0)
    doc_limit: Optional[int] = Field(default=None, ge=0)
    llm_judge_limit: Optional[int] = Field(default=None, ge=0)
    schema_slots: Optional[int] = Field(default=None, ge=0)


class OrgLimitsUpdate(LimitsUpdate):
    seat_limit: Optional[int] = Field(default=None, ge=1)


def _apply_limits(account, body: LimitsUpdate) -> None:
    for field in body.model_fields_set:
        value = getattr(body, field)
        if field == "seat_limit":
            account.seat_limit = value if value is not None else settings.ORG_SEAT_LIMIT_DEFAULT
        else:
            setattr(account, field, value)


@router.patch("/users/{user_id}/limits")
async def set_user_limits(user_id: str, body: LimitsUpdate, db: AsyncSession = Depends(get_db)):
    """Set a user's monthly limits (applies when the user is not in an organisation)."""
    user = await db.get(User, _uuid_or_400(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _apply_limits(user, body)
    await db.commit()
    return {"id": user_id, "limits": _limits(user)}


@router.patch("/orgs/{org_id}/limits")
async def set_org_limits(org_id: str, body: OrgLimitsUpdate, db: AsyncSession = Depends(get_db)):
    """Set an organisation's monthly limits (shared by its members) and seat limit."""
    org = await db.get(Organization, _uuid_or_400(org_id))
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    _apply_limits(org, body)
    await db.commit()
    return {"id": org_id, "seat_limit": org.seat_limit, "limits": _limits(org)}


class GrantTopupBody(BaseModel):
    product: str    # pii | eval | guardrail | doc
    units: int


@router.post("/users/{user_id}/grant-topup")
async def grant_topup(user_id: str, body: GrantTopupBody, db: AsyncSession = Depends(get_db)):
    """Grant extra units to a user, consumed after the monthly limit is reached. They do not reset."""
    import uuid as _uuid
    _product_map = {
        "pii": "pii_topup",
        "eval": "eval_topup",
        "guardrail": "guardrail_topup",
        "doc": "doc_topup",
    }
    if body.product not in _product_map:
        raise HTTPException(status_code=400, detail="product must be pii|eval|guardrail|doc")
    if body.units < 1:
        raise HTTPException(status_code=400, detail="units must be >= 1")
    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    attr = _product_map[body.product]
    current = getattr(user, attr)
    setattr(user, attr, current + body.units)
    await db.commit()
    return {"id": user_id, "product": body.product, attr: getattr(user, attr)}


@router.post("/users/{user_id}/reset-quota")
async def reset_user_quota(user_id: str, db: AsyncSession = Depends(get_db)):
    """Reset all monthly quota counters for a user (support / testing)."""
    import uuid as _uuid
    from datetime import datetime, timezone

    try:
        uid = _uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.pii_tokens_mo = 0
    user.eval_runs_mo = 0
    user.guardrail_checks_mo = 0
    user.doc_pages_mo = 0
    user.llm_judge_calls_mo = 0
    user.monthly_token_count = 0
    user.monthly_period = datetime.now(timezone.utc).strftime("%Y-%m")
    user.quota_warned_80 = False
    user.quota_warned_95 = False
    await db.commit()
    return {"id": user_id, "monthly_period": user.monthly_period, "reset": True}


# ── Organizations ──────────────────────────────────────────────────────────────

@router.get("/orgs")
async def list_orgs(db: AsyncSession = Depends(get_db)):
    """List all organizations with member counts."""
    orgs = (await db.execute(select(Organization).order_by(Organization.created_at.desc()))).scalars().all()
    result = []
    for org in orgs:
        seats_used = (
            await db.execute(
                select(func.count()).select_from(OrgMember).where(OrgMember.org_id == org.id)
            )
        ).scalar()
        result.append({
            "id": str(org.id),
            "name": org.name,
            "seat_limit": org.seat_limit,
            "seats_used": seats_used,
            "limits": _limits(org),
            "monthly_period": org.monthly_period,
            "pii_tokens_mo": org.pii_tokens_mo,
            "eval_runs_mo": org.eval_runs_mo,
            "guardrail_checks_mo": org.guardrail_checks_mo,
            "doc_pages_mo": org.doc_pages_mo,
            "created_at": org.created_at.isoformat() if org.created_at else None,
        })
    return {"total": len(result), "orgs": result}


# ── Metrics ────────────────────────────────────────────────────────────────────

@router.get("/metrics")
async def admin_metrics(db: AsyncSession = Depends(get_db)):
    """Full metrics: storage, AI token usage and cost by month, top users."""
    # ── Storage ────────────────────────────────────────────────────────────────
    vault_stats = (await db.execute(sa_text("""
        SELECT COUNT(*) AS entry_count,
               COALESCE(SUM(LENGTH(encrypted_value)), 0) AS total_bytes
        FROM vault_entries
    """))).mappings().one()

    usage_log_count = (await db.execute(sa_text(
        "SELECT COUNT(*) AS cnt FROM usage_logs"
    ))).mappings().one()

    # ── AI token usage by month ────────────────────────────────────────────────
    ai_rows = (await db.execute(sa_text("""
        SELECT month, product, model,
               SUM(input_tokens)  AS input_tokens,
               SUM(output_tokens) AS output_tokens,
               SUM(call_count)    AS calls
        FROM ai_usage_log
        GROUP BY month, product, model
        ORDER BY month DESC, calls DESC
    """))).mappings().all()

    # Cost rates (USD per token)
    _RATES = {
        "gpt-4o-mini":              (0.15 / 1_000_000,  0.60 / 1_000_000),
        "claude-haiku-4-5-20251001":(0.25 / 1_000_000,  1.25 / 1_000_000),
    }

    ai_by_month: dict = {}
    for row in ai_rows:
        m = row["month"]
        if m not in ai_by_month:
            ai_by_month[m] = {"month": m, "input_tokens": 0, "output_tokens": 0, "calls": 0, "cost_usd": 0.0, "by_product": []}
        in_rate, out_rate = _RATES.get(row["model"], (0.0, 0.0))
        in_tok, out_tok, calls = int(row["input_tokens"] or 0), int(row["output_tokens"] or 0), int(row["calls"] or 0)
        cost = in_tok * in_rate + out_tok * out_rate
        ai_by_month[m]["input_tokens"]  += in_tok
        ai_by_month[m]["output_tokens"] += out_tok
        ai_by_month[m]["calls"]         += calls
        ai_by_month[m]["cost_usd"]      += cost
        ai_by_month[m]["by_product"].append({
            "product": row["product"], "model": row["model"],
            "input_tokens": in_tok, "output_tokens": out_tok,
            "calls": calls, "cost_usd": round(cost, 4),
        })
    for m in ai_by_month:
        ai_by_month[m]["cost_usd"] = round(ai_by_month[m]["cost_usd"], 4)

    # Top 10 users by usage this period
    top_rows = (await db.execute(sa_text("""
        SELECT id::text, email,
               (pii_tokens_mo + eval_runs_mo + guardrail_checks_mo + doc_pages_mo) AS total_usage
        FROM users ORDER BY total_usage DESC LIMIT 10
    """))).mappings().all()

    return {
        "storage": {
            "vault_entries": int(vault_stats["entry_count"]),
            "vault_bytes": int(vault_stats["total_bytes"]),
            "vault_mb": round(int(vault_stats["total_bytes"]) / 1_048_576, 3),
            "usage_log_events": int(usage_log_count["cnt"]),
        },
        "ai_usage": sorted(ai_by_month.values(), key=lambda x: x["month"], reverse=True),
        "top_users": [dict(r) for r in top_rows],
    }


# ── Compose (send email) ───────────────────────────────────────────────────────

class ComposeRequest(BaseModel):
    to: str
    subject: str
    body: str


@router.post("/compose")
async def admin_compose(data: ComposeRequest):
    """Send a freeform email from NOTIFY_FROM via the admin panel."""
    safe_body = (
        data.body
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    html = (
        '<div style="font-family:sans-serif;max-width:560px;margin:0 auto;'
        'color:#111827;font-size:14px;line-height:1.7;white-space:pre-wrap">'
        + safe_body
        + "</div>"
    )
    await send_raw(data.to, data.subject, html)
    return {"ok": True}


# ── Support tickets ────────────────────────────────────────────────────────────

def _ser_ticket(t: SupportTicket) -> dict:
    return {
        "id": str(t.id),
        "user_id": str(t.user_id) if t.user_id else None,
        "email": t.email,
        "subject": t.subject,
        "message": t.message,
        "status": t.status,
        "admin_note": t.admin_note,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "handled_at": t.handled_at.isoformat() if t.handled_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    }


@router.get("/tickets")
async def list_tickets(
    status: Optional[str] = Query(default=None, description="open|handled|closed"),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SupportTicket).order_by(SupportTicket.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(SupportTicket.status == status)
    tickets = (await db.execute(stmt)).scalars().all()
    open_count = sum(1 for t in tickets if t.status == "open")
    return {"total": len(tickets), "open": open_count, "tickets": [_ser_ticket(t) for t in tickets]}


class TicketUpdate(BaseModel):
    status: str           # open | handled | closed
    admin_note: Optional[str] = None


@router.patch("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, body: TicketUpdate, db: AsyncSession = Depends(get_db)):
    import uuid as _uuid
    if body.status not in ("open", "handled", "closed"):
        raise HTTPException(status_code=400, detail="status must be open|handled|closed")
    try:
        tid = _uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket ID")

    ticket = await db.get(SupportTicket, tid)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket.status = body.status
    if body.admin_note is not None:
        ticket.admin_note = body.admin_note
    now = datetime.now(timezone.utc)
    if body.status == "handled" and not ticket.handled_at:
        ticket.handled_at = now
    if body.status == "closed" and not ticket.closed_at:
        ticket.closed_at = now
    await db.commit()
    return _ser_ticket(ticket)


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(ticket_id: str, db: AsyncSession = Depends(get_db)):
    import uuid as _uuid
    try:
        tid = _uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket ID")
    ticket = await db.get(SupportTicket, tid)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    await db.delete(ticket)
    await db.commit()
    return {"ok": True}
