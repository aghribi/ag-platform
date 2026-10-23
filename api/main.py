from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from core.config import settings
from core.database import create_tables
from core.eu_ai_act import EUAIActMiddleware, all_compliance_info
from routers import auth, keys, pii_vault, evalforge, guardrail, docparse, orgs, webhooks, admin_auth, admin, support
import models.docparse_schema  # noqa: F401 — ensure table is created
import models.admin_credential  # noqa: F401 — ensure table is created
import models.support_ticket    # noqa: F401 — ensure table is created
import models.admin_challenge   # noqa: F401 — ensure table is created


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="ag-tools API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.HIDE_DOCS else "/docs",
    redoc_url=None,
)

app.add_middleware(EUAIActMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(keys.router, prefix="/keys", tags=["keys"])
app.include_router(pii_vault.router, prefix="/v1/pii-vault", tags=["pii-vault"])
app.include_router(evalforge.router, prefix="/v1/eval",      tags=["evalforge"])
app.include_router(guardrail.router, prefix="/v1/guardrail", tags=["guardrail"])
app.include_router(docparse.router,  prefix="/v1/doc",       tags=["docparse"])
app.include_router(orgs.router,      prefix="/orgs",          tags=["orgs"])
app.include_router(webhooks.router,   prefix="/webhooks",       tags=["webhooks"])
app.include_router(admin_auth.router, prefix="/admin-auth",     tags=["admin-auth"])
app.include_router(admin.router,      prefix="/admin",           tags=["admin"])
app.include_router(support.router,    prefix="/support",         tags=["support"])


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(settings.dashboard)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/v1/compliance", tags=["compliance"])
async def compliance_manifest():
    """Art. 13 transparency endpoint: machine-readable compliance manifest for all products."""
    return all_compliance_info()
