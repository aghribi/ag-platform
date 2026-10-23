from sqlalchemy import BigInteger, Column, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy import DateTime

from core.database import Base


class AIUsageLog(Base):
    """Aggregated AI token usage per month/product/model — upserted after every llm_json_complete call."""
    __tablename__ = "ai_usage_log"
    __table_args__ = (
        UniqueConstraint("month", "product", "model", name="uq_ai_usage_month_product_model"),
    )

    id = Column(Integer, primary_key=True)
    month = Column(String(7), nullable=False, index=True)   # YYYY-MM
    product = Column(String(32), nullable=False)             # evalforge | guardrail | docparse | unknown
    model = Column(String(64), nullable=False)
    input_tokens = Column(BigInteger, nullable=False, default=0, server_default="0")
    output_tokens = Column(BigInteger, nullable=False, default=0, server_default="0")
    call_count = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
