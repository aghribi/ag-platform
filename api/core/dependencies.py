from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import decode_access_token, hash_api_key

_bearer = HTTPBearer(auto_error=False)


async def get_current_user_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Validate JWT — used by dashboard/web endpoints."""
    from models.user import User

    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


async def _resolve_api_key(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
    required_scope: str | None = None,
):
    """Shared logic for API key validation, expiry, and scope enforcement."""
    from sqlalchemy.orm import selectinload

    from models.api_key import APIKey

    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key required")

    token = credentials.credentials
    # mwl_ is the prefix of keys issued before the ag_ rename; those keys stay valid.
    if not token.startswith(("ag_", "mwl_")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key format")

    key_hash = hash_api_key(token)
    result = await db.execute(
        select(APIKey)
        .options(selectinload(APIKey.user))
        .where(APIKey.key_hash == key_hash, APIKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key has expired")

    if required_scope and api_key.scope and api_key.scope != required_scope:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This key is scoped to '{api_key.scope}' and cannot access '{required_scope}'",
        )

    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    return api_key.user


async def get_current_user_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
):
    """Validate API key, used by SDK endpoints (ag_live_...)."""
    return await _resolve_api_key(credentials, db, required_scope=None)


def require_scope(product: str):
    """Dependency factory: validate API key and enforce product scope."""

    async def _check(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
        db: AsyncSession = Depends(get_db),
    ):
        return await _resolve_api_key(credentials, db, required_scope=product)

    return _check
