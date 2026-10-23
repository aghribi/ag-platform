"""
EU AI Act compliance middleware, headers, and transparency manifest.

Article mapping per product:
  - PII Vault          → Article 10 (Data governance)
  - EvalForge          → Article 9  (Risk management / testing)
  - Guardrail          → Article 9  (Risk management / safety controls)
  - Guardrail audit    → Article 12 (Record-keeping / audit logs)
  - DocParse           → Article 13 (Transparency / interpretable outputs)
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

_REGULATION = "Regulation (EU) 2024/1689"


def _transparency_url() -> str:
    """The machine-readable manifest served by this API at GET /v1/compliance."""
    return f"{settings.PUBLIC_API_URL.rstrip('/')}/v1/compliance"

_ROUTE_ARTICLE_MAP = {
    "/v1/pii-vault":          "10",   # Data governance and management
    "/v1/eval":               "9",    # Risk management systems and testing
    "/v1/guardrail/me/audit": "12",   # Record-keeping — more specific, must come first
    "/v1/guardrail":          "9",    # Risk management — safety controls
    "/v1/doc":                "13",   # Transparency and information provision
}

_ARTICLE_DESCRIPTIONS = {
    "9":  "Risk management system — evaluation, testing and safety controls (Art. 9 EU AI Act)",
    "10": "Data governance — PII protection and tokenisation (Art. 10 EU AI Act)",
    "12": "Record-keeping — auditable decision log for high-risk AI (Art. 12 EU AI Act)",
    "13": "Transparency — structured extraction enabling interpretable AI outputs (Art. 13 EU AI Act)",
}

_PRODUCT_COMPLIANCE: dict[str, dict] = {
    "pii_vault": {
        "article": "10",
        "title": "Data Governance and Management",
        "control": "PII tokenisation and vault — ensures AI pipelines do not expose personal data to model providers",
        "intended_use": "Tokenise and detokenise PII in AI prompts and responses. Stores encrypted mappings in a regional vault.",
        "limitations": "Covers structured PII categories; free-form document PII requires docparse integration.",
    },
    "evalforge": {
        "article": "9",
        "title": "Risk Management System",
        "control": "Evaluation and testing framework — systematic quality assurance for AI system outputs",
        "intended_use": "Score AI outputs against reference answers or LLM judges. Supports regression testing in CI/CD pipelines.",
        "limitations": "LLM-judge scorer accuracy depends on the judge model. Not a substitute for human evaluation on safety-critical decisions.",
    },
    "guardrail": {
        "article": "9",
        "title": "Risk Management System — Safety Controls",
        "control": "Runtime safety layer — detects prompt injection, jailbreaks, harmful content and PII leakage",
        "intended_use": "Screen AI inputs and outputs for safety violations before and after LLM calls.",
        "limitations": "Regex and classifier-based detection; adversarial inputs designed to evade known patterns may pass. LLM classifier adds latency.",
    },
    "guardrail_audit": {
        "article": "12",
        "title": "Record-Keeping",
        "control": "Auditable decision log — every guardrail check is logged with timestamp, direction, verdict and blocking reason",
        "intended_use": "Provide audit trail of AI safety decisions for compliance review and incident investigation.",
        "limitations": "Log retention subject to account quota. Text previews are truncated to 200 characters.",
    },
    "docparse": {
        "article": "13",
        "title": "Transparency and Information Provision",
        "control": "Structured extraction — converts unstructured documents into machine-readable fields, making AI-processed data interpretable",
        "intended_use": "Extract structured fields from PDFs and scanned documents. Supports compliance documentation workflows.",
        "limitations": "Extraction accuracy varies by document quality and layout complexity. Confidence scores are indicative.",
    },
}


class EUAIActMiddleware(BaseHTTPMiddleware):
    """Adds EU AI Act compliance and transparency headers to relevant API responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if not settings.EU_AI_ACT_COMPLIANCE:
            return response

        path = request.url.path
        for prefix, article in _ROUTE_ARTICLE_MAP.items():
            if path.startswith(prefix):
                response.headers["x-eu-ai-act-article"] = article
                response.headers["x-eu-ai-act-control"] = (
                    _ARTICLE_DESCRIPTIONS[article]
                    .replace("—", "-")  # em-dash → hyphen; HTTP headers must be latin-1
                    .encode("latin-1", errors="replace").decode("latin-1")
                )
                response.headers["x-eu-ai-act-regulation"] = _REGULATION
                response.headers["x-eu-ai-act-transparency-url"] = _transparency_url()
                break

        return response


def compliance_info(product: str) -> dict:
    """Return compliance metadata dict for inclusion in API response bodies."""
    info = _PRODUCT_COMPLIANCE.get(product)
    if not info:
        return {}
    return {
        "eu_ai_act": {
            "article": info["article"],
            "title": info["title"],
            "control": info["control"],
            "regulation": _REGULATION,
            "transparency_url": _transparency_url(),
        }
    }


def all_compliance_info() -> dict:
    """Return the full compliance manifest — used by GET /v1/compliance."""
    return {
        "regulation": _REGULATION,
        "transparency_url": _transparency_url(),
        "products": {
            k: {
                "article": v["article"],
                "title": v["title"],
                "control": v["control"],
                "intended_use": v["intended_use"],
                "limitations": v["limitations"],
            }
            for k, v in _PRODUCT_COMPLIANCE.items()
        },
    }
