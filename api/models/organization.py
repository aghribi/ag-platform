import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)

    # Legacy column, no longer read. Limits are the *_limit columns below.
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    seat_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Monthly usage — global total (display only, sum of per-product counters)
    monthly_token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    monthly_period: Mapped[str | None] = mapped_column(String(7), nullable=True)

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    members: Mapped[list["OrgMember"]] = relationship("OrgMember", back_populates="org", lazy="select")  # noqa: F821
    invites: Mapped[list["OrgInvite"]] = relationship("OrgInvite", back_populates="org", lazy="select")  # noqa: F821
