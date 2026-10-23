import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from cryptography.fernet import Fernet
from jose import jwt

from core.config import settings


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt(12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access"},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        # Verification and reset tokens share the key; only access tokens open a session.
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except Exception:
        return None


def create_verification_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "verify"},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_verification_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "verify":
            return None
        return payload.get("sub")
    except Exception:
        return None


def create_reset_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "reset"},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_reset_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "reset":
            return None
        return payload.get("sub")
    except Exception:
        return None


# ── API Keys ──────────────────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str, str]:
    """
    Returns (full_key, prefix, hash).
    full_key  = ag_live_<32-char-urlsafe-token>, shown once to the user
    prefix    = first 16 chars of full_key, stored for display
    hash      = SHA-256(full_key), stored for validation
    """
    token = secrets.token_urlsafe(32)
    full_key = f"ag_live_{token}"
    prefix = full_key[:16]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode()).hexdigest()


# ── Vault encryption ──────────────────────────────────────────────────────────

def generate_vault_fernet_key() -> str:
    """Generate a new Fernet key for a user's vault, returned as a string."""
    return Fernet.generate_key().decode()


def _server_fernet() -> Fernet:
    """Fernet instance keyed with the server vault key (for envelope encryption)."""
    key = settings.SERVER_VAULT_KEY.encode()
    if len(key) != 44:
        # Derive a proper Fernet key from an arbitrary secret
        import base64
        derived = hashlib.sha256(key).digest()
        key = base64.urlsafe_b64encode(derived)
    return Fernet(key)


def encrypt_vault_key(user_fernet_key: str) -> str:
    """Envelope-encrypt user's Fernet key with the server master key."""
    return _server_fernet().encrypt(user_fernet_key.encode()).decode()


def decrypt_vault_key(encrypted: str) -> str:
    """Decrypt the user's Fernet key."""
    return _server_fernet().decrypt(encrypted.encode()).decode()


def encrypt_value(value: str, user_fernet_key: str) -> str:
    return Fernet(user_fernet_key.encode()).encrypt(value.encode()).decode()


def decrypt_value(encrypted: str, user_fernet_key: str) -> str:
    return Fernet(user_fernet_key.encode()).decrypt(encrypted.encode()).decode()
