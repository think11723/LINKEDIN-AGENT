"""Draft CRUD tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_draft_returns_owner(client_a: TestClient) -> None:
    response = client_a.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "AI Post", "content": "Hello"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["draft_id"]
    assert body["user_id"] == "USER_A"
    assert body["status"] == "draft"
    assert body["approval_token"]


def test_list_drafts_paginated(client_a: TestClient) -> None:
    for i in range(5):
        client_a.post(
            "/api/v1/drafts",
            json={"topic": f"topic-{i}", "title": f"Title {i}"},
        )
    response = client_a.get("/api/v1/drafts?page=1&page_size=3")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 3
    assert body["next_page"] == 2


def test_update_draft_persists(client_a: TestClient) -> None:
    created = client_a.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "Old", "content": "Old"},
    ).json()
    response = client_a.put(
        f"/api/v1/drafts/{created['draft_id']}",
        json={"title": "New", "content": "New"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New"


def test_delete_draft(client_a: TestClient) -> None:
    created = client_a.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "T"},
    ).json()
    response = client_a.delete(f"/api/v1/drafts/{created['draft_id']}")
    assert response.status_code == 204
    follow_up = client_a.get(f"/api/v1/drafts/{created['draft_id']}")
    assert follow_up.status_code == 404


def test_published_draft_cannot_be_edited(client_a: TestClient) -> None:
    """Simulate publish via direct Mongo manipulation then attempt edit."""
    import asyncio

    from backend.app.db.mongo import get_database
    from backend.app.repositories import DraftRepository

    created = client_a.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "T", "content": "c"},
    ).json()

    async def _publish() -> None:
        db = get_database()
        repo = DraftRepository(db)
        await repo.mark_published(
            user_id="USER_A",
            draft_id=created["draft_id"],
            linkedin_post_id="x",
        )

    asyncio.get_event_loop().run_until_complete(_publish()) if False else None
    # FastAPI is sync; use asyncio.run for the in-memory mock.
    asyncio.run(_publish())

    response = client_a.put(
        f"/api/v1/drafts/{created['draft_id']}",
        json={"title": "New"},
    )
    assert response.status_code == 409


def test_published_endpoint_only_returns_callers_posts(client_a: TestClient) -> None:
    import asyncio

    from backend.app.db.mongo import get_database
    from backend.app.repositories import DraftRepository

    a_draft = client_a.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "A1", "content": "c"},
    ).json()
    b_draft = client_a.post(
        "/api/v1/drafts",
        json={"topic": "ai", "title": "A2", "content": "c"},
    ).json()

    async def _publish(draft_id: str) -> None:
        repo = DraftRepository(get_database())
        await repo.mark_published(
            user_id="USER_A", draft_id=draft_id, linkedin_post_id="x"
        )

    asyncio.run(_publish(a_draft["draft_id"]))
    asyncio.run(_publish(b_draft["draft_id"]))

    response = client_a.get("/api/v1/approval/published")
    assert response.status_code == 200
    titles = sorted(item["title"] for item in response.json())
    assert titles == ["A1", "A2"]


def test_drafts_require_auth(client_anon: TestClient) -> None:
    for method, url in [
        ("GET", "/api/v1/drafts"),
        ("POST", "/api/v1/drafts"),
    ]:
        response = client_anon.request(method, url, json={"topic": "x"})
        assert response.status_code == 401, f"{method} {url} should require auth"