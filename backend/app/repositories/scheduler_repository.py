"""Scheduler repository — Mongo-backed scheduled jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import COLLECTION_SCHEDULED_JOBS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SchedulerRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_SCHEDULED_JOBS]

    async def create(
        self,
        *,
        user_id: str,
        draft_id: Optional[str],
        title: str,
        content: str,
        hashtags: list[str],
        image_path: Optional[str],
        scheduled_time: datetime,
    ) -> dict:
        job_id = uuid.uuid4().hex
        now = _utcnow()
        doc: dict[str, Any] = {
            "_id": job_id,
            "user_id": user_id,
            "draft_id": draft_id,
            "title": title,
            "content": content,
            "hashtags": list(hashtags or []),
            "image_path": image_path,
            "scheduled_time": scheduled_time,
            "status": "pending",
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now,
            "updated_at": now,
            "last_error": None,
            "completed_at": None,
        }
        await self.col.insert_one(doc)
        return doc

    async def get(self, user_id: str, job_id: str) -> Optional[dict]:
        return await self.col.find_one({"_id": job_id, "user_id": user_id})

    async def list_for_user(
        self,
        user_id: str,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        query: dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status
        cursor = (
            self.col.find(query)
            .sort("scheduled_time", 1)
            .skip(max(0, skip))
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def count_for_user(
        self, user_id: str, *, status: Optional[str] = None
    ) -> int:
        query: dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status
        return await self.col.count_documents(query)

    async def cancel(self, user_id: str, job_id: str) -> bool:
        result = await self.col.delete_one(
            {"_id": job_id, "user_id": user_id, "status": "pending"}
        )
        return result.deleted_count == 1

    # ---- runner helpers (not user-scoped — internal) ----------------------

    async def recover_orphans(self, *, older_than_seconds: int = 600) -> int:
        """Phase 8A / P0-3: reset jobs stuck in ``status: "running"``.

        When the FastAPI process is killed mid-publish, jobs that were
        claimed (``status: "running"``) never reach ``complete_job`` /
        ``fail_job``. They stay ``running`` forever because
        :meth:`claim_due_job` only matches ``status: "pending"``.

        This helper is idempotent and safe to call on every startup.
        Any job whose ``started_at`` is older than ``older_than_seconds``
        is flipped back to ``pending`` so the runner picks it up again.

        Returns the number of jobs recovered.
        """
        from datetime import timedelta

        threshold = _utcnow() - timedelta(seconds=older_than_seconds)
        result = await self.col.update_many(
            {"status": "running", "started_at": {"$lt": threshold}},
            {
                "$set": {
                    "status": "pending",
                    "updated_at": _utcnow(),
                },
                "$inc": {"orphan_recoveries": 1},
            },
        )
        return int(getattr(result, "modified_count", 0))

    # ---- runner helpers (not user-scoped — internal) ----------------------

    async def claim_due_job(self, now: datetime) -> Optional[dict]:
        """Atomically claim a due PENDING job for execution.

        Returns ``None`` if there is nothing to do. Updates the job to
        ``RUNNING`` so concurrent ticks / restarts do not double-publish.
        """
        return await self.col.find_one_and_update(
            {"status": "pending", "scheduled_time": {"$lte": now}},
            {
                "$set": {
                    "status": "running",
                    "updated_at": _utcnow(),
                    "started_at": _utcnow(),
                }
            },
            sort=[("scheduled_time", 1)],
            return_document=True,
        )

    async def complete_job(self, job_id: str, *, linkedin_post_id: str) -> None:
        await self.col.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "linkedin_post_id": linkedin_post_id,
                    "completed_at": _utcnow(),
                    "updated_at": _utcnow(),
                    "last_error": None,
                }
            },
        )

    async def fail_job(self, job_id: str, *, error: str, retry: bool) -> None:
        if retry:
            await self.col.update_one(
                {"_id": job_id},
                {
                    "$inc": {"retry_count": 1},
                    "$set": {
                        "status": "pending",
                        "last_error": error,
                        "updated_at": _utcnow(),
                    },
                }
            )
        else:
            await self.col.update_one(
                {"_id": job_id},
                {
                    "$inc": {"retry_count": 1},
                    "$set": {
                        "status": "failed",
                        "last_error": error,
                        "completed_at": _utcnow(),
                        "updated_at": _utcnow(),
                    },
                }
            )