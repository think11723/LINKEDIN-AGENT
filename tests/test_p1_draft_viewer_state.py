"""Phase 8B P1-4 — DraftViewer state-aware action visibility tests.

The frontend state-aware logic is mostly exercised in Playwright. These
backend tests verify the source-of-truth data: a draft's ``status``,
``published_at``, and ``linkedin_post_id`` fields that drive the
viewer's action visibility. The frontend P1-4 implementation
mirrors these invariants.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from backend.app.db.mongo import get_database


def _create_draft(client, *, title="T"):
    response = client.post(
        "/api/v1/drafts",
        json={"topic": "v", "title": title, "content": "c", "hashtags": []},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_draft_default_state_is_draft(client_a):
    id = _create_draft(client_a)
    response = client_a.get(f"/api/v1/drafts/{id}")
    body = response.json()
    assert body["status"] == "draft"
    assert body["published_at"] is None
    assert body["linkedin_post_id"] is None


def test_draft_metadata_is_returned_after_generation(client_a, monkeypatch):
    from shared.schemas import (
        GenerateContentResponse,
        LinkedInPostPayload,
    )
    from backend.app.services import workflow_service

    def fake_run(_payload):
        return GenerateContentResponse(
            topic="t",
            final_post=LinkedInPostPayload(
                title="FromContent", content="body", hashtags=[], image_path=None
            ),
            approved=False,
            iterations=1,
            metadata={
                "writer_provider": "groq",
                "writer_model": "llama-3.3-70b",
                "reviewer_provider": "groq",
                "reviewer_model": "llama-3.3-70b",
            },
        )

    # ``generate_content`` is now async; the FastAPI endpoint
    # does ``await service.generate_content(payload)``. The mock
    # must return an awaitable. Wrap the sync return in an async
    # coroutine.
    async def async_generate_content(self, payload):
        return fake_run(payload)
    monkeypatch.setattr(workflow_service.WorkflowService, "generate_content", async_generate_content)

    response = client_a.post("/api/v1/content/generate", json={"topic": "t"})
    assert response.status_code == 200
    body = response.json()
    assert body["draft_id"]

    # Fetching the draft returns the LLM metadata for the viewer.
    get_resp = client_a.get(f"/api/v1/drafts/{body['draft_id']}")
    assert get_resp.status_code == 200
    # The viewer doesn't surface the metadata field directly today, but the
    # backend doc carries it. Verify via direct repo read.
    async def _load():
        db = get_database()
        return await db["drafts"].find_one({"_id": body["draft_id"]})

    doc = asyncio.run(_load())
    assert doc["metadata"]["llm"]["writer_provider"] == "groq"
    assert doc["metadata"]["llm"]["writer_model"] == "llama-3.3-70b"


def test_published_draft_blocks_edits(client_a):
    id = _create_draft(client_a)

    async def _mark_published():
        db = get_database()
        await db["drafts"].update_one(
            {"_id": id},
            {
                "$set": {
                    "status": "published",
                    "published_at": datetime.now(timezone.utc),
                    "linkedin_post_id": "urn:li:ugcPost:X",
                }
            },
        )

    asyncio.run(_mark_published())

    # The viewer should NOT show Edit / Publish-now.
    # Backend confirms the 409 guard.
    response = client_a.put(
        f"/api/v1/drafts/{id}", json={"title": "Try"}
    )
    assert response.status_code == 409


def test_unpublished_draft_allows_edits(client_a):
    id = _create_draft(client_a)
    response = client_a.put(
        f"/api/v1/drafts/{id}", json={"title": "Editable"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Editable"


def test_failed_scheduler_draft_keeps_status_failed(client_a):
    """The viewer reads status from the draft + scheduler. A scheduler-failed
    draft (status=failed) is readable but not publishable.
    """
    id = _create_draft(client_a)

    async def _mark_failed():
        db = get_database()
        await db["drafts"].update_one(
            {"_id": id}, {"$set": {"status": "failed"}}
        )

    asyncio.run(_mark_failed())
    response = client_a.get(f"/api/v1/drafts/{id}")
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
