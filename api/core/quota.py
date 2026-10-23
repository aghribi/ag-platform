"""Shared quota check + notification helper used by all product routers."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.email import send_quota_warning
from models.user import User

# Maps product name → column attribute on user / org models
_PRODUCT_COLUMN: dict[str, str] = {
    "pii_vault": "pii_tokens_mo",
    "evalforge": "eval_runs_mo",
    "guardrail": "guardrail_checks_mo",
    "docparse": "doc_pages_mo",
    "llm_judge": "llm_judge_calls_mo",
}

_ALL_PRODUCT_COLUMNS = list(_PRODUCT_COLUMN.values())


_TOPUP_COLUMN: dict[str, str] = {
    "pii_vault": "pii_topup",
    "evalforge": "eval_topup",
    "guardrail": "guardrail_topup",
    "docparse": "doc_topup",
}


_LIMIT_COLUMN: dict[str, str] = {
    "pii_vault": "pii_limit",
    "evalforge": "eval_limit",
    "guardrail": "guardrail_limit",
    "docparse": "doc_limit",
    "llm_judge": "llm_judge_limit",
}


def _default_quota(product: str) -> int:
    return {
        "pii_vault": settings.QUOTA_PII_DEFAULT,
        "evalforge": settings.QUOTA_EVAL_DEFAULT,
        "guardrail": settings.QUOTA_GUARDRAIL_DEFAULT,
        "docparse": settings.QUOTA_DOC_DEFAULT,
        "llm_judge": settings.QUOTA_LLM_JUDGE_DEFAULT,
    }.get(product, 0)


def product_quota(product: str, account) -> int:
    """Monthly unit limit for a product on a user or organisation: its own limit, else the default."""
    col = _LIMIT_COLUMN.get(product)
    own = getattr(account, col, None) if col else None
    return own if own is not None else _default_quota(product)


def schema_slots(account) -> int:
    own = getattr(account, "schema_slots", None)
    return own if own is not None else settings.DOCPARSE_SCHEMA_SLOTS_DEFAULT


def _reset_period_counters(obj) -> None:
    """Reset all per-product counters and warning flags at the start of a month."""
    for col in _ALL_PRODUCT_COLUMNS:
        setattr(obj, col, 0)
    obj.monthly_token_count = 0
    obj.quota_warned_80 = False
    obj.quota_warned_95 = False


async def check_and_increment(user: User, units: int, db: AsyncSession, product: str) -> None:
    """
    Validate product-specific quota and increment counter.
    For org members quota is tracked at the org level.
    Raises HTTP 429 if quota would be exceeded.
    Fires email alerts at 80 % (or user-configured threshold) and 95 %.
    """
    import asyncio

    col = _PRODUCT_COLUMN.get(product)
    if col is None:
        raise ValueError(f"Unknown product for quota tracking: {product!r}")

    period = datetime.now(timezone.utc).strftime("%Y-%m")

    # ── Org-level quota ───────────────────────────────────────────────────────
    if user.org_id:
        from sqlalchemy import select
        from models.organization import Organization
        from models.org_member import OrgMember

        result = await db.execute(select(Organization).where(Organization.id == user.org_id))
        org = result.scalar_one_or_none()
        if org:
            if org.monthly_period != period:
                _reset_period_counters(org)
                org.monthly_period = period

            quota = product_quota(product, org)
            current: int = getattr(org, col)
            new_count = current + units
            if new_count > quota:
                topup_col = _TOPUP_COLUMN.get(product)
                topup = getattr(org, topup_col, 0) if topup_col else 0
                excess = new_count - quota
                if topup_col and topup >= excess:
                    setattr(org, topup_col, topup - excess)
                else:
                    raise HTTPException(
                        status.HTTP_429_TOO_MANY_REQUESTS,
                        f"Team quota exceeded for {product} ({quota:,} units/mo). "
                        f"To request a higher limit, contact {settings.CONTACT_EMAIL}.",
                    )
            setattr(org, col, new_count)
            org.monthly_token_count = sum(getattr(org, c) for c in _ALL_PRODUCT_COLUMNS)

            # Notify org owner
            owner_result = await db.execute(
                select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.role == "owner")
            )
            owner_member = owner_result.scalar_one_or_none()
            owner_email = user.email
            if owner_member:
                from models.user import User as UserModel
                u_res = await db.execute(
                    select(UserModel).where(UserModel.id == owner_member.user_id)
                )
                owner_user = u_res.scalar_one_or_none()
                if owner_user:
                    owner_email = owner_user.email

            pct = new_count / quota * 100 if quota else 0
            if pct >= 95 and not org.quota_warned_95:
                org.quota_warned_95 = True
                asyncio.create_task(send_quota_warning(owner_email, 95, new_count, quota))
            elif pct >= 80 and not org.quota_warned_80:
                org.quota_warned_80 = True
                asyncio.create_task(send_quota_warning(owner_email, 80, new_count, quota))
            return

    # ── Individual quota ──────────────────────────────────────────────────────
    if user.monthly_period != period:
        _reset_period_counters(user)
        user.monthly_period = period

    quota = product_quota(product, user)
    current = getattr(user, col)
    new_count = current + units

    if new_count > quota:
        topup_col = _TOPUP_COLUMN.get(product)
        topup = getattr(user, topup_col, 0) if topup_col else 0
        excess = new_count - quota
        if topup_col and topup >= excess:
            setattr(user, topup_col, topup - excess)
        else:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"Monthly quota exceeded for {product} ({quota:,} units/mo). "
                f"To request a higher limit, contact {settings.CONTACT_EMAIL}.",
            )

    setattr(user, col, new_count)
    user.monthly_token_count = sum(getattr(user, c) for c in _ALL_PRODUCT_COLUMNS)

    threshold = getattr(user, "quota_warn_threshold", 80)
    pct = new_count / quota * 100 if quota else 0
    if pct >= 95 and not getattr(user, "quota_warned_95", False):
        user.quota_warned_95 = True
        asyncio.create_task(send_quota_warning(user.email, 95, new_count, quota))
    elif pct >= threshold and not getattr(user, "quota_warned_80", False):
        user.quota_warned_80 = True
        asyncio.create_task(send_quota_warning(user.email, threshold, new_count, quota))
