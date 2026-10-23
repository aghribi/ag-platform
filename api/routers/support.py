"""Support ticket endpoints — public submission + authenticated submission."""
import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.dependencies import get_current_user_jwt
from core.email import send_ticket_confirmation, send_ticket_notification
from core.ratelimit import rate_limit
from models.support_ticket import SupportTicket
from models.user import User

router = APIRouter()

_VALID_TYPES = ("bug", "feature", "quota", "other")


class TicketSubmit(BaseModel):
    email: EmailStr
    subject: str = Field(max_length=200)
    message: str = Field(max_length=5_000)
    ticket_type: str = "other"  # bug | feature | quota | other


class AuthenticatedTicketSubmit(BaseModel):
    subject: str = Field(max_length=200)
    message: str = Field(max_length=5_000)
    ticket_type: str = "other"


@router.post("/ticket", dependencies=[Depends(rate_limit(3, 3600, "support_ticket"))])
async def submit_ticket(body: TicketSubmit, db: AsyncSession = Depends(get_db)):
    """Public ticket submission (contact form). Links to user by email if found."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    ticket_type = body.ticket_type if body.ticket_type in _VALID_TYPES else "other"
    ticket = SupportTicket(
        user_id=user.id if user else None,
        email=body.email,
        subject=f"[{ticket_type}] {body.subject}",
        message=body.message,
        status="open",
    )
    db.add(ticket)
    await db.commit()
    asyncio.create_task(send_ticket_notification(
        settings.CONTACT_EMAIL, str(ticket.id), body.email, body.subject, body.message,
    ))
    asyncio.create_task(send_ticket_confirmation(body.email, str(ticket.id), body.subject))
    return {"ok": True, "id": str(ticket.id)}


@router.post("/ticket/me")
async def submit_ticket_authenticated(
    body: AuthenticatedTicketSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user_jwt),
):
    """Authenticated ticket submission from the dashboard. Auto-fills user_id and email."""
    ticket_type = body.ticket_type if body.ticket_type in _VALID_TYPES else "other"
    ticket = SupportTicket(
        user_id=user.id,
        email=user.email,
        subject=f"[{ticket_type}] {body.subject}",
        message=body.message,
        status="open",
    )
    db.add(ticket)
    await db.commit()
    asyncio.create_task(send_ticket_notification(
        settings.CONTACT_EMAIL, str(ticket.id), user.email, body.subject, body.message,
    ))
    asyncio.create_task(send_ticket_confirmation(user.email, str(ticket.id), body.subject))
    return {"ok": True, "id": str(ticket.id)}
