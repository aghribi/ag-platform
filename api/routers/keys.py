from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user_jwt
from core.security import generate_api_key
from models.api_key import APIKey
from models.user import User

router = APIRouter()

VALID_SCOPES = {"pii-vault", "eval", "guardrail", "docparse"}


class CreateKeyRequest(BaseModel):
    name: str
    scope: str | None = None          # None = all products
    expires_in_days: int | None = None # None = never


class KeyCreatedResponse(BaseModel):
    id: str
    name: str
    key: str
    prefix: str
    scope: str | None
    expires_at: str | None
    created_at: str


class KeyListItem(BaseModel):
    id: str
    name: str
    prefix: str
    is_active: bool
    scope: str | None
    expires_at: str | None
    last_used_at: str | None
    created_at: str


@router.post("", response_model=KeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateKeyRequest,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    if body.scope is not None and body.scope not in VALID_SCOPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"scope must be one of {sorted(VALID_SCOPES)} or null")
    if body.expires_in_days is not None and not (1 <= body.expires_in_days <= 3650):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "expires_in_days must be between 1 and 3650")

    full_key, prefix, key_hash = generate_api_key()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)
        if body.expires_in_days else None
    )
    api_key = APIKey(
        user_id=user.id,
        name=body.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scope=body.scope,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return KeyCreatedResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=full_key,
        prefix=prefix,
        scope=api_key.scope,
        expires_at=api_key.expires_at.isoformat() if api_key.expires_at else None,
        created_at=api_key.created_at.isoformat(),
    )


@router.get("", response_model=list[KeyListItem])
async def list_keys(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == user.id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        KeyListItem(
            id=str(k.id),
            name=k.name,
            prefix=k.key_prefix,
            is_active=k.is_active,
            scope=k.scope,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: str,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Key not found")
    key.is_active = False
    await db.commit()
