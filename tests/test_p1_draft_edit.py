"""Phase 8B P1-6 — draft edit flow tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.app.db.mongo import get_database


def _create_draft(client, *, user="USER_A", title="Original", content="c"):
    response = client.post(
        "/api/v1/drafts",
        json={"topic": "edit", "title": title, "content": content, "hashtags": []},
    )
    assert response.status_code == 201
    return response.json()["draft_id"]


def test_edit_draft_owner_can_modify(client_a):
    draft_id = _create_draft(client_a)
    response = client_a.put(
        f"/api/v1/drafts/{draft_id}",
        json={"title": "Updated"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"
    assert response.json()["content"] == "c"  # unchanged


def test_edit_draft_cross_user_returns_404(client_a, client_b):
    draft_id = _create_draft(client_a)
    response = client_b.put(
        f"/api/v1/drafts/{draft_id}",
        json={"title": "hijacked"},
    )
    assert response.status_code == 404
    # And USER_A's draft is unchanged.
    a_get = client_a.get(f"/api/v1/drafts/{draft_id}")
    assert a_get.json()["title"] == "Original"


def test_edit_draft_published_returns_409(client_a):
    draft_id = _create_draft(client_a)

    async def _mark_published():
        db = get_database()
        await db["drafts"].update_one(
            {"_id": draft_id},
            {
                "$set": {
                    "status": "published",
                    "published_at": datetime.now(timezone.utc),
                    "linkedin_post_id": "urn:li:ugcPost:9999",
                }
            },
        )

    asyncio.run(_mark_published())

    response = client_a.put(
        f"/api/v1/drafts/{draft_id}",
        json={"title": "Edit me"},
    )
    assert response.status_code == 409
    body = response.json()
    assert "Published" in body["error"]["message"]


def test_edit_draft_with_no_fields_is_noop(client_a):
    draft_id = _create_draft(client_a)
    response = client_a.put(f"/api/v1/drafts/{draft_id}", json={})
    assert response.status_code == 200
    # Original fields preserved.
    assert response.json()["title"] == "Original"
    assert response.json()["content"] == "c"


def test_edit_draft_updates_content_and_hashtags(client_a):
    draft_id = _create_draft(client_a)
    response = client_a.put(
        f"/api/v1/drafts/{draft_id}",
        json={"content": "new body", "hashtags": ["#x", "#y"]},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "new body"
    assert response.json()["hashtags"] == ["#x", "#y"]
