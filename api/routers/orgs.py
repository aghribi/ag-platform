"""Team / organisation management router."""
import secrets
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.dependencies import get_current_user_jwt
from core.email import send_org_invite
from core.quota import _PRODUCT_COLUMN, product_quota
from models.org_invite import OrgInvite
from models.org_member import OrgMember
from models.organization import Organization
from models.user import User

router = APIRouter()

INVITE_TTL_DAYS = 7


def _referral_code() -> str:
    return secrets.token_urlsafe(12)


def _invite_token() -> str:
    return secrets.token_urlsafe(32)


# ── Schemas ───────────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str


class OrgUpdate(BaseModel):
    name: str


class OrgResponse(BaseModel):
    id: str
    name: str
    seat_limit: int
    referral_code: str
    member_count: int
    monthly_token_count: int
    monthly_period: str | None
    created_at: str
    # Shared monthly usage and limit per product: {"pii_vault": {"used": 0, "limit": 10000}, ...}
    usage: dict[str, dict[str, int]]


def _org_response(org: Organization, member_count: int) -> "OrgResponse":
    usage = {
        product: {"used": getattr(org, col), "limit": product_quota(product, org)}
        for product, col in _PRODUCT_COLUMN.items()
    }
    return OrgResponse(
        id=str(org.id), name=org.name, seat_limit=org.seat_limit,
        referral_code=org.referral_code, member_count=member_count,
        monthly_token_count=org.monthly_token_count, monthly_period=org.monthly_period,
        created_at=org.created_at.isoformat(), usage=usage,
    )


class MemberResponse(BaseModel):
    user_id: str
    email: str
    role: str
    joined_at: str


class InviteRequest(BaseModel):
    email: EmailStr


class InviteResponse(BaseModel):
    id: str
    email: str
    invited_by: str
    created_at: str
    expires_at: str
    accepted: bool


class ReferralInfo(BaseModel):
    org_name: str
    referral_code: str
    signup_url: str


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_user_org(user: User, db: AsyncSession) -> Organization | None:
    if not user.org_id:
        return None
    result = await db.execute(select(Organization).where(Organization.id == user.org_id))
    return result.scalar_one_or_none()


async def _get_member_role(user: User, org: Organization, db: AsyncSession) -> str | None:
    result = await db.execute(
        select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == user.id)
    )
    m = result.scalar_one_or_none()
    return m.role if m else None


async def _require_owner_or_admin(user: User, org: Organization, db: AsyncSession) -> None:
    role = await _get_member_role(user, org, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner or admin role required.")


# ── Create org ────────────────────────────────────────────────────────────────

@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    body: OrgCreate,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    if user.org_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You already belong to an organisation.")

    org = Organization(
        name=body.name.strip(),
        referral_code=_referral_code(),
        seat_limit=settings.ORG_SEAT_LIMIT_DEFAULT,
    )
    db.add(org)
    await db.flush()

    member = OrgMember(org_id=org.id, user_id=user.id, role="owner")
    db.add(member)

    user.org_id = org.id
    await db.commit()

    return _org_response(org, 1)


# ── Get my org ────────────────────────────────────────────────────────────────

@router.get("/me", response_model=OrgResponse)
async def get_my_org(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_user_org(user, db)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't belong to any organisation.")

    count_result = await db.execute(select(OrgMember).where(OrgMember.org_id == org.id))
    member_count = len(count_result.scalars().all())

    return _org_response(org, member_count)


@router.patch("/me", response_model=OrgResponse)
async def update_org(
    body: OrgUpdate,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_user_org(user, db)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't belong to any organisation.")
    await _require_owner_or_admin(user, org, db)

    org.name = body.name.strip()
    await db.commit()

    count_result = await db.execute(select(OrgMember).where(OrgMember.org_id == org.id))
    member_count = len(count_result.scalars().all())

    return _org_response(org, member_count)


# ── Members ───────────────────────────────────────────────────────────────────

@router.get("/me/members", response_model=list[MemberResponse])
async def list_members(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_user_org(user, db)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't belong to any organisation.")

    members_result = await db.execute(select(OrgMember).where(OrgMember.org_id == org.id))
    members = members_result.scalars().all()

    out = []
    for m in members:
        u_result = await db.execute(select(User).where(User.id == m.user_id))
        u = u_result.scalar_one_or_none()
        if u:
            out.append(MemberResponse(
                user_id=str(m.user_id), email=u.email, role=m.role,
                joined_at=m.joined_at.isoformat(),
            ))
    return out


@router.delete("/me/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    target_user_id: str,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_user_org(user, db)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't belong to any organisation.")
    await _require_owner_or_admin(user, org, db)

    try:
        target_id = _uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid user ID.")

    if target_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove yourself.")

    member_result = await db.execute(
        select(OrgMember).where(OrgMember.org_id == org.id, OrgMember.user_id == target_id)
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found.")
    if member.role == "owner":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove the owner.")

    # Detach user from org
    target_result = await db.execute(select(User).where(User.id == target_id))
    target_user = target_result.scalar_one_or_none()
    if target_user:
        target_user.org_id = None

    await db.delete(member)
    await db.commit()


# ── Invites ───────────────────────────────────────────────────────────────────

@router.post("/me/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: InviteRequest,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_user_org(user, db)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't belong to any organisation.")
    await _require_owner_or_admin(user, org, db)

    # Check seat limit
    count_result = await db.execute(select(OrgMember).where(OrgMember.org_id == org.id))
    member_count = len(count_result.scalars().all())
    pending_result = await db.execute(
        select(OrgInvite).where(OrgInvite.org_id == org.id, OrgInvite.accepted_at.is_(None))
    )
    pending_count = len(pending_result.scalars().all())
    if member_count + pending_count >= org.seat_limit:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Seat limit reached ({org.seat_limit} seats).")

    # Check not already a member
    existing_user = await db.execute(select(User).where(User.email == body.email))
    existing = existing_user.scalar_one_or_none()
    if existing and existing.org_id == org.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User is already a member.")

    # Expire any previous pending invite for this email
    old_invite = await db.execute(
        select(OrgInvite).where(
            OrgInvite.org_id == org.id,
            OrgInvite.email == body.email,
            OrgInvite.accepted_at.is_(None),
        )
    )
    for old in old_invite.scalars().all():
        await db.delete(old)

    token = _invite_token()
    invite = OrgInvite(
        org_id=org.id,
        email=body.email,
        token=token,
        invited_by_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    await db.commit()

    invite_url = f"{settings.dashboard}/join/{token}"
    import asyncio
    asyncio.create_task(send_org_invite(body.email, org.name, invite_url, user.email))

    return InviteResponse(
        id=str(invite.id), email=invite.email, invited_by=user.email,
        created_at=invite.created_at.isoformat(), expires_at=invite.expires_at.isoformat(),
        accepted=False,
    )


@router.get("/me/invites", response_model=list[InviteResponse])
async def list_invites(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_user_org(user, db)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't belong to any organisation.")

    result = await db.execute(select(OrgInvite).where(OrgInvite.org_id == org.id))
    invites = result.scalars().all()

    out = []
    for inv in invites:
        invited_by_email = ""
        if inv.invited_by_id:
            u_res = await db.execute(select(User).where(User.id == inv.invited_by_id))
            u = u_res.scalar_one_or_none()
            invited_by_email = u.email if u else ""
        out.append(InviteResponse(
            id=str(inv.id), email=inv.email, invited_by=invited_by_email,
            created_at=inv.created_at.isoformat(), expires_at=inv.expires_at.isoformat(),
            accepted=inv.accepted_at is not None,
        ))
    return out


@router.delete("/me/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite(
    invite_id: str,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    org = await _get_user_org(user, db)
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You don't belong to any organisation.")
    await _require_owner_or_admin(user, org, db)

    result = await db.execute(
        select(OrgInvite).where(OrgInvite.id == invite_id, OrgInvite.org_id == org.id)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found.")
    await db.delete(invite)
    await db.commit()


# ── Accept invite (public) ────────────────────────────────────────────────────

@router.post("/accept/{token}")
async def accept_invite(
    token: str,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(OrgInvite).where(OrgInvite.token == token))
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found or already used.")
    if invite.accepted_at:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite already accepted.")
    if invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite has expired.")
    if invite.email.lower() != user.email.lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This invite was sent to a different email address.")
    if user.org_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You already belong to an organisation.")

    # Check seat limit again
    org_result2 = await db.execute(select(Organization).where(Organization.id == invite.org_id))
    invite_org = org_result2.scalar_one_or_none()
    seat_limit = invite_org.seat_limit if invite_org else settings.ORG_SEAT_LIMIT_DEFAULT
    count_result = await db.execute(select(OrgMember).where(OrgMember.org_id == invite.org_id))
    if len(count_result.scalars().all()) >= seat_limit:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Organisation seat limit reached.")

    member = OrgMember(org_id=invite.org_id, user_id=user.id, role="member")
    db.add(member)
    user.org_id = invite.org_id
    invite.accepted_at = datetime.now(timezone.utc)
    await db.commit()

    return {"message": "Welcome to the team!", "org_id": str(invite.org_id)}


# ── Referral info (public) ────────────────────────────────────────────────────

@router.get("/ref/{referral_code}", response_model=ReferralInfo)
async def referral_info(
    referral_code: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Organization).where(Organization.referral_code == referral_code)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral code not found.")

    return ReferralInfo(
        org_name=org.name,
        referral_code=org.referral_code,
        signup_url=f"{settings.dashboard}/signup?ref={referral_code}",
    )
