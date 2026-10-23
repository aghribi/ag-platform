"""Idempotent schema and data steps run at startup, after create_all.

create_all only creates missing tables, never missing columns, so new columns on
existing tables are added here.
"""
from sqlalchemy import text

_LIMIT_COLUMNS = ("pii_limit", "eval_limit", "guardrail_limit", "doc_limit", "llm_judge_limit", "schema_slots")

# Monthly limits of the former paid plans, as they were in config.py when plans were removed.
# Accounts still on one of these plans get them as their own limits, once.
_FORMER_PLAN_LIMITS = {
    "pro":     {"pii_limit": 500_000,   "eval_limit": 50_000,  "guardrail_limit": 200_000,   "doc_limit": 5_000,  "llm_judge_limit": 2_000,  "schema_slots": 10},
    "starter": {"pii_limit": 1_000_000, "eval_limit": 100_000, "guardrail_limit": 400_000,   "doc_limit": 10_000, "llm_judge_limit": 5_000,  "schema_slots": 20},
    "team":    {"pii_limit": 2_000_000, "eval_limit": 200_000, "guardrail_limit": 1_000_000, "doc_limit": 20_000, "llm_judge_limit": 20_000, "schema_slots": 50},
}


async def run(conn) -> None:
    for table in ("users", "organizations"):
        for col in _LIMIT_COLUMNS:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} INTEGER"))

    # Carry former plan limits into per-account limits. Setting plan to 'free' in the same
    # statement makes this run once per account.
    for table in ("users", "organizations"):
        for plan, limits in _FORMER_PLAN_LIMITS.items():
            assignments = ", ".join(f"{col} = :{col}" for col in limits)
            await conn.execute(
                text(f"UPDATE {table} SET {assignments}, plan = 'free' WHERE plan = :plan"),
                {**limits, "plan": plan},
            )
