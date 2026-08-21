"""Regression tests: LinkedIn OAuth flow compliance.

Confirms the application implements the documented
**server-side 3-legged Authorization Code Flow** for a confidential
LinkedIn app — and does NOT mix in PKCE parameters.

LinkedIn documents two distinct OAuth flows for third-party apps:

A. Standard 3-legged Authorization Code Flow (confidential server-side
   apps).
   - Authorize: GET https://www.linkedin.com/oauth/v2/authorization
   - Token:     POST https://www.linkedin.com/oauth/v2/accessToken
   - Token body MUST include:
       grant_type=authorization_code
       code=<auth code>
       client_id=<client id>
       client_secret=<client secret>
       redirect_uri=<callback URL>
   - Token body MUST NOT include:
       code_verifier
   - Authorize URL MUST NOT include:
       code_challenge
       code_challenge_method

B. Native PKCE Authorization Code Flow (mobile/desktop apps without
   a server-side secret).
   - Authorize: GET https://www.linkedin.com/oauth/native-pkce/authorization
   - Token body MUST include:
       code_verifier
   - Token body MUST NOT include:
       client_secret

References:
- https://learn.microsoft.com/en-us/linkedin/shared/authentication/
  authorization-code-flow
- https://learn.microsoft.com/en-us/linkedin/shared/authentication/
  authorization-code-flow-native
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient


# Documented authorize endpoint for standard 3-legged flow.
STD_AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
# Native PKCE uses a DIFFERENT endpoint — we must NOT hit this one.
NATIVE_PKCE_AUTHORIZE_URL = "https://www.linkedin.com/oauth/native-pkce/authorization"
# Same token endpoint for both flows.
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"


async def _seed_valid_state(state: str) -> None:
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
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc).replace(year=2099),
            "consumed": False,
        }
    )


def _install_fake_credentials(monkeypatch) -> None:
    """Inject fake LinkedIn credentials into os.environ and clear the
    Settings lru_cache so the new values are picked up."""
    import os

    os.environ["LINKEDIN_CLIENT_ID"] = "FAKE-CLIENT-ID-12345678"
    os.environ["LINKEDIN_CLIENT_SECRET"] = "FAKE-CLIENT-SECRET-VALUE"
    os.environ["LINKEDIN_REDIRECT_URI"] = (
        "https://linkedin-agent-production-fake.up.railway.app"
        "/api/v1/linkedin/callback"
    )

    from backend.app.core import config as config_mod

    if hasattr(config_mod.get_settings, "cache_clear"):
        config_mod.get_settings.cache_clear()


def test_authorize_url_hits_standard_3_legged_endpoint(client_a) -> None:
    """The application's /linkedin/connect must hit the documented
    STANDARD 3-legged authorize endpoint, NOT the native PKCE one."""
    response = client_a.get("/api/v1/linkedin/connect")
    assert response.status_code == 200
    url = response.json()["authorization_url"]
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    assert base == STD_AUTHORIZE_URL
    assert base != NATIVE_PKCE_AUTHORIZE_URL


def test_authorize_url_does_not_contain_pkce_parameters(client_a) -> None:
    """For a standard 3-legged flow the authorize URL MUST NOT carry
    PKCE parameters — those belong to the native PKCE flow only.

    Required params per LinkedIn docs:
        response_type, client_id, redirect_uri, scope, state

    Forbidden for standard 3-legged:
        code_challenge, code_challenge_method
    """
    response = client_a.get("/api/v1/linkedin/connect")
    assert response.status_code == 200
    url = response.json()["authorization_url"]
    params = parse_qs(urlparse(url).query)

    for required in ("response_type", "client_id", "redirect_uri",
                     "scope", "state"):
        assert required in params, (
            f"Standard 3-legged authorize URL is missing required "
            f"param {required!r}: got {sorted(params.keys())}"
        )

    for forbidden in ("code_challenge", "code_challenge_method"):
        assert forbidden not in params, (
            f"Authorize URL must NOT carry {forbidden!r} for a "
            f"standard 3-legged confidential server-side flow. "
            f"Got params: {sorted(params.keys())}"
        )


def test_token_request_carries_only_standard_3_legged_fields(
    monkeypatch, client_a
) -> None:
    """Reproduce the actual POST to /oauth/v2/accessToken and assert
    the EXACT body that LinkedIn receives.

    Required for standard 3-legged:
        grant_type, code, redirect_uri, client_id, client_secret

    Forbidden for standard 3-legged:
        code_verifier, code_challenge, code_challenge_method
    """
    captured: dict = {}

    async def fake_post(self, url, **_kwargs):
        captured["url"] = url
        captured["kwargs"] = _kwargs

        class _R:
            status_code = 200

            def json(self):
                return {
                    "access_token": "FAKE-ACCESS-TOKEN",
                    "refresh_token": "FAKE-REFRESH-TOKEN",
                    "expires_in": 3600,
                    "scope": (
                        "openid profile email w_member_social"
                    ),
                }

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    from backend.app.api.v1 import linkedin as linkedin_router
    from backend.app.repositories import linkedin_repository

    async def _upsert(self, **_kwargs):
        return None

    monkeypatch.setattr(
        linkedin_repository.LinkedInRepository, "upsert_tokens", _upsert
    )

    async def _stub_urn(_token):
        return None

    monkeypatch.setattr(linkedin_router, "_fetch_person_urn", _stub_urn)

    _install_fake_credentials(monkeypatch)
    asyncio.run(_seed_valid_state(state="std3-state-1111"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {"code": "FAKE-AUTH-CODE", "state": "std3-state-1111"}
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "linkedin=connected" in response.headers["location"]

    assert captured["url"] == TOKEN_URL

    body = captured["kwargs"]["data"]

    required = {
        "grant_type": "authorization_code",
        "code": "FAKE-AUTH-CODE",
        "redirect_uri": (
            "https://linkedin-agent-production-fake.up.railway.app"
            "/api/v1/linkedin/callback"
        ),
        "client_id": "FAKE-CLIENT-ID-12345678",
        "client_secret": "FAKE-CLIENT-SECRET-VALUE",
    }
    for key, expected in required.items():
        assert body[key] == expected, (
            f"Required field {key!r} missing or wrong in token body. "
            f"Got: {body.get(key)!r}, expected: {expected!r}"
        )

    for forbidden in ("code_verifier", "code_challenge",
                      "code_challenge_method"):
        assert forbidden not in body, (
            f"Forbidden field {forbidden!r} present in token body — "
            "the application has regressed to sending PKCE parameters "
            "to the standard 3-legged token endpoint. This is what "
            "LinkedIn rejects as invalid_client."
        )

    # Content-Type
    headers = captured["kwargs"]["headers"]
    assert headers.get("Accept") == "application/json"


def test_token_request_never_combines_client_secret_with_code_verifier(
    monkeypatch, client_a
) -> None:
    """Hard guard: the application must NEVER simultaneously include
    BOTH `client_secret` and `code_verifier` in the token body.

    This combination was the exact root cause of the production
    `invalid_client` failures between 2026-08-21 07:28 and 10:21:
    standard 3-legged endpoint receives `client_secret` (good) AND
    `code_verifier` (PKCE, mutually exclusive). LinkedIn rejects this
    hybrid as an unsupported flow. The fix is to send only the
    standard 3-legged set.

    This test asserts the invariant at the runtime request level so
    a regression cannot silently re-introduce the bug.
    """
    captured: dict = {}

    async def fake_post(self, url, **_kwargs):
        captured["kwargs"] = _kwargs

        class _R:
            status_code = 200

            def json(self):
                return {
                    "access_token": "FAKE-ACCESS-TOKEN",
                    "refresh_token": "FAKE-REFRESH-TOKEN",
                    "expires_in": 3600,
                    "scope": (
                        "openid profile email w_member_social"
                    ),
                }

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    from backend.app.api.v1 import linkedin as linkedin_router
    from backend.app.repositories import linkedin_repository

    async def _upsert(self, **_kwargs):
        return None

    monkeypatch.setattr(
        linkedin_repository.LinkedInRepository, "upsert_tokens", _upsert
    )

    async def _stub_urn(_token):
        return None

    monkeypatch.setattr(linkedin_router, "_fetch_person_urn", _stub_urn)

    _install_fake_credentials(monkeypatch)
    asyncio.run(_seed_valid_state(state="hybrid-guard-2222"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {"code": "FAKE-AUTH-CODE", "state": "hybrid-guard-2222"}
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    assert response.status_code == 303
    body = captured["kwargs"]["data"]

    assert "client_secret" in body
    assert "code_verifier" not in body, (
        "BUG: token body contains BOTH client_secret AND code_verifier. "
        "LinkedIn rejects this hybrid as invalid_client. "
        f"Body keys: {sorted(body.keys())}"
    )

    assert "code_challenge" not in body
    assert "code_challenge_method" not in body
