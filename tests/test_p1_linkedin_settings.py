"""Phase 8B P1-1 — LinkedIn settings UI backend tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.app.db.mongo import get_database


def _seed_linkedin(user_id: str = "USER_A") -> None:
    from cryptography.fernet import Fernet
    import os

    fernet = Fernet(os.environ["LINKEDIN_TOKEN_ENCRYPTION_KEY"].encode())

    async def _seed():
        db = get_database()
        await db["linkedin_accounts"].update_one(
            {"_id": user_id},
            {
                "$set": {
                    "access_token_enc": fernet.encrypt(b"FAKE_TOKEN"),
                    "refresh_token_enc": fernet.encrypt(b"FAKE_REFRESH"),
                    "expires_at": datetime.now(timezone.utc),
                    "scope": "openid profile email w_member_social",
                    "person_urn": "urn:li:person:USER_A_URN",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    asyncio.run(_seed())


def test_status_returns_connected_when_seeded(client_a):
    _seed_linkedin()
    response = client_a.get("/api/v1/linkedin/status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is True
    assert body["person_urn"] == "urn:li:person:USER_A_URN"


def test_status_returns_disconnected_when_no_row(client_a):
    response = client_a.get("/api/v1/linkedin/status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["person_urn"] is None


def test_disconnect_removes_row(client_a):
    _seed_linkedin()
    response = client_a.post("/api/v1/linkedin/disconnect")
    assert response.status_code == 200
    assert response.json() == {"connected": False}

    # Status now disconnected.
    status_resp = client_a.get("/api/v1/linkedin/status")
    assert status_resp.json()["connected"] is False


def test_disconnect_cross_user_does_not_affect_other(client_a, client_b):
    _seed_linkedin("USER_A")
    response_b = client_b.post("/api/v1/linkedin/disconnect")
    assert response_b.status_code == 200

    # A still connected.
    status_a = client_a.get("/api/v1/linkedin/status")
    assert status_a.json()["connected"] is True


def test_disconnect_writes_audit_event(client_a):
    _seed_linkedin()
    client_a.post("/api/v1/linkedin/disconnect")

    async def _load():
        db = get_database()
        cursor = db["audit_events"].find(
            {"user_id": "USER_A", "event_type": "LINKEDIN_DISCONNECTED"}
        )
        return [doc async for doc in cursor]

    events = asyncio.run(_load())
    assert len(events) == 1


def test_status_response_never_includes_tokens(client_a):
    _seed_linkedin()
    response = client_a.get("/api/v1/linkedin/status")
    text = response.text
    # Plain-text search for forbidden material.
    assert "FAKE_TOKEN" not in text
    assert "FAKE_REFRESH" not in text
    assert "access_token" not in text
    assert "refresh_token" not in text
