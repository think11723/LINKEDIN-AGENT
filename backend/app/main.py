"""FastAPI application entry point for the SaaS backend layer."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.v1.activity import router as activity_router
from backend.app.api.v1.approval import router as approval_router
from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.content import router as content_router
from backend.app.api.v1.dashboard import router as dashboard_router
from backend.app.api.v1.drafts import router as drafts_router
from backend.app.api.v1.linkedin import router as linkedin_router
from backend.app.api.v1.profile import router as profile_router
from backend.app.api.v1.publishing import router as publishing_router
from backend.app.api.v1.scheduler import router as scheduler_router
from backend.app.api.v1.settings import router as settings_router
from backend.app.core import security as _security
from backend.app.core.config import get_settings
from backend.app.core.error_handlers import install_error_handlers
from backend.app.core.logging import configure_json_logging
from backend.app.core.request_id import (
    RequestIdMiddleware,
    install_request_id_log_filter,
)
from backend.app.core.security import init_firebase
from backend.app.db import mongo as _mongo
from backend.app.db.mongo import close_mongo, ensure_indexes, init_mongo
from backend.app.services.scheduler_runner import SchedulerRunner
from backend.app.services.source_job_runner import SourceJobRunner
from backend.app.services.sources.ssrf import warn_if_allow_private

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # MongoDB must be reachable. Failure is loud and fast.
    init_mongo(settings)
    await _mongo.ping_mongo()
    await ensure_indexes()

    # Firebase Admin SDK is required for all auth.
    init_firebase(settings)

    # Phase 8A / P0-3: recover scheduler jobs orphaned by a previous
    # crash. Idempotent — safe to call on every cold start.
    from backend.app.repositories.scheduler_repository import SchedulerRepository

    scheduler_repo = SchedulerRepository(_mongo.get_database())
    recovered = await scheduler_repo.recover_orphans(older_than_seconds=600)
    if recovered:
        logger.warning(
            "Recovered %d orphan scheduler job(s) from previous process.",
            recovered,
        )

    scheduler_runner = SchedulerRunner(poll_interval=5.0)
    scheduler_runner.start()
    app.state.scheduler_runner = scheduler_runner

    # Phase 8D / URL-to-LinkedIn — source-job runner for the new
    # ``/generate-from-url`` endpoint. Mirrors the scheduler runner's
    # in-process asyncio pattern.
    source_runner = SourceJobRunner(poll_interval=2.0)
    source_runner.start()
    app.state.source_runner = source_runner
    warn_if_allow_private()

    logger.info("Backend startup complete.")
    try:
        yield
    finally:
        await source_runner.stop()
        await scheduler_runner.stop()
        await close_mongo()
        logger.info("Backend shutdown complete.")


app = FastAPI(
    title="LinkedIn Content SaaS API",
    version="0.2.0",
    description=(
        "Multi-user REST API for the LinkedIn content orchestration engine. "
        "All endpoints (except /health and /api/v1/linkedin/callback) require a "
        "Firebase ID token in the Authorization header."
    ),
    lifespan=lifespan,
)

settings = get_settings()
# P3-1: install request-ID log filter and middleware. Middleware is added
# before CORSMiddleware so the response header is stamped on every
# response including those produced by the global error handlers.
install_request_id_log_filter()
# P3-2: install JSON logging on the root logger. Idempotent and
# side-effect-free for any handler that is not the JSON handler — so
# caplog and other test instrumentation remain intact.
configure_json_logging()
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(content_router)
app.include_router(drafts_router)
app.include_router(dashboard_router)
app.include_router(activity_router)
app.include_router(approval_router)
app.include_router(scheduler_router)
app.include_router(linkedin_router)
app.include_router(publishing_router)
app.include_router(profile_router)
app.include_router(settings_router)

# P0-1 — global error handlers (install before request handlers).
install_error_handlers(app)


# P0-2 — health endpoints.
# /live: process is up. No external dependencies.
# /ready: required dependencies (Mongo + Firebase) are reachable.
# /health: kept for backward compatibility — equivalent to /live.
@app.get("/live", include_in_schema=True)
async def live() -> dict[str, str]:
    return {"status": "alive"}


async def _ready_check() -> tuple[bool, dict[str, str]]:
    """Return (ok, details) for readiness."""
    details: dict[str, str] = {}
    ok = True
    try:
        await _mongo.ping_mongo()
        details["mongo"] = "ok"
    except Exception:
        details["mongo"] = "unavailable"
        ok = False
    try:
        _security.get_firebase_app()
        details["firebase"] = "ok"
    except Exception:
        details["firebase"] = "uninitialised"
        ok = False
    return ok, details


@app.get("/ready", include_in_schema=True)
async def ready() -> JSONResponse:
    ok, details = await _ready_check()
    status_code = 200 if ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if ok else "unready", **details},
    )


@app.get("/health", include_in_schema=True)
async def health() -> dict[str, str]:
    """Backward-compatible alias for /live. No external dependencies."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import os

    import uvicorn

    # Railway injects ``$PORT``; fall back to 8000 for local ``python -m``.
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)