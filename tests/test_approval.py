"""Approval tests: token scoping + idempotency + cross-user rejection."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_draft_with_token(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "Approval Test", "content": "c"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["draft_id"], body["approval_token"]


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


def test_approve_is_idempotent(client_a: TestClient) -> None:
    _, token = _create_draft_with_token(client_a)

    first = client_a.post("/api/v1/approval/approve", json={"token": token})
    second = client_a.post("/api/v1/approval/approve", json={"token": token})

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