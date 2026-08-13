"""Auth tests: 401 on missing/invalid bearer, 200 on valid token."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_missing_authorization_returns_401(client_anon: TestClient) -> None:
    response = client_anon.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_malformed_authorization_returns_401(client_anon: TestClient) -> None:
    response = client_anon.get(
        "/api/v1/auth/me",
        headers={"Authorization": "NotBearer abc"},
    )
    assert response.status_code == 401


def test_invalid_token_returns_401(client_anon: TestClient) -> None:
    from backend.app.core import security

    def boom(token, app=None):
        raise security.firebase_auth.InvalidIdTokenError("nope")

    original = security.firebase_auth.verify_id_token
    security.firebase_auth.verify_id_token = boom
    try:
        response = client_anon.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer bogus"},
        )
        assert response.status_code == 401
    finally:
        security.firebase_auth.verify_id_token = original


def test_valid_token_returns_user(client_a: TestClient) -> None:
    response = client_a.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "USER_A"
    assert body["email"].endswith("@example.com")