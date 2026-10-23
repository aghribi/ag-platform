from sqlalchemy import Column, DateTime, String

from core.database import Base


class AdminChallenge(Base):
    """Pending WebAuthn challenge. Stored in the database so any uvicorn worker can complete the flow."""

    __tablename__ = "admin_challenges"

    key = Column(String, primary_key=True)        # "register" or "login"
    challenge = Column(String, nullable=False)    # base64url
    expires_at = Column(DateTime(timezone=True), nullable=False)
