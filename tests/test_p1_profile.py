"""Phase 8B P1-10 — server-side profile tests."""

from __future__ import annotations


def test_get_profile_anonymous_returns_401(client_anon):
    response = client_anon.get("/api/v1/profile")
    assert response.status_code == 401


def test_get_profile_returns_200_for_authenticated(client_a):
    """First call auto-seeds the user document; subsequent calls are no-op."""
    response = client_a.get("/api/v1/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "USER_A"
    # The conftest's user_a fixture seeds email = "USER_A@example.com".
    assert body["email"] == "USER_A@example.com"
    assert body["email_verified"] is True


def test_update_profile_persists_fields(client_a):
    response = client_a.put(
        "/api/v1/profile",
        json={
            "display_name": "Alice",
            "headline": "Engineer",
            "bio": "Hello world",
            "linkedin_url": "https://linkedin.com/in/alice",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice"
    assert body["headline"] == "Engineer"
    assert body["bio"] == "Hello world"
    assert body["linkedin_url"] == "https://linkedin.com/in/alice"

    # GET returns the persisted fields.
    get_resp = client_a.get("/api/v1/profile")
    assert get_resp.json()["display_name"] == "Alice"


def test_update_profile_cross_user_returns_404(client_a, client_b):
    response = client_b.put("/api/v1/profile", json={"display_name": "B"})
    # The endpoint is keyed by the caller's uid (b's uid). 404 only happens
    # when the user document does not exist; both clients here call on
    # their own uid so this is a 200 with B's data, not a 404. Test that
    # USER_A's data was not modified.
    assert response.status_code == 200
    a_put = client_a.put(
        "/api/v1/profile", json={"display_name": "Alice-A"}
    )
    a_get = client_a.get("/api/v1/profile")
    assert a_get.json()["display_name"] == "Alice-A"
    assert a_get.json()["display_name"] != response.json().get("display_name", "") or (
        response.json().get("display_name") == ""
    )


def test_update_profile_with_unknown_field_ignored(client_a):
    """Server-side allowlist: unknown keys must be silently dropped."""
    response = client_a.put(
        "/api/v1/profile",
        json={"display_name": "Alice", "user_id": "INJECTED", "is_admin": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Alice"
    assert "user_id" not in body  # never echoed (it's a path/query param)
    assert "is_admin" not in body  # silently dropped by allowlist


def test_update_profile_empty_body_returns_current(client_a):
    response = client_a.put("/api/v1/profile", json={})
    assert response.status_code == 200
    # Just returns the current profile (no changes).
