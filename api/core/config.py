from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://ag:ag@localhost:5432/ag_platform"
    SECRET_KEY: str = "change-me-in-production"
    SERVER_VAULT_KEY: str = "change-me-vault-key-32-chars-min"  # Fernet key for encrypting vault values

    # Public addresses. Links in emails, redirects, CORS and WebAuthn derive from these.
    PUBLIC_API_URL: str = "https://ai-api.artifact-network.org"
    DASHBOARD_URL: str = "https://ai.artifact-network.org"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Default monthly limits per account (user, or organisation for its members).
    # An admin can set a different limit per account from the admin panel.
    QUOTA_PII_DEFAULT: int = 10_000        # PII Vault token operations
    QUOTA_EVAL_DEFAULT: int = 1_000        # EvalForge cases scored
    QUOTA_GUARDRAIL_DEFAULT: int = 5_000   # Guardrail check requests
    QUOTA_DOC_DEFAULT: int = 100           # DocParse pages extracted
    QUOTA_LLM_JUDGE_DEFAULT: int = 50      # LLM judge/classifier calls (EvalForge + Guardrail)
    DOCPARSE_SCHEMA_SLOTS_DEFAULT: int = 2
    ORG_SEAT_LIMIT_DEFAULT: int = 3

    # Email (Resend)
    RESEND_API_KEY: str = ""
    NOTIFY_FROM: str = "ai@artifact-network.org"
    # Receives support tickets; shown to users as the contact address.
    CONTACT_EMAIL: str = "ai@artifact-network.org"

    # Quota alert thresholds (fractions)
    QUOTA_WARN_80: float = 0.80
    QUOTA_WARN_95: float = 0.95

    # OpenAI (used by evalforge LLM judge, guardrail ML classifier, docparse extraction)
    OPENAI_API_KEY: str = ""

    # LLM backend: "openai" (default) or "anthropic" (Claude Haiku)
    LLM_BACKEND: str = "openai"
    ANTHROPIC_API_KEY: str = ""

    # LlamaParse: optional OCR provider for DocParse image input
    LLAMA_PARSE_API_KEY: str = ""

    # EU AI Act compliance flag (adds x-eu-ai-act-article headers to responses)
    EU_AI_ACT_COMPLIANCE: bool = True

    # CORS. Empty means DASHBOARD_URL plus http://localhost:3000.
    ALLOWED_ORIGINS: list[str] = []

    # Admin panel. ADMIN_TOKEN registers passkeys and also works as a direct admin login,
    # so a change of DASHBOARD_URL (which invalidates existing passkeys) cannot lock the admin out.
    ADMIN_TOKEN: str = ""
    ADMIN_SESSION_HOURS: int = 8
    # Empty means derived from DASHBOARD_URL.
    WEBAUTHN_RP_ID: str = ""
    WEBAUTHN_ORIGIN: str = ""

    # Set to True in production to hide /docs and /redoc endpoints
    HIDE_DOCS: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return self.ALLOWED_ORIGINS or [self.DASHBOARD_URL.rstrip("/"), "http://localhost:3000"]

    @property
    def webauthn_rp_id(self) -> str:
        return self.WEBAUTHN_RP_ID or (urlparse(self.DASHBOARD_URL).hostname or "")

    @property
    def webauthn_origin(self) -> str:
        return self.WEBAUTHN_ORIGIN or self.DASHBOARD_URL.rstrip("/")

    @property
    def dashboard(self) -> str:
        return self.DASHBOARD_URL.rstrip("/")


settings = Settings()
