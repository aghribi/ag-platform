import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.dependencies import get_current_user_jwt
from core.email import send_verification, send_password_reset
from core.ratelimit import rate_limit
from core.security import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    create_verification_token,
    decode_verification_token,
    encrypt_vault_key,
    generate_vault_fernet_key,
    hash_password,
    verify_password,
)
from models.user import User
from models.vault import UsageLog

router = APIRouter()


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
    monthly_token_count: int
    monthly_period: str | None


class ProductUsage(BaseModel):
    product: str
    units: int


class UsageResponse(BaseModel):
    period: str
    total: int
    by_product: list[ProductUsage]


class SignupResponse(BaseModel):
    message: str = "Check your email to confirm your account"


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit(10, 3600, "signup"))])
async def signup(body: SignupRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    vault_key = generate_vault_fernet_key()
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        vault_encryption_key=encrypt_vault_key(vault_key),
        email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_verification_token(str(user.id))
    verify_url = f"{settings.dashboard}/verify-email?token={token}"
    background_tasks.add_task(send_verification, body.email, verify_url)
    return SignupResponse()


class VerifyEmailBody(BaseModel):
    token: str


@router.post("/verify-email", response_model=TokenResponse,
             dependencies=[Depends(rate_limit(20, 3600, "verify_email"))])
async def verify_email(body: VerifyEmailBody, db: AsyncSession = Depends(get_db)):
    user_id = decode_verification_token(body.token)
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification link")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired verification link")
    if user.email_verified:
        # Already verified — just return a token so clicking the link twice still works
        return TokenResponse(access_token=create_access_token(str(user.id)))

    user.email_verified = True
    await db.commit()
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=TokenResponse,
             dependencies=[Depends(rate_limit(10, 60, "login"))])
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Please confirm your email address before signing in")

    return TokenResponse(access_token=create_access_token(str(user.id)))


class PasswordResetRequestBody(BaseModel):
    email: EmailStr


class PasswordResetConfirmBody(BaseModel):
    token: str
    new_password: str


@router.post("/password-reset/request", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(rate_limit(5, 3600, "reset_request"))])
async def request_password_reset(body: PasswordResetRequestBody, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    # Always return 204 — never reveal whether email exists
    if user:
        token = create_reset_token(str(user.id))
        reset_url = f"{settings.dashboard}/reset-password?token={token}"
        background_tasks.add_task(send_password_reset, body.email, reset_url)


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(rate_limit(10, 3600, "reset_confirm"))])
async def confirm_password_reset(body: PasswordResetConfirmBody, db: AsyncSession = Depends(get_db)):
    user_id = decode_reset_token(body.token)
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")
    if len(body.new_password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Password must be at least 8 characters")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user.password_hash = hash_password(body.new_password)
    await db.commit()


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user_jwt)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        monthly_token_count=user.monthly_token_count,
        monthly_period=user.monthly_period,
    )


class SettingsUpdateRequest(BaseModel):
    quota_warn_threshold: int | None = None  # 10–95


@router.patch("/me/settings", response_model=UserResponse)
async def update_settings(
    body: SettingsUpdateRequest,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    if body.quota_warn_threshold is not None:
        if not (10 <= body.quota_warn_threshold <= 95):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "quota_warn_threshold must be between 10 and 95")
        user.quota_warn_threshold = body.quota_warn_threshold
        await db.commit()
    return UserResponse(
        id=str(user.id),
        email=user.email,
        monthly_token_count=user.monthly_token_count,
        monthly_period=user.monthly_period,
    )


@router.get("/me/usage", response_model=UsageResponse)
async def me_usage(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """Per-product usage breakdown for the current month."""
    now = datetime.now(timezone.utc)
    rows = await db.execute(
        select(UsageLog.product, func.sum(UsageLog.units).label("units"))
        .where(
            and_(
                UsageLog.user_id == user.id,
                extract("year", UsageLog.created_at) == now.year,
                extract("month", UsageLog.created_at) == now.month,
            )
        )
        .group_by(UsageLog.product)
        .order_by(func.sum(UsageLog.units).desc())
    )
    by_product = [ProductUsage(product=r.product, units=int(r.units)) for r in rows]
    total = sum(p.units for p in by_product)
    return UsageResponse(
        period=now.strftime("%Y-%m"),
        total=total,
        by_product=by_product,
    )


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.patch("/me/password")
async def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """Change account password. Requires current password for verification."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "New password must be at least 8 characters")
    user.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}


@router.delete("/me/vault")
async def delete_vault_data(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """Delete all PII vault entries for this user. Irreversible."""
    from models.vault import VaultEntry
    from sqlalchemy import delete
    await db.execute(delete(VaultEntry).where(VaultEntry.user_id == user.id))
    # Reset PII quota counters since all data is gone
    user.pii_tokens_mo = 0
    await db.commit()
    return {"ok": True}


@router.delete("/me")
async def delete_account(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete the account and all associated data.
    """
    from sqlalchemy import delete as sa_delete
    from models.vault import VaultEntry, UsageLog as ULog
    from models.api_key import APIKey
    from models.org_member import OrgMember
    from models.support_ticket import SupportTicket

    # Delete child rows (respect FK constraints)
    await db.execute(sa_delete(VaultEntry).where(VaultEntry.user_id == user.id))
    await db.execute(sa_delete(ULog).where(ULog.user_id == user.id))
    await db.execute(sa_delete(APIKey).where(APIKey.user_id == user.id))
    await db.execute(sa_delete(OrgMember).where(OrgMember.user_id == user.id))
    # Nullify user_id on support tickets rather than delete them (audit trail)
    from sqlalchemy import update
    await db.execute(
        update(SupportTicket)
        .where(SupportTicket.user_id == user.id)
        .values(user_id=None)
    )
    await db.delete(user)
    await db.commit()
    return {"ok": True}


@router.get("/me/usage/export")
async def export_usage(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """Export full usage history as CSV."""
    rows = await db.execute(
        select(UsageLog.product, UsageLog.operation, UsageLog.units, UsageLog.created_at)
        .where(UsageLog.user_id == user.id)
        .order_by(UsageLog.created_at.desc())
        .limit(10_000)
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "product", "operation", "units"])
    for row in rows:
        writer.writerow([row.created_at.isoformat(), row.product, row.operation, row.units])

    buf.seek(0)
    filename = f"ag-tools_usage_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
