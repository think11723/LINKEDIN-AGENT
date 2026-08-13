"""Tests for Phase 8A P0-3: scheduler orphan recovery."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.db.mongo import get_database
from backend.app.repositories.scheduler_repository import SchedulerRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_jobs(repo: SchedulerRepository) -> dict[str, str]:
    """Insert one stale-running + one fresh-running + one pending."""
    now = _utcnow()
    ids = {
        "stale": "stale-running-job",
        "fresh": "fresh-running-job",
        "pending": "pending-job",
    }
    await repo.col.insert_many([
        {
            "_id": ids["stale"],
            "user_id": "USER_A",
            "title": "Stale",
            "content": "x",
            "hashtags": [],
            "image_path": None,
            "scheduled_time": now - timedelta(minutes=20),
            "status": "running",
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now - timedelta(minutes=20),
            "updated_at": now - timedelta(minutes=20),
            "started_at": now - timedelta(minutes=20),
        },
        {
            "_id": ids["fresh"],
            "user_id": "USER_A",
            "title": "Fresh",
            "content": "x",
            "hashtags": [],
            "image_path": None,
            "scheduled_time": now - timedelta(minutes=2),
            "status": "running",
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now - timedelta(minutes=2),
            "updated_at": now - timedelta(minutes=2),
            "started_at": now - timedelta(minutes=2),
        },
        {
            "_id": ids["pending"],
            "user_id": "USER_A",
            "title": "Pending",
            "content": "x",
            "hashtags": [],
            "image_path": None,
            "scheduled_time": now + timedelta(minutes=10),
            "status": "pending",
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now,
            "updated_at": now,
        },
    ])
    return ids


def test_recover_orphans_resets_only_stale_running_jobs():
    repo = SchedulerRepository(get_database())
    ids = asyncio.run(_seed_jobs(repo))

    recovered = asyncio.run(repo.recover_orphans(older_than_seconds=600))
    assert recovered == 1, f"Expected exactly the stale job to be recovered, got {recovered}"

    stale = asyncio.run(repo.get("USER_A", ids["stale"]))
    fresh = asyncio.run(repo.get("USER_A", ids["fresh"]))
    pending = asyncio.run(repo.get("USER_A", ids["pending"]))

    assert stale["status"] == "pending"
    assert stale.get("orphan_recoveries", 0) == 1
    # Fresh running job must NOT be touched (started_at within threshold).
    assert fresh["status"] == "running"
    assert fresh.get("orphan_recoveries", 0) == 0
    # Pending jobs are unrelated.
    assert pending["status"] == "pending"
    assert pending.get("orphan_recoveries", 0) == 0


def test_recover_orphans_is_idempotent():
    repo = SchedulerRepository(get_database())
    asyncio.run(_seed_jobs(repo))

    first = asyncio.run(repo.recover_orphans(older_than_seconds=600))
    second = asyncio.run(repo.recover_orphans(older_than_seconds=600))
    assert first == 1
    # Second pass: the job is already pending — no further changes.
    assert second == 0


def test_recover_orphans_with_zero_threshold_recovers_fresh_too():
    """A threshold of 0 seconds should treat every running job as stale."""
    repo = SchedulerRepository(get_database())
    asyncio.run(_seed_jobs(repo))

    recovered = asyncio.run(repo.recover_orphans(older_than_seconds=0))
    # The "fresh" job (started 2 min ago) and the "stale" one both qualify.
    assert recovered == 2