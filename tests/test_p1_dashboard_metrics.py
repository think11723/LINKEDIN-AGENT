"""Phase 8B P1-5 — dashboard metrics tests (approved + failed counts)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from backend.app.db.mongo import get_database


def _create_draft(client, *, user="USER_A", title="T", status="draft", published=False):
    response = client.post(
        "/api/v1/drafts",
        json={"topic": "d", "title": title, "content": "c", "hashtags": []},
    )
    assert response.status_code == 201
    id = response.json()["id"]

    if status != "draft" or published:
        async def _update():
            db = get_database()
            update = {"status": status}
            if published:
                update["published_at"] = datetime.now(timezone.utc)
                update["linkedin_post_id"] = "urn:li:ugcPost:9999"
            await db["drafts"].update_one({"_id": id}, {"$set": update})

        asyncio.run(_update())
    return id


def _schedule(client, *, when=None, status="pending"):
    when = when or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    response = client.post(
        "/api/v1/scheduler/schedule",
        json={"title": "S", "content": "C", "hashtags": [], "scheduled_time": when},
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    if status != "pending":
        async def _update():
            db = get_database()
            await db["scheduled_jobs"].update_one(
                {"_id": job_id}, {"$set": {"status": status}}
            )

        asyncio.run(_update())
    return job_id


def test_dashboard_summary_includes_approved_count(client_a):
    _create_draft(client_a, title="approved-1", status="approved")
    _create_draft(client_a, title="approved-2", status="approved")
    _create_draft(client_a, title="draft-1", status="draft")

    response = client_a.get("/api/v1/dashboard/summary")
    body = response.json()
    assert body["approved_count"] == 2
    assert body["drafts_count"] == 3


def test_dashboard_summary_includes_failed_count(client_a):
    _schedule(client_a, status="failed")
    _schedule(client_a, status="failed")
    _schedule(client_a, status="pending")

    response = client_a.get("/api/v1/dashboard/summary")
    body = response.json()
    assert body["failed_count"] == 2
    assert body["scheduled_count"] == 1


def test_dashboard_summary_cross_user_scoping(client_a, client_b):
    _create_draft(client_a, title="A-1", status="approved")
    _create_draft(client_a, title="A-2")
    _create_draft(client_b, title="B-1", status="approved")

    a = client_a.get("/api/v1/dashboard/summary").json()
    b = client_b.get("/api/v1/dashboard/summary").json()

    assert a["approved_count"] == 1
    assert a["drafts_count"] == 2
    assert b["approved_count"] == 1
    assert b["drafts_count"] == 1
