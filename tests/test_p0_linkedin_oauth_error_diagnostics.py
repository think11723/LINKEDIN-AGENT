"""Regression test for LinkedIn token-exchange failure diagnostics.

Verifies that when LinkedIn's ``/oauth/v2/accessToken`` endpoint
returns a non-200 response, the backend:

* surfaces the safe OAuth-standard fields (``error``,
  ``error_description``, ``error_uri``) in the audit log,
* surfaces the safe ``error`` code in the redirect query string as a
  ``detail`` parameter so the SPA can show the real reason,
* NEVER records or returns secrets, tokens, authorization codes, PKCE
  verifiers, or Authorization headers,
* still falls back gracefully if LinkedIn returns a non-JSON body.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient


# Fragments that must NEVER appear in the audit log or in the redirect
# query string when a non-200 token response is processed.
SENSITIVE_FRAGMENTS = (
    "FAKE-CLIENT-SECRET",
    "FAKE-ACCESS-TOKEN",
    "FAKE-REFRESH-TOKEN",
    "FAKE-AUTH-CODE-9876",
    "FAKE-PKCE-VERIFIER-1234567890",
    "Bearer FAKE-BEARER-TOKEN",
    "Basic FAKE-BASIC-AUTH",
)


async def _seed_valid_state(state: str = "diagnostic-state-1234") -> None:
    from backend.app.db.mongo import get_database
    from backend.app.repositories.oauth_state_repository import (
        OAuthStateRepository,
    )

    repo = OAuthStateRepository(get_database())
    await repo.col.insert_one(
        {
            "_id": state,
            "state": state,
            "user_id": "USER_A",
            "code_verifier": "FAKE-PKCE-VERIFIER-1234567890",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc).replace(year=2099),
            "consumed": False,
        }
    )


def _make_fake_response(status_code: int, json_body: dict) -> object:
    class _FakeResponse:
        pass

    resp = _FakeResponse()
    resp.status_code = status_code
    resp.text = ""

    def _json() -> dict:
        return json_body

    resp.json = _json  # type: ignore[attr-defined]
    return resp


def test_token_exchange_failure_records_safe_oauth_error(
    monkeypatch,
) -> None:
    """A non-200 LinkedIn token response containing the OAuth-standard
    ``invalid_client`` payload must land in the audit log without any
    secret/token/code leakage."""
    from backend.app.repositories import audit_repository

    captured: list[dict] = []

    async def _capture(self, **_kwargs):
        captured.append(_kwargs)

    monkeypatch.setattr(audit_repository.AuditRepository, "log", _capture)

    import httpx

    async def fake_post(*_args, **_kwargs):
        return _make_fake_response(
            401,
            {
                "error": "invalid_client",
                "error_description": "Client authentication failed",
                "error_uri": "https://docs.linkedin.com/auth",
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    asyncio.run(_seed_valid_state())

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {
            "code": "FAKE-AUTH-CODE-9876",
            "state": "diagnostic-state-1234",
        }
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    # 303 redirect to the SPA with both reason and detail.
    assert response.status_code == 303
    location = response.headers["location"]
    assert "linkedin=error" in location
    assert "reason=token_exchange" in location
    assert "detail=invalid_client" in location

    # The audit row must contain the safe diagnostic fields.
    failed = [
        c
        for c in captured
        if c.get("event_type") == "LINKEDIN_CONNECT_FAILED"
    ]
    assert failed, "Expected a LINKEDIN_CONNECT_FAILED audit row."
    details = failed[-1]["details"]
    assert details["status"] == 401
    assert details["error"] == "invalid_client"
    assert details["error_description"] == "Client authentication failed"
    assert details["error_uri"] == "https://docs.linkedin.com/auth"

    # None of the sensitive fragments may appear in either the audit
    # row or the redirect Location.
    serialized = str(captured) + " " + location
    for frag in SENSITIVE_FRAGMENTS:
        assert frag not in serialized, (
            f"Sensitive fragment {frag!r} leaked into diagnostics."
        )


def test_token_exchange_failure_handles_non_json_body(monkeypatch) -> None:
    """LinkedIn occasionally returns a non-JSON error body. The
    diagnostic path must still record the status code and NOT crash."""
    from backend.app.repositories import audit_repository

    captured: list[dict] = []

    async def _capture(self, **_kwargs):
        captured.append(_kwargs)

    monkeypatch.setattr(audit_repository.AuditRepository, "log", _capture)

    import httpx

    class _BadJsonResponse:
        status_code = 502

        def json(self):
            raise ValueError("invalid json")

    async def fake_post(*_args, **_kwargs):
        return _BadJsonResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    asyncio.run(_seed_valid_state(state="non-json-state-5678"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {
            "code": "FAKE-AUTH-CODE-9876",
            "state": "non-json-state-5678",
        }
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "reason=token_exchange" in location
    # No ``detail`` is added when we cannot parse the body.
    assert "detail=" not in location

    failed = [
        c
        for c in captured
        if c.get("event_type") == "LINKEDIN_CONNECT_FAILED"
    ]
    assert failed
    details = failed[-1]["details"]
    assert details["status"] == 502
    assert "error" not in details
    assert "error_description" not in details
    assert "error_uri" not in details


def test_token_exchange_failure_sanitises_hostile_error_payload(
    monkeypatch,
) -> None:
    """A malicious or buggy error payload containing control characters
    must be sanitised before reaching the audit row and the redirect
    Location so it cannot smuggle log-injection or URL-injection
    content."""
    from backend.app.repositories import audit_repository

    captured: list[dict] = []

    async def _capture(self, **_kwargs):
        captured.append(_kwargs)

    monkeypatch.setattr(audit_repository.AuditRepository, "log", _capture)

    import httpx

    async def fake_post(*_args, **_kwargs):
        return _make_fake_response(
            400,
            {
                # newline + carriage return in error_description;
                # control chars + shell metacharacters in error.
                "error": "invalid_request\r\n; rm -rf /; echo pwned",
                "error_description": (
                    "boom\nshell-injection-attempt&code=evil"
                ),
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    asyncio.run(_seed_valid_state(state="sanitise-state-9999"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {
            "code": "FAKE-AUTH-CODE-9876",
            "state": "sanitise-state-9999",
        }
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    location = response.headers["location"]
    assert "reason=token_exchange" in location

    failed = [
        c
        for c in captured
        if c.get("event_type") == "LINKEDIN_CONNECT_FAILED"
    ]
    assert failed
    details = failed[-1]["details"]

    # Control characters must NEVER appear in the audit row or the
    # redirect Location — they are the realistic log-injection vector.
    serialized = str(details) + " " + location
    assert "\n" not in serialized
    assert "\r" not in serialized
    assert ";" not in serialized
    # The cleaned ``error`` value is short, ASCII-alphanumeric, and
    # still ends up in both the audit row and the redirect ``detail``
    # parameter (URL-encoded by urllib.parse.quote with safe="").
    assert "invalid_request" in details["error"]
    assert "detail=invalid_request" in location
    # None of the sensitive fragments may appear in either the audit
    # row or the redirect Location.
    for frag in SENSITIVE_FRAGMENTS:
        assert frag not in serialized, (
            f"Sensitive fragment {frag!r} leaked into diagnostics."
        )


def test_token_exchange_success_does_not_record_failure(monkeypatch) -> None:
    """Sanity: a 200 response must NOT take the diagnostic-error path."""
    from backend.app.repositories import audit_repository

    captured: list[dict] = []

    async def _capture(self, **_kwargs):
        captured.append(_kwargs)

    monkeypatch.setattr(audit_repository.AuditRepository, "log", _capture)

    import httpx

    async def fake_post(*_args, **_kwargs):
        return _make_fake_response(
            200,
            {
                "access_token": "FAKE-ACCESS-TOKEN",
                "refresh_token": "FAKE-REFRESH-TOKEN",
                "expires_in": 3600,
                "scope": "openid profile email w_member_social",
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    # Stub linkedin repository upsert + person-urn fetch so the
    # success path can complete without network calls.
    from backend.app.api.v1 import linkedin as linkedin_router
    from backend.app.repositories import linkedin_repository

    async def _upsert(self, **_kwargs):
        return None

    monkeypatch.setattr(
        linkedin_repository.LinkedInRepository, "upsert_tokens", _upsert
    )

    async def _stub_urn(_access_token):
        return None

    monkeypatch.setattr(linkedin_router, "_fetch_person_urn", _stub_urn)

    asyncio.run(_seed_valid_state(state="success-state-0000"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {
            "code": "FAKE-AUTH-CODE-9876",
            "state": "success-state-0000",
        }
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    assert response.status_code == 303
    location = response.headers["location"]
    assert "linkedin=connected" in location
    # No diagnostic failure row was logged.
    failed = [
        c
        for c in captured
        if c.get("event_type") == "LINKEDIN_CONNECT_FAILED"
    ]
    assert not failed, f"Unexpected failure audit row: {failed}"
