"""Razio Connect — Module 1A backend entrypoint.

Wiring order matters:
  1. Load .env before anything imports os.environ-dependent modules.
  2. Configure logging BEFORE routers import the loggers.
  3. Attach request-id middleware BEFORE CORS so downstream handlers see it.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.middleware.cors import CORSMiddleware  # noqa: E402

from db import client, db, ensure_indexes  # noqa: E402
from logging_config import app_logger, configure_logging  # noqa: E402
from security import Headers  # noqa: E402

configure_logging()
_log = app_logger()

app = FastAPI(
    title="Razio Connect API",
    version="1.0.0-module1a",
    description=(
        "Tally-integrated SaaS backend. Module 1A hardens the sync endpoint "
        "with HMAC-SHA256 auth, replay protection, idempotency, and audit "
        "logging. See /docs/SECURITY.md and /docs/adr/."
    ),
)


# ---------------------------------------------------------------------------
# Middleware: assign / propagate an X-Request-ID
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    incoming = request.headers.get(Headers.REQUEST_ID)
    request_id = incoming or f"req_{uuid.uuid4().hex[:16]}"
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except Exception:
        _log.exception("unhandled_error request_id=%s path=%s", request_id, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error", "request_id": request_id},
            headers={Headers.REQUEST_ID: request_id},
        )
    response.headers[Headers.REQUEST_ID] = request_id
    return response


# ---------------------------------------------------------------------------
# Consistent JSON error envelope for structured errors thrown by routers.
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        body = {**detail, "request_id": getattr(request.state, "request_id", "-")}
    else:
        body = {"detail": detail, "request_id": getattr(request.state, "request_id", "-")}
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers={Headers.REQUEST_ID: getattr(request.state, "request_id", "-")},
    )


# ---------------------------------------------------------------------------
# CORS — permissive by env (frontend on Emergent subdomain uses cookies)
# ---------------------------------------------------------------------------
_cors_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[Headers.REQUEST_ID, "X-Idempotent-Replayed"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from routes.auth import router as auth_router  # noqa: E402
from routes.connectors import router as connectors_router  # noqa: E402
from routes.tally import router as tally_router  # noqa: E402

app.include_router(auth_router)
app.include_router(connectors_router)
app.include_router(tally_router)


@app.get("/api")
async def api_root():
    return {"service": "razio-connect", "module": "1A", "status": "ok"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def _startup() -> None:
    await ensure_indexes()
    _log.info("razio_connect_started module=1A db=%s", os.environ["DB_NAME"])


@app.on_event("shutdown")
async def _shutdown() -> None:
    client.close()
