"""
/admin-auth: WebAuthn passkey registration and login for the admin panel.

Flow:
  Registration (one-time, gated by ADMIN_TOKEN):
    POST /register/begin    → returns WebAuthn creation options
    POST /register/complete → verifies and stores the passkey

  Authentication (every login):
    POST /login/begin    → returns WebAuthn assertion options
    POST /login/complete → verifies assertion, returns 8h session JWT

  Status:
    GET /status → { registered: bool } — public, used by frontend

Challenges are stored in the database (5-minute TTL), so several workers can serve the flow.
The relying party follows DASHBOARD_URL. After a domain change, register a new passkey with
ADMIN_TOKEN; the token also works as a direct admin login.
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import webauthn
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request as FastAPIRequest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from core.admin_security import create_admin_session_jwt, verify_admin_token
from core.config import settings
from core.database import get_db
from models.admin_challenge import AdminChallenge
from models.admin_credential import AdminCredential

router = APIRouter()

_CHALLENGE_TTL = 300  # 5 minutes


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padded = s + "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(padded)


async def _store_challenge(db: AsyncSession, key: str, challenge: bytes) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(delete(AdminChallenge).where(AdminChallenge.expires_at < now))
    await db.merge(AdminChallenge(
        key=key, challenge=_b64url_encode(challenge), expires_at=now + timedelta(seconds=_CHALLENGE_TTL),
    ))
    await db.commit()


async def _pop_challenge(db: AsyncSession, key: str) -> Optional[bytes]:
    row = await db.get(AdminChallenge, key)
    if row is None:
        return None
    await db.delete(row)
    await db.commit()
    if datetime.now(timezone.utc) > row.expires_at:
        return None
    return _b64url_decode(row.challenge)


# ── Status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
async def webauthn_status(db: AsyncSession = Depends(get_db)):
    """Public. Returns whether any passkey is registered."""
    result = await db.execute(select(AdminCredential))
    creds = result.scalars().all()
    return {
        "registered": len(creds) > 0,
        "count": len(creds),
        "labels": [c.label for c in creds],
    }


# ── Registration ───────────────────────────────────────────────────────────────

@router.post("/register/begin", dependencies=[Depends(verify_admin_token)])
async def register_begin(db: AsyncSession = Depends(get_db)):
    """Start passkey registration. Requires X-Admin-Token header."""
    options = webauthn.generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name="ag-tools admin",
        user_id=b"admin",
        user_name="admin",
        user_display_name="ag-tools admin",
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
    )
    await _store_challenge(db, "register", options.challenge)
    return json.loads(webauthn.options_to_json(options))


@router.post("/register/complete", dependencies=[Depends(verify_admin_token)])
async def register_complete(request: FastAPIRequest, db: AsyncSession = Depends(get_db)):
    """Verify registration response and persist the credential."""
    expected_challenge = await _pop_challenge(db, "register")
    if expected_challenge is None:
        raise HTTPException(status_code=400, detail="No pending registration — restart the flow")

    body = await request.json()
    label = body.pop("label", "Passkey")

    try:
        verification = webauthn.verify_registration_response(
            credential=body,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Registration failed: {exc}")

    cred = AdminCredential(
        credential_id=verification.credential_id.hex(),
        public_key=verification.credential_public_key.hex(),
        sign_count=verification.sign_count,
        label=label,
    )
    db.add(cred)
    await db.commit()
    return {"ok": True, "label": label}


# ── Authentication ─────────────────────────────────────────────────────────────

@router.post("/login/begin")
async def login_begin(db: AsyncSession = Depends(get_db)):
    """Return challenge + allowed credentials. No auth required."""
    result = await db.execute(select(AdminCredential))
    creds = result.scalars().all()
    if not creds:
        raise HTTPException(
            status_code=404,
            detail="No passkeys registered — use X-Admin-Token to register one first",
        )

    allow = [PublicKeyCredentialDescriptor(id=bytes.fromhex(c.credential_id)) for c in creds]
    options = webauthn.generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    await _store_challenge(db, "login", options.challenge)
    return json.loads(webauthn.options_to_json(options))


@router.post("/login/complete")
async def login_complete(request: FastAPIRequest, db: AsyncSession = Depends(get_db)):
    """Verify passkey assertion, return an 8h admin session JWT."""
    expected_challenge = await _pop_challenge(db, "login")
    if expected_challenge is None:
        raise HTTPException(status_code=400, detail="No pending login challenge — restart the flow")

    body = await request.json()
    raw_id_b64 = body.get("rawId") or body.get("id", "")
    credential_id_hex = _b64url_decode(raw_id_b64).hex()

    result = await db.execute(
        select(AdminCredential).where(AdminCredential.credential_id == credential_id_hex)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=400, detail="Unknown passkey")

    try:
        verification = webauthn.verify_authentication_response(
            credential=body,
            expected_challenge=expected_challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=bytes.fromhex(cred.public_key),
            credential_current_sign_count=cred.sign_count,
            require_user_verification=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Passkey verification failed: {exc}")

    cred.sign_count = verification.new_sign_count
    await db.commit()

    return {"session_token": create_admin_session_jwt()}


# ── Credential management ──────────────────────────────────────────────────────

@router.delete("/credentials/{credential_id}", dependencies=[Depends(verify_admin_token)])
async def delete_credential(credential_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a registered passkey. Requires X-Admin-Token."""
    result = await db.execute(
        select(AdminCredential).where(AdminCredential.credential_id == credential_id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    await db.delete(cred)
    await db.commit()
    return {"ok": True}
