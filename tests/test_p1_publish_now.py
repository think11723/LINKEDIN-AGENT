"""Phase 8B P1-9 — publish-now endpoint tests."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import pytest


def _seed_linkedin_token(user_id: str = "USER_A") -> None:
    """Helper: insert a fake LinkedIn account row with Fernet-encrypted tokens."""
    from cryptography.fernet import Fernet
    import os

    from backend.app.db.mongo import get_database

    fernet = Fernet(os.environ["LINKEDIN_TOKEN_ENCRYPTION_KEY"].encode())

    async def _insert():
        db = get_database()
        await db["linkedin_accounts"].update_one(
            {"_id": user_id},
            {
                "$set": {
                    "access_token_enc": fernet.encrypt(b"FAKE_TOKEN"),
                    "refresh_token_enc": fernet.encrypt(b"FAKE_REFRESH"),
                    "expires_at": datetime.now(timezone.utc),
                    "scope": "openid profile email w_member_social",
                    "person_urn": "urn:li:person:FAKE_URN",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    asyncio.run(_insert())


def test_publish_now_anonymous_returns_401(client_anon):
    response = client_anon.post("/api/v1/drafts/some-draft-id/publish")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_publish_now_404_cross_user(client_a, client_b):
    """USER_B cannot publish USER_A's draft."""
    create_a = client_a.post(
        "/api/v1/drafts",
        json={"topic": "iso", "title": "A", "content": "x"},
    )
    assert create_a.status_code == 201
    draft_id = create_a.json()["draft_id"]

    response = client_b.post(f"/api/v1/drafts/{draft_id}/publish")
    assert response.status_code == 404


def test_publish_now_400_when_linkedin_not_connected(client_a):
    """No tokens in linkedin_accounts → 400."""
    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "no-linkedin", "title": "T", "content": "x"},
    )
    assert create.status_code == 201
    draft_id = create.json()["draft_id"]

    response = client_a.post(f"/api/v1/drafts/{draft_id}/publish")
    assert response.status_code == 400
    body = response.json()
    assert "LinkedIn" in body["error"]["message"]


def test_publish_now_200_idempotent(client_a, monkeypatch):
    """Publishing twice: 200 both times. Second call returns already_published=true."""
    _seed_linkedin_token()
    import httpx

    class _R:
        status_code = 201

        def json(self):
            return {"id": "urn:li:ugcPost:1234"}

    async def fake_post(*_a, **_kw):
        return _R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    create = client_a.post(
        "/api/v1/drafts", json={"topic": "twice", "title": "T", "content": "x"}
    )
    draft_id = create.json()["draft_id"]

    first = client_a.post(f"/api/v1/drafts/{draft_id}/publish")
    assert first.status_code == 200
    assert first.json()["linkedin_post_id"] == "urn:li:ugcPost:1234"
    assert first.json()["already_published"] is False

    second = client_a.post(f"/api/v1/drafts/{draft_id}/publish")
    assert second.status_code == 200
    assert second.json()["already_published"] is True
    assert second.json()["linkedin_post_id"] == "urn:li:ugcPost:1234"


def test_publish_now_200_with_linkedin_stub(client_a, monkeypatch):
    _seed_linkedin_token()
    import httpx

    class _R:
        status_code = 201

        def json(self):
            return {"id": "urn:li:ugcPost:9999"}

    async def fake_post(*_a, **_kw):
        return _R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "happy", "title": "H", "content": "world", "hashtags": ["#t"]},
    )
    draft_id = create.json()["draft_id"]

    response = client_a.post(f"/api/v1/drafts/{draft_id}/publish")
    assert response.status_code == 200
    body = response.json()
    assert body["linkedin_post_id"] == "urn:li:ugcPost:9999"
    assert body["already_published"] is False
    assert body["published_at"]  # ISO-8601 string


def test_publish_now_logs_draft_published_audit_event(client_a, monkeypatch):
    _seed_linkedin_token()
    import httpx

    class _R:
        status_code = 201

        def json(self):
            return {"id": "urn:li:ugcPost:audit"}

    async def fake_post(*_a, **_kw):
        return _R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    create = client_a.post(
        "/api/v1/drafts", json={"topic": "audit", "title": "A", "content": "x"}
    )
    draft_id = create.json()["draft_id"]
    client_a.post(f"/api/v1/drafts/{draft_id}/publish")

    from backend.app.db.mongo import get_database
    db = get_database()

    async def _load():
        cursor = db["audit_events"].find({"user_id": "USER_A", "event_type": "DRAFT_PUBLISHED_NOW"})
        return [doc async for doc in cursor]

    events = asyncio.run(_load())
    assert any(e.get("details", {}).get("draft_id") == draft_id for e in events)


def test_publish_now_400_on_linkedin_5xx(client_a, monkeypatch):
    _seed_linkedin_token()
    import httpx

    class _R:
        status_code = 500
        text = '{"error":"server"}'

    async def fake_post(*_a, **_kw):
        return _R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    create = client_a.post(
        "/api/v1/drafts", json={"topic": "fail", "title": "F", "content": "x"}
    )
    draft_id = create.json()["draft_id"]
    response = client_a.post(f"/api/v1/drafts/{draft_id}/publish")
    assert response.status_code == 400
    body = response.json()
    assert "500" in body["error"]["message"] or "LinkedIn" in body["error"]["message"]


def test_publish_now_does_not_leak_linkedin_response_body(client_a, monkeypatch, caplog):
    """P0-8 hygiene: a LinkedIn 5xx response body must NOT appear in logs."""
    _seed_linkedin_token()
    import httpx

    class _R:
        status_code = 500
        text = '{"secret":"<LEAKED_BODY>"}'

    async def fake_post(*_a, **_kw):
        return _R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    create = client_a.post(
        "/api/v1/drafts", json={"topic": "leak", "title": "L", "content": "x"}
    )
    draft_id = create.json()["draft_id"]

    with caplog.at_level(logging.WARNING):
        response = client_a.post(f"/api/v1/drafts/{draft_id}/publish")

    assert response.status_code == 400
    assert "LEAKED_BODY" not in caplog.text