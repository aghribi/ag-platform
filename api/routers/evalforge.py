import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.quota import check_and_increment, product_quota
from core.database import get_db
from core.dependencies import get_current_user_jwt, require_scope
_auth = require_scope("eval")
from models.user import User
from models.vault import UsageLog

router = APIRouter()

PRODUCT = "evalforge"


# ── Pure-Python scorers ───────────────────────────────────────────────────────

def _exact_match(output: str, expected: str) -> float:
    return 1.0 if output.strip() == expected.strip() else 0.0


def _rouge_l(output: str, expected: str) -> float:
    """F1-based ROUGE-L (token-level LCS)."""
    pred = output.lower().split()
    ref = expected.lower().split()
    if not pred or not ref:
        return 0.0
    m, n = len(ref), len(pred)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref[i - 1] == pred[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[m][n]
    if lcs == 0:
        return 0.0
    precision = lcs / n
    recall = lcs / m
    return 2 * precision * recall / (precision + recall)


def _regex_match(output: str, pattern: str) -> float:
    try:
        return 1.0 if re.search(pattern, output) else 0.0
    except re.error:
        return 0.0


async def _llm_judge(input: str, output: str, expected: str | None, criteria: str | None) -> tuple[float, str]:
    """LLM judge (OpenAI or Claude Haiku): returns (score 0.0–1.0, rationale)."""
    from core.llm import llm_json_complete

    rubric_parts = []
    if expected:
        rubric_parts.append(f"Reference answer: {expected}")
    if criteria:
        rubric_parts.append(f"Evaluation criteria: {criteria}")
    if not rubric_parts:
        rubric_parts.append("Evaluate overall quality, accuracy, and helpfulness.")
    rubric = "\n".join(rubric_parts)

    prompt = f"""You are an objective evaluator. Score the following LLM output on a scale from 0.0 to 1.0.

Input: {input}
Output to evaluate: {output}
{rubric}

Respond with JSON only: {{"score": <float 0.0-1.0>, "rationale": "<one sentence>"}}"""

    try:
        data = await llm_json_complete(prompt, max_tokens=120, timeout=20.0, product="evalforge")
        score = max(0.0, min(1.0, float(data.get("score", 0.0))))
        rationale = str(data.get("rationale", ""))
    except Exception:
        score, rationale = 0.0, "Failed to parse judge response."

    return round(score, 4), rationale


async def _pairwise_judge(
    prompt: str,
    response_a: str,
    response_b: str,
    criteria: str | None,
) -> tuple[str, float, str]:
    """Direct A-vs-B comparison in a single LLM call. Returns (winner: 'A'|'B'|'tie', confidence, rationale)."""
    from core.llm import llm_json_complete

    rubric = criteria or "Evaluate overall quality, accuracy, helpfulness, and correctness."

    judge_prompt = f"""You are comparing two AI responses to the same input. Decide which response is better.

Input prompt: {prompt[:3000]}

Response A:
{response_a[:3000]}

Response B:
{response_b[:3000]}

Evaluation criteria: {rubric}

Analyze both responses carefully. Consider accuracy, completeness, clarity, and relevance.

Respond with JSON only: {{"winner": "A" or "B" or "tie", "confidence": <0.0-1.0>, "rationale": "<one sentence explaining the winner>"}}"""

    try:
        data = await llm_json_complete(judge_prompt, max_tokens=150, timeout=25.0, product="evalforge")
        winner = str(data.get("winner", "tie")).upper()
        if winner not in ("A", "B", "TIE"):
            winner = "TIE"
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        rationale = str(data.get("rationale", ""))
    except Exception:
        winner, confidence, rationale = "TIE", 0.5, "Failed to parse judge response."

    return winner, round(confidence, 4), rationale


# ── Schemas ───────────────────────────────────────────────────────────────────

class EvalCase(BaseModel):
    input: str = Field(max_length=20_000)
    output: str = Field(max_length=20_000)
    expected: str | None = Field(default=None, max_length=20_000)


class ScoreRequest(BaseModel):
    cases: list[EvalCase] = Field(max_length=500)
    scorer: Literal["exact_match", "rouge_l", "regex", "llm_judge", "pairwise_judge"] = "exact_match"
    threshold: float = 0.5
    pattern: str | None = Field(default=None, max_length=500)
    criteria: str | None = Field(default=None, max_length=2_000)


class CaseResult(BaseModel):
    input: str
    output: str
    expected: str | None
    score: float
    passed: bool
    rationale: str | None = None  # populated for llm_judge only


class ScoreResponse(BaseModel):
    scorer: str
    mean_score: float
    pass_rate: float
    results: list[CaseResult]
    units: int


class StatsResponse(BaseModel):
    monthly_usage: int
    monthly_period: str
    quota: int


# ── Quota helper ──────────────────────────────────────────────────────────────

async def _check_and_increment_quota(user: User, units: int, db: AsyncSession) -> None:
    await check_and_increment(user, units, db, product=PRODUCT)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/score", response_model=ScoreResponse)
async def score(
    body: ScoreRequest,
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    if not body.cases:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "cases must not be empty")
    if body.scorer == "regex" and not body.pattern:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "pattern required for regex scorer")
    if body.scorer == "pairwise_judge" and len(body.cases) != 2:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "pairwise_judge requires exactly 2 cases: cases[0]=response A, cases[1]=response B",
        )

    await _check_and_increment_quota(user, len(body.cases), db)

    # Extra cap for LLM judge calls (cost-protection, separate from eval_runs quota)
    if body.scorer in ("llm_judge", "pairwise_judge"):
        await check_and_increment(user, 1, db, product="llm_judge")

    results: list[CaseResult] = []

    if body.scorer == "pairwise_judge":
        case_a, case_b = body.cases[0], body.cases[1]
        shared_prompt = case_a.input
        winner, confidence, rationale = await _pairwise_judge(
            shared_prompt, case_a.output, case_b.output, body.criteria
        )
        score_a = 1.0 if winner == "A" else (0.5 if winner == "TIE" else 0.0)
        score_b = 1.0 if winner == "B" else (0.5 if winner == "TIE" else 0.0)
        results.append(CaseResult(
            input=case_a.input, output=case_a.output, expected=case_a.expected,
            score=score_a, passed=score_a >= body.threshold, rationale=f"Winner: {winner} (confidence={confidence}) — {rationale}",
        ))
        results.append(CaseResult(
            input=case_b.input, output=case_b.output, expected=case_b.expected,
            score=score_b, passed=score_b >= body.threshold, rationale=None,
        ))
    else:
        for case in body.cases:
            ref = case.expected or ""
            rationale: str | None = None
            if body.scorer == "exact_match":
                score_val = _exact_match(case.output, ref)
            elif body.scorer == "rouge_l":
                score_val = _rouge_l(case.output, ref)
            elif body.scorer == "llm_judge":
                score_val, rationale = await _llm_judge(case.input, case.output, case.expected, body.criteria)
            else:
                score_val = _regex_match(case.output, body.pattern or "")
            results.append(CaseResult(
                input=case.input,
                output=case.output,
                expected=case.expected,
                score=round(score_val, 4),
                passed=score_val >= body.threshold,
                rationale=rationale,
            ))

    mean_score = sum(r.score for r in results) / len(results)
    pass_rate = sum(1 for r in results if r.passed) / len(results)

    db.add(UsageLog(
        user_id=user.id,
        product=PRODUCT,
        operation="score",
        units=len(body.cases),
    ))
    await db.commit()

    return ScoreResponse(
        scorer=body.scorer,
        mean_score=round(mean_score, 4),
        pass_rate=round(pass_rate, 4),
        results=results,
        units=len(body.cases),
    )


@router.get("/me/stats", response_model=StatsResponse)
async def me_stats(
    user: User = Depends(get_current_user_jwt),
    db: AsyncSession = Depends(get_db),
):
    """JWT-authenticated stats — used by the dashboard."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(func.coalesce(func.sum(UsageLog.units), 0)).where(
            and_(
                UsageLog.user_id == user.id,
                UsageLog.product == PRODUCT,
                extract("year", UsageLog.created_at) == now.year,
                extract("month", UsageLog.created_at) == now.month,
            )
        )
    )
    return StatsResponse(
        monthly_usage=int(result.scalar() or 0),
        monthly_period=now.strftime("%Y-%m"),
        quota=product_quota("evalforge", user),
    )


@router.get("/stats", response_model=StatsResponse)
async def stats(
    user: User = Depends(_auth),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(func.coalesce(func.sum(UsageLog.units), 0)).where(
            and_(
                UsageLog.user_id == user.id,
                UsageLog.product == PRODUCT,
                extract("year", UsageLog.created_at) == now.year,
                extract("month", UsageLog.created_at) == now.month,
            )
        )
    )
    monthly = int(result.scalar() or 0)
    return StatsResponse(
        monthly_usage=monthly,
        monthly_period=now.strftime("%Y-%m"),
        quota=product_quota("evalforge", user),
    )
