"""Phase 8B P1-7 — schedule cancellation tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from backend.app.db.mongo import get_database


def _schedule(client, *, when=None):
    when = when or (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    response = client.post(
        "/api/v1/scheduler/schedule",
        json={"title": "S", "content": "C", "hashtags": [], "scheduled_time": when},
    )
    assert response.status_code == 200, response.text
    return response.json()["job_id"]


def test_cancel_pending_job_returns_204(client_a):
    job_id = _schedule(client_a)
    response = client_a.delete(f"/api/v1/scheduler/jobs/{job_id}")
    assert response.status_code == 204
    # And it's gone.
    list_resp = client_a.get("/api/v1/scheduler/jobs")
    assert all(j["job_id"] != job_id for j in list_resp.json())


def test_cancel_cross_user_returns_404(client_a, client_b):
    job_id = _schedule(client_a)
    response = client_b.delete(f"/api/v1/scheduler/jobs/{job_id}")
    assert response.status_code == 404
    # A still owns it.
    list_a = client_a.get("/api/v1/scheduler/jobs")
    assert any(j["job_id"] == job_id for j in list_a.json())


def test_cancel_completed_job_returns_409(client_a):
    job_id = _schedule(client_a)

    async def _mark_completed():
        db = get_database()
        await db["scheduled_jobs"].update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "linkedin_post_id": "urn:li:ugcPost:9999",
                    "completed_at": datetime.now(timezone.utc),
                }
            },
        )

    asyncio.run(_mark_completed())

    response = client_a.delete(f"/api/v1/scheduler/jobs/{job_id}")
    assert response.status_code == 409


def test_cancel_failed_job_returns_409(client_a):
    job_id = _schedule(client_a)

    async def _mark_failed():
        db = get_database()
        await db["scheduled_jobs"].update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "last_error": "X",
                    "completed_at": datetime.now(timezone.utc),
                }
            },
        )

    asyncio.run(_mark_failed())

    response = client_a.delete(f"/api/v1/scheduler/jobs/{job_id}")
    assert response.status_code == 409


def test_cancel_writes_audit_event(client_a):
    from backend.app.db.mongo import get_database

    job_id = _schedule(client_a)
    client_a.delete(f"/api/v1/scheduler/jobs/{job_id}")

    async def _load():
        db = get_database()
        cursor = db["audit_events"].find({"user_id": "USER_A", "event_type": "JOB_CANCELLED"})
        return [doc async for doc in cursor]

    events = asyncio.run(_load())
    assert any(e.get("details", {}).get("job_id") == job_id for e in events)
