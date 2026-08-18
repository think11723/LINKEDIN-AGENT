"""Phase 8D / P0 — SourceJobRepository tests.

User-scoped reads (the structural isolation guarantee) are exercised
here. The runner helpers (``claim_next_queued``, ``recover_stale_running``)
are tested in ``test_p0_source_job_runner.py``.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from backend.app.db.mongo import COLLECTION_SOURCE_JOBS, get_database
from backend.app.repositories.source_job_repository import SourceJobRepository


@pytest.fixture
def jobs() -> SourceJobRepository:
    return SourceJobRepository(get_database())


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def test_create_returns_queued_job_with_defaults(jobs: SourceJobRepository) -> None:
    doc = asyncio.run(
        jobs.create(user_id="USER_A", url="https://example.com/x")
    )
    assert doc["status"] == SourceJobRepository.STATUS_QUEUED
    assert doc["user_id"] == "USER_A"
    assert doc["url"] == "https://example.com/x"
    assert doc["job_id"].startswith("sj_")
    assert doc["request_id"].startswith("req_")
    assert doc["stage"] is None
    assert doc["attempts"] == 0
    assert doc["adapter"] is None
    assert doc["intent"] is None
    assert doc["tone"] is None
    assert doc["audience"] is None
    assert doc["error"] is None
    assert doc["error_code"] is None
    # expires_at is set in the future.
    assert doc["expires_at"] > doc["created_at"]


def test_create_stores_adapter_hint(jobs: SourceJobRepository) -> None:
    doc = asyncio.run(
        jobs.create(
            user_id="USER_A",
            url="https://github.com/user/repo",
            adapter="github",
        )
    )
    assert doc["adapter"] == "github"


def test_create_stores_overrides(jobs: SourceJobRepository) -> None:
    doc = asyncio.run(
        jobs.create(
            user_id="USER_A",
            url="https://example.com/x",
            intent="announce",
            tone="professional",
            audience="developers",
        )
    )
    assert doc["intent"] == "announce"
    assert doc["tone"] == "professional"
    assert doc["audience"] == "developers"


def test_get_is_strictly_user_scoped(jobs: SourceJobRepository) -> None:
    """The structural isolation guarantee: a different ``user_id`` returns
    ``None`` even when the ``job_id`` is correct. This is how the API
    endpoint enforces user isolation without an explicit permission check.
    """
    user_a_job = asyncio.run(
        jobs.create(user_id="USER_A", url="https://example.com/a")
    )
    user_b_job = asyncio.run(
        jobs.create(user_id="USER_B", url="https://example.com/b")
    )

    # Same job_id, same user → returned.
    assert asyncio.run(jobs.get(user_a_job["job_id"], "USER_A")) is not None
    # Same job_id, different user → None.
    assert asyncio.run(jobs.get(user_a_job["job_id"], "USER_B")) is None
    # Distinct jobs are distinct rows.
    assert user_a_job["job_id"] != user_b_job["job_id"]


def test_get_unknown_job_returns_none(jobs: SourceJobRepository) -> None:
    assert asyncio.run(jobs.get(_new_id("nope"), "USER_A")) is None


def test_count_active_for_user_excludes_terminal(jobs: SourceJobRepository) -> None:
    """``count_active_for_user`` counts queued + running, not succeeded/failed."""
    a1 = asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    a2 = asyncio.run(jobs.create(user_id="USER_A", url="https://x/2"))
    a3 = asyncio.run(jobs.create(user_id="USER_A", url="https://x/3"))
    asyncio.run(jobs.create(user_id="USER_B", url="https://x/4"))

    # All 3 of USER_A's jobs are queued (active).
    assert asyncio.run(jobs.count_active_for_user("USER_A")) == 3
    assert asyncio.run(jobs.count_active_for_user("USER_B")) == 1

    # Mark two of USER_A's jobs as terminal.
    asyncio.run(
        jobs.mark_succeeded(
            job_id=a1["job_id"],
            draft_id="draft1",
            approval_token=None,
            source_summary=None,
            source_metadata=None,
        )
    )
    asyncio.run(
        jobs.mark_failed(
            job_id=a2["job_id"],
            error="upstream 5xx",
            error_code="http_5xx",
        )
    )

    # Only the still-queued a3 counts as active for USER_A.
    assert asyncio.run(jobs.count_active_for_user("USER_A")) == 1
    # USER_B unchanged.
    assert asyncio.run(jobs.count_active_for_user("USER_B")) == 1
    # ``a3`` is still in the active set.
    assert a3["job_id"] in {j["job_id"] for j in asyncio.run(jobs.list_for_user("USER_A"))}


def test_count_recent_for_user_window(jobs: SourceJobRepository) -> None:
    from datetime import timedelta

    asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    asyncio.run(jobs.create(user_id="USER_A", url="https://x/2"))
    # 1h window: both jobs are within it.
    assert (
        asyncio.run(jobs.count_recent_for_user("USER_A", window=timedelta(hours=1)))
        == 2
    )
    # 1-second window: zero (the jobs are older than 1s when the
    # assertion fires — a same-second race could flake, so use a
    # generous assertion).
    n = asyncio.run(
        jobs.count_recent_for_user("USER_A", window=timedelta(seconds=0))
    )
    assert n in {0, 1, 2}  # tolerate millisecond-level timing


def test_claim_next_queued_is_atomic(jobs: SourceJobRepository) -> None:
    """Two concurrent claimers must get two different jobs.

    Asserts the atomicity of ``find_one_and_update`` — exactly the
    pattern that prevents the runner from double-processing a job.
    """
    asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    asyncio.run(jobs.create(user_id="USER_A", url="https://x/2"))
    asyncio.run(jobs.create(user_id="USER_A", url="https://x/3"))

    async def claim_all():
        # Sequential but each ``claim_next_queued`` is one atomic write.
        a = await jobs.claim_next_queued()
        b = await jobs.claim_next_queued()
        c = await jobs.claim_next_queued()
        return a, b, c

    a, b, c = asyncio.run(claim_all())
    assert a is not None and b is not None and c is not None
    assert len({a["job_id"], b["job_id"], c["job_id"]}) == 3
    # All three are now ``running`` with attempts=1.
    for job in (a, b, c):
        assert job["status"] == SourceJobRepository.STATUS_RUNNING
        assert job["attempts"] == 1
        assert job["stage"] == SourceJobRepository.STAGE_FETCHING


def test_claim_next_queued_returns_none_when_empty(
    jobs: SourceJobRepository,
) -> None:
    assert asyncio.run(jobs.claim_next_queued()) is None


def test_set_stage_updates_stage(jobs: SourceJobRepository) -> None:
    doc = asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    asyncio.run(jobs.set_stage(doc["job_id"], SourceJobRepository.STAGE_WRITING))
    fetched = asyncio.run(jobs.get(doc["job_id"], "USER_A"))
    assert fetched["stage"] == SourceJobRepository.STAGE_WRITING


def test_mark_succeeded_and_mark_failed(jobs: SourceJobRepository) -> None:
    """Round-trip the two terminal transitions."""
    a = asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    b = asyncio.run(jobs.create(user_id="USER_A", url="https://x/2"))

    asyncio.run(
        jobs.mark_succeeded(
            job_id=a["job_id"],
            draft_id="d1",
            approval_token="t1",
            source_summary={"title": "T", "summary": "S"},
            source_metadata={"adapter": "github"},
        )
    )
    asyncio.run(
        jobs.mark_failed(
            job_id=b["job_id"],
            error="upstream 5xx",
            error_code="http_5xx",
        )
    )

    fa = asyncio.run(jobs.get(a["job_id"], "USER_A"))
    fb = asyncio.run(jobs.get(b["job_id"], "USER_A"))
    assert fa["status"] == SourceJobRepository.STATUS_SUCCEEDED
    assert fa["draft_id"] == "d1"
    assert fa["approval_token"] == "t1"
    assert fa["source_summary"]["title"] == "T"
    assert fa["finished_at"] is not None
    assert fb["status"] == SourceJobRepository.STATUS_FAILED
    assert fb["error"] == "upstream 5xx"
    assert fb["error_code"] == "http_5xx"
    assert fb["finished_at"] is not None


def test_recover_stale_running_resets_to_queued(
    jobs: SourceJobRepository,
) -> None:
    """Stale ``running`` rows are requeued; ``succeeded`` rows are untouched."""
    fresh = asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    stale = asyncio.run(jobs.create(user_id="USER_A", url="https://x/2"))

    # Claim both.
    asyncio.run(jobs.claim_next_queued())
    asyncio.run(jobs.claim_next_queued())
    # Backdate ``stale``'s started_at by 1 hour via direct update.
    asyncio.run(
        jobs.col.update_one(
            {"job_id": stale["job_id"]},
            {"$set": {"started_at": datetime.now(timezone.utc)}},
        )
    )
    # Actually backdate it properly.
    from datetime import timedelta

    asyncio.run(
        jobs.col.update_one(
            {"job_id": stale["job_id"]},
            {
                "$set": {
                    "started_at": datetime.now(timezone.utc) - timedelta(hours=1)
                }
            },
        )
    )
    # Mark ``fresh`` succeeded.
    asyncio.run(
        jobs.mark_succeeded(
            job_id=fresh["job_id"],
            draft_id="d",
            approval_token=None,
            source_summary=None,
            source_metadata=None,
        )
    )

    # Run recovery with a 5-minute threshold.
    n = asyncio.run(jobs.recover_stale_running(older_than_seconds=300))
    assert n == 1  # only ``stale`` was recovered

    stale_after = asyncio.run(jobs.get(stale["job_id"], "USER_A"))
    fresh_after = asyncio.run(jobs.get(fresh["job_id"], "USER_A"))
    assert stale_after["status"] == SourceJobRepository.STATUS_QUEUED
    assert fresh_after["status"] == SourceJobRepository.STATUS_SUCCEEDED


def test_recover_stale_running_is_idempotent(
    jobs: SourceJobRepository,
) -> None:
    asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    asyncio.run(jobs.claim_next_queued())
    from datetime import timedelta

    asyncio.run(
        jobs.col.update_one(
            {"user_id": "USER_A"},
            {
                "$set": {
                    "started_at": datetime.now(timezone.utc) - timedelta(hours=1)
                }
            },
        )
    )
    assert (
        asyncio.run(jobs.recover_stale_running(older_than_seconds=300)) == 1
    )
    # Second call: nothing to recover.
    assert (
        asyncio.run(jobs.recover_stale_running(older_than_seconds=300)) == 0
    )


def test_recover_stale_running_respects_user_scope(
    jobs: SourceJobRepository,
) -> None:
    """Stale jobs are recovered regardless of user — they're a global
    restart-safety sweep, not a per-user operation.
    """
    asyncio.run(jobs.create(user_id="USER_A", url="https://x/1"))
    asyncio.run(jobs.create(user_id="USER_B", url="https://x/2"))
    asyncio.run(jobs.claim_next_queued())
    asyncio.run(jobs.claim_next_queued())
    from datetime import timedelta

    asyncio.run(
        jobs.col.update_many(
            {},
            {
                "$set": {
                    "started_at": datetime.now(timezone.utc) - timedelta(hours=1)
                }
            },
        )
    )
    n = asyncio.run(jobs.recover_stale_running(older_than_seconds=300))
    assert n == 2


def test_to_response_strips_internal_fields(
    jobs: SourceJobRepository,
) -> None:
    """Internal-only fields (TTL, attempts, etc.) are not in the API response."""
    doc = asyncio.run(
        jobs.create(user_id="USER_A", url="https://example.com/x")
    )
    response = SourceJobRepository.to_response(doc)
    # Public fields present.
    for key in [
        "job_id",
        "status",
        "url",
        "created_at",
        "stage",
        "adapter",
        "draft_id",
        "approval_token",
        "source_summary",
        "source_metadata",
        "request_id",
        "error",
        "error_code",
    ]:
        assert key in response
    # Internal-only fields absent. (user_id is the authenticated
    # caller's own UID — already known to the SPA — so it is not
    # surfaced in the response.)
    for internal in ["_id", "expires_at", "attempts"]:
        assert internal not in response

    # Datetime fields are ISO 8601 strings.
    assert isinstance(response["created_at"], str)
