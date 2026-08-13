"""Tests for Phase 8A P0-8: LinkedIn log hygiene.

These tests prove the LinkedIn code paths DO NOT log response bodies,
tokens, or other sensitive material. They inspect log records via
pytest's ``caplog`` fixture.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import pytest


SENSITIVE_FRAGMENTS = (
    "access_token=ACCESS",
    "refresh_token=REFRESH",
    "Bearer SECRET-BEARER",
    "client_secret=SECRET",
    "<SECRET_RESPONSE_BODY>",
    "code=OAUTH-CODE-12345",
)


def _has_sensitive(caplog) -> bool:
    text = " ".join(rec.getMessage() for rec in caplog.records)
    return any(frag in text for frag in SENSITIVE_FRAGMENTS)


# ----- backend/app/api/v1/linkedin.py: token exchange failure logging -----


def test_linkedin_callback_does_not_log_response_body_on_token_failure(monkeypatch, caplog):
    """The /linkedin/callback handler must NOT log LinkedIn response body
    when the token exchange fails (which is the path P0-8 flagged).
    """
    from backend.app.api.v1 import linkedin as linkedin_router

    class _FakeResponse:
        status_code = 400
        text = (
            '{"error":"invalid_grant","access_token=ACCESS","refresh_token=REFRESH",'
            '"client_secret=SECRET","code=OAUTH-CODE-12345"}'
        )

    async def fake_post(*_args, **_kwargs):
        return _FakeResponse()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    # We need a valid state row in oauth_states first. Use the repository.
    from backend.app.db.mongo import get_database
    from backend.app.repositories.oauth_state_repository import OAuthStateRepository

    async def _seed_state():
        repo = OAuthStateRepository(get_database())
        # Insert a state directly to bypass the connect flow.
        await repo.col.insert_one(
            {
                "_id": "test-state-1234",
                "state": "test-state-1234",
                "user_id": "USER_A",
                "code_verifier": "v",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc),
                "consumed": False,
            }
        )

    asyncio.run(_seed_state())

    # Stub the audit log + LinkedIn repository so the route can complete.
    from backend.app.repositories import linkedin_repository
    from backend.app.repositories import audit_repository

    async def _noop(self, **_kw):
        return None

    async def _upsert(self, **_kw):
        return None

    monkeypatch.setattr(audit_repository.AuditRepository, "log", _noop)

    # Use the actual route via TestClient.
    from fastapi.testclient import TestClient
    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        with caplog.at_level(logging.WARNING):
            response = client.get(
                "/api/v1/linkedin/callback",
                params={"code": "fake", "state": "test-state-1234"},
            )
    assert response.status_code in (400, 502)  # 400 invalid state, 502 exchange fail
    # Most importantly, no sensitive fragment must appear in the captured log.
    assert not _has_sensitive(caplog), (
        "LinkedIn callback log path leaked a sensitive fragment. "
        f"Captured: {[r.getMessage() for r in caplog.records]}"
    )


# ----- backend/app/services/scheduler_runner.py: publish failure logging -----


def test_scheduler_runner_does_not_log_publish_response_body(monkeypatch, caplog):
    """The runner must log the publish-failure status only, never the body."""
    from backend.app.services import scheduler_runner as runner_mod
    from backend.app.db.mongo import get_database
    from backend.app.repositories.scheduler_repository import SchedulerRepository

    class _FakeResponse:
        status_code = 500
        text = (
            '{"error":"server_error","access_token=ACCESS",'
            '"refresh_token=REFRESH","<SECRET_RESPONSE_BODY>"}'
        )

    async def _seed_and_dispatch():
        repo = SchedulerRepository(get_database())
        now = datetime.now(timezone.utc)
        await repo.col.insert_one(
            {
                "_id": "job-secret",
                "user_id": "USER_A",
                "title": "T",
                "content": "C",
                "hashtags": [],
                "image_path": None,
                "scheduled_time": now,
                "status": "pending",
                "retry_count": 0,
                "max_retries": 1,
                "created_at": now,
                "updated_at": now,
            }
        )

    asyncio_run = asyncio.run

    # Patch the access-token lookup so the runner has something to use.
    from backend.app.repositories import linkedin_repository

    async def _stub_tokens(self, user_id):
        return {
            "access_token": "FAKE_BEARER",
            "refresh_token": "REFRESH",
            "expires_at": None,
            "scope": None,
            "person_urn": None,
        }

    monkeypatch.setattr(
        linkedin_repository.LinkedInRepository,
        "get_decrypted_tokens",
        _stub_tokens,
    )

    # Patch httpx post to return our fake body.
    import httpx

    async def fake_post(*_a, **_kw):
        return _FakeResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    # Seed a job that is due.
    asyncio_run(_seed_and_dispatch())

    # Run a single tick.
    with caplog.at_level(logging.WARNING):
        asyncio_run(runner_mod.SchedulerRunner(poll_interval=0.001)._tick())

    # Allow the runner to retry up to max_retries=1 and fail.
    assert not _has_sensitive(caplog), (
        "Scheduler runner log path leaked a sensitive fragment. "
        f"Captured: {[r.getMessage() for r in caplog.records]}"
    )


# ----- static check: no .text / response body in any LinkedIn log call -----


def test_no_linkedin_log_uses_response_text():
    """Static check: no ``logger.*`` call inside the LinkedIn router or
    scheduler runner logs ``response.text`` (which can contain tokens).
    """
    import re

    for path in (
        "backend/app/api/v1/linkedin.py",
        "backend/app/services/scheduler_runner.py",
    ):
        with open(path, "r", encoding="utf-8") as f:
            contents = f.read()
        # Match logger.<level>(...) or logger.<level>(f"...").
        # Search for any logger call that references ``response.text``
        # or ``token_response.text`` inside the call.
        for m in re.finditer(r"logger\.\w+\([^)]*response\.text", contents):
            # Skip docstrings / comments by stripping leading whitespace.
            line_start = contents.rfind("\n", 0, m.start()) + 1
            line = contents[line_start : contents.find("\n", m.start())]
            assert not line.lstrip().startswith("#"), (
                f"{path} contains a commented-out response.text log call."
            )
            raise AssertionError(
                f"{path} has a logger call that logs response.text: {line.strip()!r}"
            )