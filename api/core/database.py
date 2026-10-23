from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables() -> None:
    from models import user, api_key, vault, guardrail_policy, docparse_job, organization, org_member, org_invite, guardrail_audit, webhook, ai_usage_log  # noqa: F401 — registers models
    from core import migrations
    async with engine.begin() as conn:
        # Serialise startup DDL across uvicorn workers.
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('ag-platform-startup'))"))
        await conn.run_sync(Base.metadata.create_all)
        await migrations.run(conn)
