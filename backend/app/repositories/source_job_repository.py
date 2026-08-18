"""Source-job repository — Phase 8D / URL-to-LinkedIn feature.

Backs the ``source_jobs`` Mongo collection declared in
``backend/app/db/mongo.py:14-20``. Every read is scoped by
``user_id`` — there is **no** bare ``get(job_id)`` helper, which is
how the user-isolation guarantee is enforced structurally.

Document shape (set in :meth:`:`create`):

    {
      "_id": ObjectId,
      "job_id": "sj_<uuid4hex>",         # unique index
      "user_id": "...",                   # (user_id, created_at desc) index
      "request_id": "req_<uuid4hex>",     # correlation
      "url": "https://…",                 # normalized
      "adapter": "github" | "webpage" | "stub" | None,
      "status": "queued" | "running" | "succeeded" | "failed" | "cancelled",
      "stage": "fetching" | "analyzing" | "writing" | "reviewing"
                | "persisting" | None,
      "attempts": 0,
      "draft_id": None,
      "approval_token": None,
      "source_summary": {"title","summary","key_facts"} | None,
      "source_metadata": {...} | None,
      "error": None,
      "error_code": None,
      "created_at", "started_at", "finished_at", "updated_at",
      "expires_at": <7-day TTL>,
      # Optional override fields written at create-time:
      "intent": Optional[str],
      "tone": Optional[str],
      "audience": Optional[str],
    }
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import COLLECTION_SOURCE_JOBS

logger = logging.getLogger(__name__)

# TTL on finished jobs: 7 days.
JOB_TTL = timedelta(days=7)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_job_id() -> str:
    return f"sj_{uuid.uuid4().hex}"


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


class SourceJobRepository:
    """User-scoped CRUD for ``source_jobs``.

    The runner calls :meth:`claim_next_queued` (atomic find_one_and_update)
    to take ownership of the next available job. The API endpoints use
    :meth:`create` and :meth:`get` — both scoped by ``user_id``.
    """

    # Status / stage literal sets — kept in sync with ``models/source.py``.
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    STAGE_FETCHING = "fetching"
    STAGE_ANALYZING = "analyzing"
    STAGE_WRITING = "writing"
    STAGE_REVIEWING = "reviewing"
    STAGE_PERSISTING = "persisting"

    TERMINAL_STATUSES = frozenset({STATUS_SUCCEEDED, STATUS_FAILED, STATUS_CANCELLED})

    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_SOURCE_JOBS]

    # ------------------------------------------------------------------
    # Create / lookup
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        user_id: str,
        url: str,
        adapter: Optional[str] = None,
        intent: Optional[str] = None,
        tone: Optional[str] = None,
        audience: Optional[str] = None,
        ttl: timedelta = JOB_TTL,
    ) -> dict:
        """Create a new ``queued`` job. Returns the stored document."""
        now = _utcnow()
        doc: dict[str, Any] = {
            "_id": uuid.uuid4().hex,
            "job_id": _new_job_id(),
            "user_id": user_id,
            "request_id": _new_request_id(),
            "url": url,
            "adapter": adapter,
            "status": self.STATUS_QUEUED,
            "stage": None,
            "attempts": 0,
            "draft_id": None,
            "approval_token": None,
            "source_summary": None,
            "source_metadata": None,
            "error": None,
            "error_code": None,
            "intent": intent,
            "tone": tone,
            "audience": audience,
            "created_at": now,
            "started_at": None,
            "finished_at": None,
            "updated_at": now,
            "expires_at": now + ttl,
        }
        await self.col.insert_one(doc)
        return doc

    async def get(self, job_id: str, user_id: str) -> Optional[dict]:
        """Return a job scoped by ``user_id`` — never cross-user."""
        return await self.col.find_one({"job_id": job_id, "user_id": user_id})

    async def list_for_user(
        self,
        user_id: str,
        *,
        limit: int = 50,
        skip: int = 0,
    ) -> list[dict]:
        cursor = (
            self.col.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(max(0, skip))
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def count_active_for_user(self, user_id: str) -> int:
        """Count jobs that are not yet terminal for the given user."""
        return await self.col.count_documents(
            {
                "user_id": user_id,
                "status": {"$nin": list(self.TERMINAL_STATUSES)},
            }
        )

    async def count_recent_for_user(self, user_id: str, *, window: timedelta) -> int:
        """Count jobs (any status) the user created in the last `` `` ``window``."""
        threshold = _utcnow() - window
        return await self.col.count_documents(
            {"user_id": user_id, "created_at": {"$gte": threshold}}
        )

    # ------------------------------------------------------------------
    # Runner helpers
    # ------------------------------------------------------------------

    async def claim_next_queued(self) -> Optional[dict]:
        """Atomically take ownership of the next ``queued`` job.

        Mirrors ``scheduler_repository.claim_due_job()`` —
        ``find_one_and_update`` flips ``status: queued`` to
        ``status: running`` and sets ``stage: fetching`` + ``started_at``
        in a single atomic write so two runner ticks never see the
        same row.

        Returns the post-update document, or ``None`` if nothing is
        available.
        """
        return await self.col.find_one_and_update(
            {"status": self.STATUS_QUEUED},
            {
                "$set": {
                    "status": self.STATUS_RUNNING,
                    "started_at": _utcnow(),
                    "stage": self.STAGE_FETCHING,
                    "updated_at": _utcnow(),
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1)],
            return_document=True,
        )

    async def set_stage(self, job_id: str, stage: str) -> Optional[dict]:
        return await self.col.find_one_and_update(
            {"job_id": job_id},
            {"$set": {"stage": stage, "updated_at": _utcnow()}},
            return_document=True,
        )

    async def mark_succeeded(
        self,
        *,
        job_id: str,
        draft_id: str,
        approval_token: Optional[str],
        source_summary: Optional[dict],
        source_metadata: Optional[dict],
    ) -> Optional[dict]:
        return await self.col.find_one_and_update(
            {"job_id": job_id},
            {
                "$set": {
                    "status": self.STATUS_SUCCEEDED,
                    "draft_id": draft_id,
                    "approval_token": approval_token,
                    "source_summary": source_summary,
                    "source_metadata": source_metadata,
                    "stage": None,
                    "finished_at": _utcnow(),
                    "updated_at": _utcnow(),
                    "error": None,
                    "error_code": None,
                }
            },
            return_document=True,
        )

    async def mark_failed(
        self,
        *,
        job_id: str,
        error: str,
        error_code: str,
        stage: Optional[str] = None,
    ) -> Optional[dict]:
        return await self.col.find_one_and_update(
            {"job_id": job_id},
            {
                "$set": {
                    "status": self.STATUS_FAILED,
                    "error": error,
                    "error_code": error_code,
                    "stage": stage,
                    "finished_at": _utcnow(),
                    "updated_at": _utcnow(),
                }
            },
            return_document=True,
        )

    async def requeue_for_retry(self, *, job_id: str, error: str, error_code: str) -> Optional[dict]:
        """Reset a transient ``running`` job back to ``queued`` for retry.

        Used when the runner sweep recovers a stale ``running`` row that
        did not complete due to a process crash.
        """
        return await self.col.find_one_and_update(
            {"job_id": job_id, "status": self.STATUS_RUNNING},
            {
                "$set": {
                    "status": self.STATUS_QUEUED,
                    "stage": None,
                    "started_at": None,
                    "error": error,
                    "error_code": error_code,
                    "updated_at": _utcnow(),
                }
            },
            return_document=True,
        )

    async def recover_stale_running(self, *, older_than_seconds: int) -> int:
        """Sweep ``running`` jobs older than the threshold back to ``queued``.

        Called once at runner startup. Returns the number of jobs
        recovered. Crashed-process recovery — see the parallel
        implementation in ``scheduler_runner.py`` P0-3.
        """
        threshold = _utcnow() - timedelta(seconds=older_than_seconds)
        result = await self.col.update_many(
            {"status": self.STATUS_RUNNING, "started_at": {"$lt": threshold}},
            {
                "$set": {
                    "status": self.STATUS_QUEUED,
                    "stage": None,
                    "started_at": None,
                    "updated_at": _utcnow(),
                    "error": "Recovered from stale running state.",
                    "error_code": "stale_running_recovered",
                }
            },
        )
        return int(getattr(result, "modified_count", 0))

    # ------------------------------------------------------------------
    # Public view (SPA-facing serializer)
    # ------------------------------------------------------------------

    @staticmethod
    def to_response(doc: dict) -> dict:
        """Project a stored Mongo doc into the API response shape.

        Internal-only fields (TTL, internal attempts counter, etc.)
        are stripped. Datetime fields are converted to ISO 8601.
        """
        def _iso(value):
            if value is None:
                return None
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value)

        return {
            "job_id": doc["job_id"],
            "status": doc["status"],
            "stage": doc.get("stage"),
            "url": doc.get("url"),
            "adapter": doc.get("adapter"),
            "created_at": _iso(doc.get("created_at")),
            "started_at": _iso(doc.get("started_at")),
            "finished_at": _iso(doc.get("finished_at")),
            "draft_id": doc.get("draft_id"),
            "approval_token": doc.get("approval_token"),
            "source_summary": doc.get("source_summary"),
            "source_metadata": doc.get("source_metadata"),
            "request_id": doc.get("request_id"),
            "error": doc.get("error"),
            "error_code": doc.get("error_code"),
        }


__all__ = ["SourceJobRepository"]