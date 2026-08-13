"""Phase 8B P1-11 — server-side settings tests."""

from __future__ import annotations

from datetime import datetime, timezone


def _seed_user_with_linkedin(user_id: str = "USER_A") -> None:
    """Seed the ``linkedin_accounts`` collection (not the user document)."""
    from backend.app.db.mongo import get_database
    from cryptography.fernet import Fernet
    import asyncio
    import os

    fernet = Fernet(os.environ["LINKEDIN_TOKEN_ENCRYPTION_KEY"].encode())

    async def _seed():
        db = get_database()
        await db["linkedin_accounts"].update_one(
            {"_id": user_id},
            {
                "$set": {
                    "access_token_enc": fernet.encrypt(b"FAKE"),
                    "refresh_token_enc": fernet.encrypt(b"FAKE_R"),
                    "expires_at": datetime.now(timezone.utc),
                    "scope": "openid profile email w_member_social",
                    "person_urn": "urn:li:person:USER_A_URN",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    asyncio.run(_seed())


def test_get_settings_anonymous_returns_401(client_anon):
    response = client_anon.get("/api/v1/settings")
    assert response.status_code == 401


def test_get_settings_returns_defaults(client_a):
    response = client_a.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["publishing_mode"] == "manual"
    assert body["approval_mode"] == "email"
    assert body["linkedin_connected"] is False
    assert body["person_urn"] is None


def test_get_settings_reflects_linkedin_connection(client_a):
    _seed_user_with_linkedin()
    response = client_a.get("/api/v1/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["linkedin_connected"] is True
    assert body["person_urn"] == "urn:li:person:USER_A_URN"


def test_update_settings_persists_fields(client_a):
    response = client_a.put(
        "/api/v1/settings",
        json={
            "publishing_mode": "scheduled",
            "approval_mode": "manual",
            "notification_email": "alice@example.com",
            "timezone": "UTC",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["publishing_mode"] == "scheduled"
    assert body["approval_mode"] == "manual"
    assert body["notification_email"] == "alice@example.com"
    assert body["timezone"] == "UTC"

    get_resp = client_a.get("/api/v1/settings")
    assert get_resp.json()["publishing_mode"] == "scheduled"


def test_update_settings_rejects_invalid_enum(client_a):
    response = client_a.put(
        "/api/v1/settings",
        json={"publishing_mode": "INVALID"},
    )
    assert response.status_code == 422
    body = response.json()
    assert "publishing_mode" in body["error"]["message"]


def test_update_settings_rejects_invalid_timezone(client_a):
    response = client_a.put(
        "/api/v1/settings",
        json={"timezone": "Not/A/Real/Zone"},
    )
    assert response.status_code == 422
    body = response.json()
    assert "timezone" in body["error"]["message"].lower()


def test_update_settings_rejects_invalid_email(client_a):
    response = client_a.put(
        "/api/v1/settings",
        json={"notification_email": "not-an-email"},
    )
    assert response.status_code == 422


def test_update_settings_empty_body_returns_current(client_a):
    response = client_a.put("/api/v1/settings", json={})
    assert response.status_code == 200
