"""Scheduler tests: ownership + cancel."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _schedule(client: TestClient, *, when: datetime | None = None) -> dict:
    when = when or (datetime.now(timezone.utc) + timedelta(hours=1))
    response = client.post(
        "/api/v1/scheduler/schedule",
        json={
            "title": "T",
            "content": "C",
            "hashtags": [],
            "scheduled_time": when.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_schedule_requires_auth(client_anon: TestClient) -> None:
    response = client_anon.post(
        "/api/v1/scheduler/schedule",
        json={
            "title": "T",
            "content": "C",
            "hashtags": [],
            "scheduled_time": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 401


def test_user_a_cannot_cancel_user_b_job(client_a: TestClient, client_b: TestClient) -> None:
    b_job = _schedule(client_b)

    response = client_a.delete(f"/api/v1/scheduler/jobs/{b_job['job_id']}")
    assert response.status_code == 404

    # Verify it still exists for user B.
    list_b = client_b.get("/api/v1/scheduler/jobs")
    assert list_b.status_code == 200
    assert any(item["job_id"] == b_job["job_id"] for item in list_b.json())


def test_cancel_own_job(client_a: TestClient) -> None:
    job = _schedule(client_a)
    response = client_a.delete(f"/api/v1/scheduler/jobs/{job['job_id']}")
    assert response.status_code == 204


def test_jobs_list_is_user_scoped(client_a: TestClient, client_b: TestClient) -> None:
    _schedule(client_a)
    _schedule(client_b)

    a_jobs = client_a.get("/api/v1/scheduler/jobs").json()
    b_jobs = client_b.get("/api/v1/scheduler/jobs").json()
    assert len(a_jobs) == 1
    assert len(b_jobs) == 1