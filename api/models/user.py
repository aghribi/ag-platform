import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Legacy column, no longer read. Limits are the *_limit columns below.
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    org_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)

    # Envelope-encrypted Fernet key used to encrypt vault entries at rest
    vault_encryption_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Monthly usage — global total (display only, sum of per-product counters)
    monthly_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_period: Mapped[str | None] = mapped_column(String(7), nullable=True)  # YYYY-MM

    # Per-product monthly counters (quota enforcement)
    pii_tokens_mo: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    eval_runs_mo: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    guardrail_checks_mo: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    doc_pages_mo: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    llm_judge_calls_mo: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    # Per-account monthly limits set by the admin. NULL means the default from settings.
    pii_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eval_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    guardrail_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doc_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_judge_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_slots: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Extra units granted by the admin: non-resetting, consumed above the monthly limit
    pii_topup: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    eval_topup: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    guardrail_topup: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")
    doc_topup: Mapped[int] = mapped_column(Integer, default=0, nullable=False, server_default="0")

    quota_warned_80: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    quota_warned_95: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    quota_warn_threshold: Mapped[int] = mapped_column(Integer, default=80, nullable=False, server_default="80")  # % at which to send warning

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="user", lazy="select")  # noqa: F821
    vault_entries: Mapped[list["VaultEntry"]] = relationship("VaultEntry", back_populates="user", lazy="select")  # noqa: F821
