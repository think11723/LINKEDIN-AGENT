"""LinkedIn OAuth tests: state binding + non-reuse + Fernet encryption."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient


def test_status_when_not_connected(client_a: TestClient) -> None:
    response = client_a.get("/api/v1/linkedin/status")
    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert "access_token" not in body
    assert "refresh_token" not in body


def test_connect_creates_state(client_a: TestClient) -> None:
    response = client_a.get("/api/v1/linkedin/connect")
    assert response.status_code == 200
    body = response.json()
    assert body["authorization_url"].startswith("https://www.linkedin.com/oauth/v2/authorization")
    assert body["state"]
    assert body["expires_at"]


def test_callback_rejects_invalid_state(client_a: TestClient) -> None:
    response = client_a.get(
        "/api/v1/linkedin/callback",
        params={"code": "abc", "state": "definitely-not-a-real-state"},
    )
    assert response.status_code == 400


def test_callback_rejects_expired_state(client_a: TestClient) -> None:
    """Inject an expired state directly into Mongo and verify the callback rejects it."""
    import asyncio
    import secrets

    from backend.app.db.mongo import get_database
    from backend.app.repositories import OAuthStateRepository

    async def _insert_expired() -> str:
        repo = OAuthStateRepository(get_database())
        state = secrets.token_urlsafe(8)
        await repo.col.insert_one(
            {
                "_id": state,
                "state": state,
                "user_id": "USER_A",
                "code_verifier": "v",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc),  # already past
                "consumed": False,
            }
        )
        return state

    state = asyncio.run(_insert_expired())
    response = client_a.get(
        "/api/v1/linkedin/callback",
        params={"code": "abc", "state": state},
    )
    assert response.status_code == 400


def test_oauth_state_is_single_use(client_a: TestClient) -> None:
    """Simulate a callback that consumes the state — a second attempt fails."""
    import asyncio
    import secrets

    from backend.app.db.mongo import get_database

    state = secrets.token_urlsafe(8)
    asyncio.run(
        get_database()["oauth_states"].insert_one(
            {
                "_id": state,
                "state": state,
                "user_id": "USER_A",
                "code_verifier": "v",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc).replace(year=2099),
                "consumed": True,  # already consumed
            }
        )
    )
    response = client_a.get(
        "/api/v1/linkedin/callback",
        params={"code": "abc", "state": state},
    )
    assert response.status_code == 400


def test_status_response_never_includes_tokens(client_a: TestClient) -> None:
    response = client_a.get("/api/v1/linkedin/status")
    text = response.text
    assert "access_token" not in text
    assert "refresh_token" not in text
    assert "client_secret" not in text


def test_disconnect_returns_disconnected(client_a: TestClient) -> None:
    response = client_a.post("/api/v1/linkedin/disconnect")
    assert response.status_code == 200
    assert response.json() == {"connected": False}