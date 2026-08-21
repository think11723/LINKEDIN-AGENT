"""Regression test for the LinkedIn token-exchange POST body shape.

The previous diagnostic audit (commit 8734a92) revealed that no
existing test asserted the actual request body sent to LinkedIn's
``/oauth/v2/accessToken`` endpoint. Every other test mocks the
response but never inspects what was sent.

This test intercepts the httpx call and verifies:

* the URL,
* the HTTP method,
* the form-urlencoded body contains the stripped credential values,
* whitespace / quotes / newlines that may have been introduced via
  copy-paste into the env-var UI are stripped before the request is
  built.

Fake credentials only — no real secrets.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from fastapi.testclient import TestClient


# Fake, fake, fake. None of these values belong to a real LinkedIn app.
FAKE_CLIENT_ID = "FAKE-CLIENT-ID-12345678"
FAKE_CLIENT_SECRET = "FAKE-CLIENT-SECRET-VALUE"
FAKE_REDIRECT_URI = (
    "https://linkedin-agent-production-fake.up.railway.app"
    "/api/v1/linkedin/callback"
)
FAKE_AUTH_CODE = "FAKE-AUTH-CODE-AAA"
FAKE_VERIFIER = "FAKE-PKCE-VERIFIER-BBB"


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
            "code_verifier": FAKE_VERIFIER,
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc).replace(year=2099),
            "consumed": False,
        }
    )


def _install_fake_credentials(monkeypatch) -> None:
    """Inject fake LinkedIn credentials into os.environ AND clear any
    cached Settings instance so the new values are picked up."""
    os.environ["LINKEDIN_CLIENT_ID"] = FAKE_CLIENT_ID
    os.environ["LINKEDIN_CLIENT_SECRET"] = FAKE_CLIENT_SECRET
    os.environ["LINKEDIN_REDIRECT_URI"] = FAKE_REDIRECT_URI

    # Clear the lru_cache on get_settings so Settings is re-built
    # from the freshly set env vars.
    from backend.app.core import config as config_mod

    if hasattr(config_mod.get_settings, "cache_clear"):
        config_mod.get_settings.cache_clear()


def test_token_exchange_post_body_shape(monkeypatch) -> None:
    """The token-exchange POST must hit the documented LinkedIn
    endpoint, use POST, and contain the stripped credential values in
    a form-urlencoded body."""

    captured: dict = {}

    async def fake_post(self, url, **_kwargs):
        captured["url"] = url
        captured["kwargs"] = _kwargs
        captured["method"] = "POST"

        class _R:
            status_code = 200

            def json(self):
                return {
                    "access_token": "FAKE-ACCESS-TOKEN",
                    "refresh_token": "FAKE-REFRESH-TOKEN",
                    "expires_in": 3600,
                    "scope": "openid profile email w_member_social",
                }

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    # Stub the linkedin repository + person-urn lookup so the success
    # path can complete without further network calls.
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
    asyncio.run(_seed_valid_state(state="shape-state-1111"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {"code": FAKE_AUTH_CODE, "state": "shape-state-1111"}
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "linkedin=connected" in response.headers["location"]

    # 1. URL must be the documented LinkedIn token endpoint.
    assert captured["url"] == "https://www.linkedin.com/oauth/v2/accessToken"

    # 2. Method must be POST.
    assert captured["method"] == "POST"

    # 3. Body must be a form-urlencoded dict (httpx serializes `data=`).
    assert "data" in captured["kwargs"]
    body = captured["kwargs"]["data"]

    assert body["grant_type"] == "authorization_code"
    assert body["code"] == FAKE_AUTH_CODE
    assert body["redirect_uri"] == FAKE_REDIRECT_URI
    assert body["client_id"] == FAKE_CLIENT_ID
    assert body["client_secret"] == FAKE_CLIENT_SECRET
    assert body["code_verifier"] == FAKE_VERIFIER

    # 4. Headers must include Accept: application/json.
    assert "headers" in captured["kwargs"]
    assert captured["kwargs"]["headers"]["Accept"] == "application/json"


def test_token_exchange_strips_whitespace_in_credentials(monkeypatch) -> None:
    """If the Railway env-var UI smuggles a leading newline, a trailing
    space, or surrounding whitespace into the credential value, the
    request body must contain the stripped value — not the raw one.
    This is the P0-9 hardening.

    Note: ``str.strip()`` only strips whitespace characters (spaces,
    tabs, newlines, carriage returns). Surrounding double-quotes are
    not whitespace and remain in the value. The diagnostic
    ``_credential_shape`` helper reports the anomaly so the operator
    can see and remove the quote manually. This test proves the
    whitespace-stripping half of P0-9."""

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
                    "scope": "openid profile email w_member_social",
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

    # Inject credentials with leading whitespace, trailing newline,
    # and embedded tab — the classic copy-paste-into-Railway-UI
    # pattern.
    os.environ["LINKEDIN_CLIENT_ID"] = "\n  FAKE-CLIENT-ID-WITH-JUNK  \n"
    os.environ["LINKEDIN_CLIENT_SECRET"] = (
        "\tFAKE-CLIENT-SECRET-WITH-JUNK\t\n"
    )
    os.environ["LINKEDIN_REDIRECT_URI"] = FAKE_REDIRECT_URI

    from backend.app.core import config as config_mod

    if hasattr(config_mod.get_settings, "cache_clear"):
        config_mod.get_settings.cache_clear()

    asyncio.run(_seed_valid_state(state="strip-state-2222"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {"code": FAKE_AUTH_CODE, "state": "strip-state-2222"}
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    assert response.status_code == 303
    body = captured["kwargs"]["data"]
    # The stripped values must be what is sent.
    assert body["client_id"] == "FAKE-CLIENT-ID-WITH-JUNK"
    assert body["client_secret"] == "FAKE-CLIENT-SECRET-WITH-JUNK"
    # And the raw whitespace junk must NOT appear.
    assert "\n" not in body["client_id"]
    assert "  " not in body["client_id"]
    assert "\n" not in body["client_secret"]
    assert "\t" not in body["client_secret"]


def test_token_exchange_uses_same_client_id_as_authorize(
    monkeypatch, client_a
) -> None:
    """The authorization URL and the token-exchange request must use
    the EXACT same client_id. This proves there is no second config
    object, no hard-coded value, and no stale constant."""

    from backend.app.core import config as config_mod

    if hasattr(config_mod.get_settings, "cache_clear"):
        config_mod.get_settings.cache_clear()

    captured: dict = {"authorize_client_id": None, "token_client_id": None}

    import httpx

    original_post = httpx.AsyncClient.post

    async def fake_post(self, url, **_kwargs):
        if "accessToken" in url:
            captured["token_client_id"] = _kwargs["data"]["client_id"]

            class _R:
                status_code = 200

                def json(self):
                    return {
                        "access_token": "FAKE-ACCESS-TOKEN",
                        "refresh_token": "FAKE-REFRESH-TOKEN",
                        "expires_in": 3600,
                        "scope": "openid profile email w_member_social",
                    }

            return _R()
        return await original_post(self, url, **_kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    _install_fake_credentials(monkeypatch)

    # Stub the linkedin repository + person-urn lookup so the success
    # path can complete without further network calls.
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

    asyncio.run(_seed_valid_state(state="consistency-state-3333"))

    # /connect requires Firebase auth, so we use the authed client_a.
    # Trigger /connect to capture the authorize-URL client_id.
    connect_resp = client_a.get("/api/v1/linkedin/connect")
    assert connect_resp.status_code == 200
    authorize_url = connect_resp.json()["authorization_url"]
    from urllib.parse import parse_qs, urlparse

    qs = parse_qs(urlparse(authorize_url).query)
    captured["authorize_client_id"] = qs["client_id"][0]

    # Trigger /callback to capture the token-exchange client_id.
    params = {"code": FAKE_AUTH_CODE, "state": "consistency-state-3333"}
    cb_resp = client_a.get(
        "/api/v1/linkedin/callback",
        params=params,
        follow_redirects=False,
    )
    assert cb_resp.status_code == 303

    assert captured["authorize_client_id"] == FAKE_CLIENT_ID
    assert captured["token_client_id"] == FAKE_CLIENT_ID
    assert captured["authorize_client_id"] == captured["token_client_id"]


def test_credential_shape_helper_detects_whitespace() -> None:
    """The diagnostic helper must report had_whitespace / had_newline
    accurately so the audit log proves whether an invalid_client was
    caused by env-var corruption."""
    from backend.app.api.v1.linkedin import _credential_shape

    # Clean value — nothing to report.
    clean = _credential_shape("abcd1234")
    assert clean["configured"] is True
    assert clean["length"] == 8
    assert clean["raw_length"] == 8
    assert clean["had_whitespace"] is False
    assert clean["had_newline"] is False
    assert clean["had_unusual_chars"] is False
    assert clean["fingerprint_sha256_16"] is not None

    # Trailing newline + leading space — classic paste artefact.
    dirty = _credential_shape("\n  abcd1234\n")
    assert dirty["configured"] is True
    assert dirty["length"] == 8
    # raw = 1 (\n) + 2 (spaces) + 8 (chars) + 1 (\n) = 12
    assert dirty["raw_length"] == 12
    assert dirty["had_whitespace"] is True
    assert dirty["had_newline"] is True

    # Empty / unset value.
    empty = _credential_shape("")
    assert empty["configured"] is False
    assert empty["length"] == 0
    assert empty["had_whitespace"] is False
    assert empty["had_newline"] is False
    assert empty["fingerprint_sha256_16"] is None


def test_credential_normalization_handles_common_paste_corruption() -> None:
    """The defensive normalization must strip every common kind of
    paste corruption so a single anomaly does not reach LinkedIn's
    /oauth/v2/accessToken and produce invalid_client."""
    from backend.app.api.v1.linkedin import (
        _credential_fingerprint,
        _credential_shape,
    )

    clean_value = "FAKE-LINKEDIN-SECRET-VALUE"
    clean_fp = _credential_fingerprint(clean_value)

    # Every one of these corruptions must normalize to the same
    # fingerprint as the clean value — i.e. the request body sent
    # to LinkedIn would be identical.
    #
    # We use ``\uXXXX`` escapes so the test does not depend on the
    # source file preserving invisible Unicode characters through
    # copy-paste.
    corruptions = [
        ('whitespace', '  FAKE-LINKEDIN-SECRET-VALUE  '),
        ('newline', 'FAKE-LINKEDIN-SECRET-VALUE\n'),
        ('cr-lf', 'FAKE-LINKEDIN-SECRET-VALUE\r\n'),
        ('dquotes', '"FAKE-LINKEDIN-SECRET-VALUE"'),
        ('squotes', "'FAKE-LINKEDIN-SECRET-VALUE'"),
        ('backticks', '`FAKE-LINKEDIN-SECRET-VALUE`'),
        ('bom', '﻿FAKE-LINKEDIN-SECRET-VALUE'),
        ('zwsp', '​FAKE-LINKEDIN-SECRET-VALUE​'),
        ('zwnj', '‌FAKE-LINKEDIN-SECRET-VALUE‌'),
        ('zwj', '‍FAKE-LINKEDIN-SECRET-VALUE‍'),
        ('lrm', '‎FAKE-LINKEDIN-SECRET-VALUE‎'),
        ('rlm', '‏FAKE-LINKEDIN-SECRET-VALUE‏'),
        ('dquote+bom', '﻿"FAKE-LINKEDIN-SECRET-VALUE"﻿'),
        ('dquote+ws', '  "FAKE-LINKEDIN-SECRET-VALUE"  '),
    ]

    for name, dirty in corruptions:
        shape = _credential_shape(dirty)
        assert shape["fingerprint_sha256_16"] == clean_fp, (
            f"{name}: fingerprint mismatch — {dirty!r} did not "
            f"normalize to clean fingerprint {clean_fp}; got "
            f"{shape['fingerprint_sha256_16']}"
        )
        # Either the whitespace flag OR the unusual-chars flag
        # must be raised — the operator needs SOME signal that
        # the env var value was not pristine. Whitespace-only
        # corruptions raise ``had_whitespace``; non-whitespace
        # corruptions raise ``had_unusual_chars``.
        assert shape["had_whitespace"] or shape["had_unusual_chars"], (
            f"{name}: neither had_whitespace nor had_unusual_chars "
            f"was raised — diagnostic will silently hide the "
            f"corruption"
        )


def test_token_exchange_strips_non_whitespace_paste_corruption(
    monkeypatch, client_a
) -> None:
    """The full OAuth callback path must strip non-whitespace paste
    corruption from the env-var credential BEFORE sending the POST
    body to LinkedIn. Without this, BOM / zero-width / quote
    corruption would survive ``str.strip()`` and produce
    ``invalid_client``."""

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
                    "scope": "openid profile email w_member_social",
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

    # Inject credentials with the worst-case paste corruption: a BOM,
    # surrounding double-quotes, and zero-width characters. This
    # pattern is exactly what happens when a secret is copy-pasted
    # from a webpage or a notes app into the Railway UI.
    raw_secret = (
        '﻿"‍‎FAKE-LINKEDIN-SECRET-CORRUPTED‎‍"﻿'
    )
    os.environ["LINKEDIN_CLIENT_ID"] = "FAKE-CLIENT-ID-CORRUPTED"
    os.environ["LINKEDIN_CLIENT_SECRET"] = raw_secret
    os.environ["LINKEDIN_REDIRECT_URI"] = FAKE_REDIRECT_URI

    from backend.app.core import config as config_mod

    if hasattr(config_mod.get_settings, "cache_clear"):
        config_mod.get_settings.cache_clear()

    asyncio.run(_seed_valid_state(state="corrupt-state-4444"))

    import backend.app.main

    with TestClient(backend.app.main.app) as client:
        params = {"code": FAKE_AUTH_CODE, "state": "corrupt-state-4444"}
        response = client.get(
            "/api/v1/linkedin/callback",
            params=params,
            follow_redirects=False,
        )

    assert response.status_code == 303
    body = captured["kwargs"]["data"]

    # The request body must contain the CLEAN values — no BOM,
    # no quotes, no zero-width chars.
    assert body["client_secret"] == "FAKE-LINKEDIN-SECRET-CORRUPTED"
    assert body["client_id"] == "FAKE-CLIENT-ID-CORRUPTED"
    assert "﻿" not in body["client_secret"]
    assert '"' not in body["client_secret"]
    assert "‍" not in body["client_secret"]
    assert "‎" not in body["client_secret"]
