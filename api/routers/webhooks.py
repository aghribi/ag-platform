import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.dependencies import get_current_user_jwt
from models.user import User
from models.webhook import WebhookEndpoint, VALID_EVENTS

router = APIRouter()


class CreateWebhookRequest(BaseModel):
    url: str
    events: list[str]


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: list[str]
    secret: str | None  # returned only on creation
    is_active: bool
    created_at: str


@router.post("", response_model=WebhookResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: CreateWebhookRequest,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    unknown = [e for e in body.events if e not in VALID_EVENTS]
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Unknown events: {unknown}. Valid: {sorted(VALID_EVENTS)}")
    if not body.url.startswith("https://"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "URL must use HTTPS")

    # Limit 10 endpoints per user
    count_result = await db.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.user_id == user.id, WebhookEndpoint.is_active.is_(True))
    )
    if len(count_result.scalars().all()) >= 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maximum of 10 active webhook endpoints reached")

    secret = secrets.token_hex(32)
    endpoint = WebhookEndpoint(
        user_id=user.id,
        url=body.url,
        events=",".join(body.events),
        secret=secret,
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)

    return WebhookResponse(
        id=str(endpoint.id),
        url=endpoint.url,
        events=endpoint.events.split(","),
        secret=secret,  # shown once
        is_active=endpoint.is_active,
        created_at=endpoint.created_at.isoformat(),
    )


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.user_id == user.id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    endpoints = result.scalars().all()
    return [
        WebhookResponse(
            id=str(e.id),
            url=e.url,
            events=e.events.split(","),
            secret=None,  # never shown after creation
            is_active=e.is_active,
            created_at=e.created_at.isoformat(),
        )
        for e in endpoints
    ]


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    endpoint_id: str,
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.id == endpoint_id, WebhookEndpoint.user_id == user.id)
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook endpoint not found")
    endpoint.is_active = False
    await db.commit()
