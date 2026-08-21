"""Multi-user isolation tests for drafts."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_draft(client: TestClient, *, topic: str = "isolation test") -> dict:
    response = client.post(
        "/api/v1/drafts",
        json={"topic": topic, "title": topic.title(), "content": "hello world"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_user_a_cannot_read_user_b_draft(client_a: TestClient, client_b: TestClient) -> None:
    b_draft = _create_draft(client_b)

    response = client_a.get(f"/api/v1/drafts/{b_draft['id']}")
    assert response.status_code == 404


def test_user_a_cannot_update_user_b_draft(client_a: TestClient, client_b: TestClient) -> None:
    b_draft = _create_draft(client_b)

    response = client_a.put(
        f"/api/v1/drafts/{b_draft['id']}",
        json={"title": "hijacked"},
    )
    assert response.status_code == 404

    # Verify the underlying record is untouched.
    follow_up = client_b.get(f"/api/v1/drafts/{b_draft['id']}")
    assert follow_up.status_code == 200
    assert follow_up.json()["title"] == b_draft["title"]


def test_user_a_cannot_delete_user_b_draft(client_a: TestClient, client_b: TestClient) -> None:
    b_draft = _create_draft(client_b)

    response = client_a.delete(f"/api/v1/drafts/{b_draft['id']}")
    assert response.status_code == 404

    # Verify the underlying record is untouched.
    follow_up = client_b.get(f"/api/v1/drafts/{b_draft['id']}")
    assert follow_up.status_code == 200


def test_user_a_list_does_not_include_user_b_drafts(
    client_a: TestClient, client_b: TestClient
) -> None:
    _create_draft(client_b, topic="private")
    _create_draft(client_a, topic="mine")

    response_a = client_a.get("/api/v1/drafts")
    assert response_a.status_code == 200
    titles_a = [item["title"] for item in response_a.json()["items"]]
    assert "Mine" in titles_a
    assert "Private" not in titles_a

    response_b = client_b.get("/api/v1/drafts")
    titles_b = [item["title"] for item in response_b.json()["items"]]
    assert "Private" in titles_b
    assert "Mine" not in titles_b


def test_dashboard_is_user_scoped(client_a: TestClient, client_b: TestClient) -> None:
    _create_draft(client_a, topic="a-draft")
    _create_draft(client_a, topic="another-a-draft")
    _create_draft(client_b, topic="b-draft")

    a_summary = client_a.get("/api/v1/dashboard/summary").json()
    b_summary = client_b.get("/api/v1/dashboard/summary").json()

    assert a_summary["drafts_count"] == 2
    assert b_summary["drafts_count"] == 1


def test_activity_is_user_scoped(client_a: TestClient, client_b: TestClient) -> None:
    _create_draft(client_a, topic="a-draft")

    a_activity = client_a.get("/api/v1/activity/recent").json()
    b_activity = client_b.get("/api/v1/activity/recent").json()

    assert len(a_activity["items"]) >= 1
    assert all(item["event_type"] for item in a_activity["items"])
    assert b_activity["items"] == []


def test_user_a_cannot_edit_user_b_via_approval_edit(
    client_a: TestClient, client_b: TestClient
) -> None:
    b_draft = _create_draft(client_b)
    response = client_a.post(
        "/api/v1/approval/edit",
        json={
            "draft_id": b_draft["id"],
            "title": "hijacked",
            "content": "x",
            "hashtags": [],
        },
    )
    assert response.status_code == 404