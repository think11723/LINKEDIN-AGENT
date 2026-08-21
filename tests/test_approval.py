"""Approval tests: token scoping + idempotency + cross-user rejection."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import asyncio
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


def _seed_linkedin_tokens_for_test(user_id: str = "USER_A") -> None:
    """Insert a fake LinkedIn account row with Fernet-encrypted tokens.

    Required for approval tests that now trigger publish_now, because
    publish_now requires a stored LinkedIn access token.
    """
    fernet = Fernet(os.environ["LINKEDIN_TOKEN_ENCRYPTION_KEY"].encode())

    async def _insert() -> None:
        from backend.app.db.mongo import get_database
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

    asyncio.get_event_loop().run_until_complete(_insert()) if False else asyncio.run(_insert())


def _create_draft_with_token(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "Approval Test", "content": "c"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["id"], body["approval_token"]


def test_user_a_cannot_load_user_b_approval_draft(client_a: TestClient, client_b: TestClient) -> None:
    _, token = _create_draft_with_token(client_b)

    response = client_a.get(f"/api/v1/approval/draft?token={token}")
    assert response.status_code == 404


def test_user_a_cannot_approve_user_b_token(client_a: TestClient, client_b: TestClient) -> None:
    _, token = _create_draft_with_token(client_b)

    response = client_a.post(
        "/api/v1/approval/approve",
        json={"token": token},
    )
    assert response.status_code == 404


def test_approve_is_idempotent(client_a: TestClient, monkeypatch) -> None:
    """Approving twice yields success==True on both calls. The first
    call publishes the draft; the second call is a no-op (the draft
    is already published) and the approval is recorded as
    idempotent."""
    # Seed LinkedIn tokens + stub LinkedIn API so approve → publish
    # succeeds end-to-end.
    _seed_linkedin_tokens_for_test("USER_A")
    import httpx

    class _R:
        status_code = 201

        def json(self):
            return {"id": "urn:li:ugcPost:approve-idem"}

    async def fake_post(*_a, **_kw):
        return _R()

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    _, token = _create_draft_with_token(client_a)

    first = client_a.post(
        "/api/v1/approval/approve",
        json={"token": token},
    )
    second = client_a.post(
        "/api/v1/approval/approve",
        json={"token": token},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["success"] is True
    assert second.json()["success"] is True


def test_reject_is_idempotent(client_a: TestClient) -> None:
    _, token = _create_draft_with_token(client_a)

    first = client_a.post("/api/v1/approval/reject", json={"token": token})
    second = client_a.post("/api/v1/approval/reject", json={"token": token})

    assert first.status_code == 200
    assert second.status_code == 200


def test_approval_queue_only_returns_callers_pending(client_a: TestClient, client_b: TestClient) -> None:
    _create_draft_with_token(client_a)
    _create_draft_with_token(client_b)

    a_queue = client_a.get("/api/v1/approval/queue").json()
    b_queue = client_b.get("/api/v1/approval/queue").json()

    assert len(a_queue) == 1
    assert len(b_queue) == 1