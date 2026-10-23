from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from core.config import settings


def create_admin_session_jwt() -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "admin",
        "type": "admin_session",
        "iat": now,
        "exp": now + timedelta(hours=settings.ADMIN_SESSION_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


async def verify_admin_token(x_admin_token: str = Header(default=None)):
    """Bootstrap gate — required to register/delete WebAuthn passkeys."""
    if x_admin_token and x_admin_token == settings.ADMIN_TOKEN:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin token")


async def verify_admin_session(
    x_admin_token: str = Header(default=None),
    authorization: str = Header(default=None),
):
    """
    Gate for admin panel endpoints. Accepts either:
      1. Authorization: Bearer {session_jwt}  — issued by WebAuthn login (8h)
      2. Authorization: Bearer {raw_token}    — raw ADMIN_TOKEN as Bearer
      3. X-Admin-Token: {raw_token}           — raw ADMIN_TOKEN header (curl/CLI)
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("type") == "admin_session" and payload.get("sub") == "admin":
                return
        except JWTError:
            pass
        if settings.ADMIN_TOKEN and token == settings.ADMIN_TOKEN:
            return

    if x_admin_token and settings.ADMIN_TOKEN and x_admin_token == settings.ADMIN_TOKEN:
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authentication required")
