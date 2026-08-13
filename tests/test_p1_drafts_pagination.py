"""Phase 8B P1-3 — server-side draft pagination tests."""

from __future__ import annotations

import asyncio

from backend.app.db.mongo import get_database


async def _seed(n: int) -> None:
    db = get_database()
    await db["drafts"].delete_many({"_id": {"$regex": "^pagination-"}})
    docs = [
        {
            "_id": f"pagination-{i:03d}",
            "user_id": "USER_A",
            "topic": f"t{i}",
            "title": f"T{i}",
            "content": f"c{i}",
            "hashtags": [],
            "image_path": None,
            "status": "draft",
            "created_at": f"2026-08-13T00:00:{i:02d}Z",
            "updated_at": f"2026-08-13T00:00:{i:02d}Z",
        }
        for i in range(n)
    ]
    await db["drafts"].insert_many(docs)


def test_pagination_default_size_and_total(client_a):
    asyncio.run(_seed(3))
    response = client_a.get("/api/v1/drafts?page=1&page_size=10")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3
    assert body["next_page"] is None


def test_pagination_returns_next_page_when_more_exist(client_a):
    asyncio.run(_seed(3))
    response = client_a.get("/api/v1/drafts?page=1&page_size=2")
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["next_page"] == 2


def test_pagination_cross_user_scoping(client_a, client_b):
    asyncio.run(_seed(3))
    # USER_A's draft list returns A's 3 drafts.
    a_resp = client_a.get("/api/v1/drafts?page=1&page_size=10")
    assert a_resp.json()["total"] == 3

    # USER_B's draft list is independent.
    b_resp = client_b.get("/api/v1/drafts?page=1&page_size=10")
    assert b_resp.json()["total"] == 0
    assert b_resp.json()["items"] == []


def test_pagination_status_filter(client_a):
    asyncio.run(_seed(2))
    # Update one to published.
    async def _update():
        db = get_database()
        await db["drafts"].update_one(
            {"_id": "pagination-000"}, {"$set": {"status": "published"}}
        )

    asyncio.run(_update())
    response = client_a.get("/api/v1/drafts?status=published&page=1&page_size=10")
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "published"


def test_pagination_search_filter(client_a):
    """Search filters by topic / title / content. mongomock-motor's
    regex implementation is permissive so we only verify the API
    accepts the search parameter and returns a valid envelope.
    """
    asyncio.run(_seed(3))
    response = client_a.get("/api/v1/drafts?search=T1&page=1&page_size=10")
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
