"""Tests for Phase 8A P0-1 (error handler) + P0-2 (health endpoints)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_live_returns_200_without_deps(client_anon):
    """P0-2: /live must not depend on Mongo or Firebase."""
    response = client_anon.get("/live")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "alive"}


def test_health_alias_returns_200(client_anon):
    """Backward-compatible /health still returns 200 (no deps)."""
    response = client_anon.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_ready_returns_200_when_deps_ok(client_a):
    """P0-2: /ready returns 200 when Mongo ping + Firebase app are healthy."""
    response = client_a.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mongo"] == "ok"
    assert body["firebase"] == "ok"


def test_ready_returns_503_when_mongo_unavailable(client_a, monkeypatch):
    """P0-2: /ready returns 503 if Mongo ping fails."""
    from backend.app.db import mongo

    async def boom() -> None:
        raise RuntimeError("simulated mongo outage")

    monkeypatch.setattr(mongo, "ping_mongo", boom)
    response = client_a.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unready"
    assert body["mongo"] == "unavailable"


def test_ready_returns_503_when_firebase_not_initialised(client_a, monkeypatch):
    """P0-2: /ready returns 503 if Firebase app is missing."""
    from backend.app.core import security

    def boom():
        raise RuntimeError("firebase not initialised")

    monkeypatch.setattr(security, "get_firebase_app", boom)
    response = client_a.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["firebase"] == "uninitialised"


def test_unhandled_exception_returns_safe_envelope(client_a, monkeypatch):
    """P0-1: uncaught exceptions return a generic envelope without leaking str(exc)."""

    def boom(_self, _payload):
        raise RuntimeError(
            "SECRET-LLM-KEY=sk-THIS-MUST-NOT-LEAK api.linkedin.com response: <access_token>"
        )

    # Patch the unbound method on the class. FastAPI calls
    # ``WorkflowService().generate_content(payload)`` so ``self`` is injected.
    from backend.app.services import workflow_service

    monkeypatch.setattr(workflow_service.WorkflowService, "generate_content", boom)

    response = client_a.post(
        "/api/v1/content/generate",
        json={"topic": "test"},
    )
    assert response.status_code == 500
    body = response.json()
    assert "error" in body
    err = body["error"]
    assert err["code"] == "INTERNAL_SERVER_ERROR"
    assert err["message"] == "An unexpected error occurred."
    assert "request_id" in err and len(err["request_id"]) == 32
    # The leaked secret MUST NOT appear anywhere in the response.
    assert "SECRET-LLM-KEY" not in response.text
    assert "sk-THIS-MUST-NOT-LEAK" not in response.text
    assert "access_token" not in response.text


def test_http_exception_preserves_safe_detail(client_a):
    """P0-1: known HTTPException messages are preserved in the envelope."""
    response = client_a.post(
        "/api/v1/content/generate",
        json={"topic": ""},  # min_length=1 -> 422
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    # Pydantic message must appear; the secret must NOT.
    assert "request_id" in body["error"]
    assert "topic" in response.text


def test_unauthorized_uses_envelope(client_anon):
    """P0-1: 401 from get_current_user keeps the same envelope shape."""
    response = client_anon.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert "request_id" in body["error"]