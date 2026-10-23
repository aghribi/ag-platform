"""Unified LLM call layer — routes to OpenAI or Anthropic Claude Haiku based on settings."""
import json
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status

from core.config import settings

_OPENAI_MODEL = "gpt-4o-mini"
_HAIKU_MODEL  = "claude-haiku-4-5-20251001"


async def _log_usage(product: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """Upsert aggregated token usage into ai_usage_log. Fire-and-forget — never raises."""
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from core.database import AsyncSessionLocal as async_session_factory
        from models.ai_usage_log import AIUsageLog

        month = datetime.now(timezone.utc).strftime("%Y-%m")
        async with async_session_factory() as session:
            stmt = pg_insert(AIUsageLog).values(
                month=month, product=product, model=model,
                input_tokens=input_tokens, output_tokens=output_tokens, call_count=1,
            ).on_conflict_do_update(
                constraint="uq_ai_usage_month_product_model",
                set_={
                    "input_tokens":  AIUsageLog.input_tokens  + input_tokens,
                    "output_tokens": AIUsageLog.output_tokens + output_tokens,
                    "call_count":    AIUsageLog.call_count    + 1,
                },
            )
            await session.execute(stmt)
            await session.commit()
    except Exception:
        pass  # never block the caller


async def llm_json_complete(
    prompt: str,
    max_tokens: int = 300,
    timeout: float = 20.0,
    product: str = "unknown",
) -> dict:
    """
    Send a single-turn prompt expecting a JSON response.
    Routes to OpenAI (gpt-4o-mini) or Anthropic Claude Haiku based on LLM_BACKEND setting.
    Returns parsed JSON dict. Logs token usage asynchronously.
    """
    if settings.LLM_BACKEND == "anthropic":
        return await _anthropic_json(prompt, max_tokens, timeout, product)
    return await _openai_json(prompt, max_tokens, timeout, product)


async def _openai_json(prompt: str, max_tokens: int, timeout: float, product: str) -> dict:
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OpenAI API key not configured.")

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _OPENAI_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": max_tokens,
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"OpenAI request failed ({resp.status_code}).")
    try:
        body = resp.json()
        usage = body.get("usage", {})
        await _log_usage(product, _OPENAI_MODEL, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        return json.loads(body["choices"][0]["message"]["content"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to parse OpenAI JSON response.")


async def _anthropic_json(prompt: str, max_tokens: int, timeout: float, product: str) -> dict:
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Anthropic API key not configured.")

    system = "You are a precise evaluator. Always respond with valid JSON only, no markdown fences."
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": _HAIKU_MODEL,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Anthropic request failed ({resp.status_code}).")
    try:
        body = resp.json()
        usage = body.get("usage", {})
        await _log_usage(product, _HAIKU_MODEL, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        text = body["content"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Failed to parse Anthropic JSON response.")
