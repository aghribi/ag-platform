from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from core.database import Base


class AdminCredential(Base):
    __tablename__ = "admin_credentials"

    id = Column(Integer, primary_key=True)
    credential_id = Column(String, unique=True, nullable=False, index=True)  # hex
    public_key = Column(String, nullable=False)                               # hex
    sign_count = Column(Integer, default=0, nullable=False)
    label = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
