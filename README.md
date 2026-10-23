# ag-platform

Hosted API and dashboard for [ag-pii-vault](https://github.com/aghribi/ag-pii-vault), [ag-evalforge](https://github.com/aghribi/ag-evalforge), [ag-guardrail](https://github.com/aghribi/ag-guardrail) and [ag-docparse](https://github.com/aghribi/ag-docparse).

- `api/`: FastAPI service (Python 3.11, PostgreSQL). Accounts, API keys, organisations, per-account monthly limits, admin panel API, and the product endpoints under `/v1`.
- `dashboard/`: Next.js dashboard, deployed as a Cloudflare Worker (OpenNext) or as a container.
- `tests/`: integration test runner against a running API.

Production: API at https://ai-api.artifact-network.org, dashboard at https://ai.artifact-network.org.

## Run locally

```sh
cp api/.env.example api/.env        # set SECRET_KEY, SERVER_VAULT_KEY, ADMIN_TOKEN
docker compose up --build           # Postgres on :5433, API on :8100
cd dashboard && npm ci && NEXT_PUBLIC_API_URL=http://localhost:8100 npm run dev
```

The API creates its tables at startup and adds new columns to existing tables (`api/core/migrations.py`). Startup DDL is serialised with a Postgres advisory lock, so several workers can start at once.

## API settings

Set as environment variables (or in `api/.env`). Defaults are in `api/core/config.py`.

| Variable | Purpose | Production value |
|---|---|---|
| `DATABASE_URL` | asyncpg URL | `postgresql+asyncpg://...` |
| `SECRET_KEY` | Signs JWTs and admin sessions | random, 64 bytes |
| `SERVER_VAULT_KEY` | Encrypts per-user vault keys. Changing it makes existing vault data unreadable | unchanged from previous deployment |
| `PUBLIC_API_URL` | Public API address, used in compliance headers | `https://ai-api.artifact-network.org` |
| `DASHBOARD_URL` | Dashboard address: email links, redirects, default CORS origin, WebAuthn relying party | `https://ai.artifact-network.org` |
| `ALLOWED_ORIGINS` | CORS origins as a JSON list. Empty means `DASHBOARD_URL` plus `http://localhost:3000` | empty |
| `ADMIN_TOKEN` | Registers admin passkeys and works as a direct admin login | random |
| `WEBAUTHN_RP_ID`, `WEBAUTHN_ORIGIN` | Override the relying party derived from `DASHBOARD_URL` | empty |
| `RESEND_API_KEY` | Transactional email. Empty disables email | Resend key |
| `NOTIFY_FROM` | Sender address | `ai@artifact-network.org` |
| `CONTACT_EMAIL` | Receives support tickets, shown to users | `ai@artifact-network.org` |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `LLM_BACKEND` | LLM provider for judge, classifier and extraction | as needed |
| `LLAMA_PARSE_API_KEY` | Optional OCR for DocParse image input | optional |
| `QUOTA_PII_DEFAULT`, `QUOTA_EVAL_DEFAULT`, `QUOTA_GUARDRAIL_DEFAULT`, `QUOTA_DOC_DEFAULT`, `QUOTA_LLM_JUDGE_DEFAULT` | Default monthly limits per account | 10000, 1000, 5000, 100, 50 |
| `DOCPARSE_SCHEMA_SLOTS_DEFAULT`, `ORG_SEAT_LIMIT_DEFAULT` | Default schema slots and organisation seats | 2, 3 |
| `WEB_CONCURRENCY` | uvicorn workers | 2 |
| `HIDE_DOCS` | Hide `/docs` | `true` |

## Limits

Every user and organisation has monthly limits per product. A limit left empty uses the default above. Members of an organisation share the organisation's limits. The admin sets limits and seats from the admin panel (`/admin`, organisation rows and user rows) or with `PATCH /admin/users/{id}/limits` and `PATCH /admin/orgs/{id}/limits`; a `null` value resets a limit to the default. Extra units granted by the admin are used after the monthly limit and do not reset.

## API keys

New keys start with `ag_live_`. Keys issued with the earlier `mwl_` prefix remain valid.

## Admin access

Open `/admin/login` on the dashboard. The first time, or after a change of `DASHBOARD_URL`, register a passkey with `ADMIN_TOKEN`. Passkeys are bound to the dashboard hostname, so a hostname change requires a new one. `ADMIN_TOKEN` also works as a bearer token on the admin API.

## Deploy

API: build `api/Dockerfile` (port 8100, health check on `/health`) and run it with the settings above.

Dashboard on Cloudflare Workers (custom domain in `dashboard/wrangler.jsonc`):

```sh
cd dashboard && npm ci && npm run deploy
```

## Tests

```sh
AG_API_KEY=ag_live_... AG_JWT=eyJ... python3 tests/test_products.py --local
```

## License

MIT, Copyright (c) 2026 Adnan Ghribi.
