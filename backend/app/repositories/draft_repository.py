"""Draft repository — Mongo-backed CRUD.

Every operation is scoped by the authenticated ``user_id``. Cross-user
operations silently return ``None``/empty so callers respond with 404.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import COLLECTION_DRAFTS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DraftRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_DRAFTS]

    async def create(
        self,
        user_id: str,
        draft_id: str,
        *,
        topic: str,
        title: str,
        content: str,
        hashtags: list[str],
        image_path: Optional[str] = None,
        review_score: Optional[int] = None,
        review_feedback: Optional[str] = None,
        research_summary: Optional[str] = None,
        status: str = "draft",
        approval_token: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        now = _utcnow()
        doc: dict[str, Any] = {
            "_id": draft_id,
            "user_id": user_id,
            "topic": topic,
            "title": title,
            "content": content,
            "hashtags": list(hashtags or []),
            "image_path": image_path,
            "review_score": review_score,
            "review_feedback": review_feedback,
            "research_summary": research_summary,
            "status": status,
            "approval_token": approval_token,
            "approval_status": "pending" if approval_token else "none",
            "published_at": None,
            "linkedin_post_id": None,
            "created_at": now,
            "updated_at": now,
        }
        if metadata:
            doc["metadata"] = dict(metadata)
        await self.col.insert_one(doc)
        return doc

    async def get(self, user_id: str, draft_id: str) -> Optional[dict]:
        return await self.col.find_one({"_id": draft_id, "user_id": user_id})

    async def list(
        self,
        user_id: str,
        *,
        status: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        query: dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"topic": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}},
            ]
        # M11 (Phase 8C) - allow server-side ordering. Default remains
        # updated_at desc. Whitelist a small set of safe sort keys.
        sort_key = "updated_at"
        sort_direction = -1
        if sort_by == "created":
            sort_key = "created_at"
        elif sort_by == "title":
            sort_key = "title"
            sort_direction = 1  # alphabetical ascending
        cursor = (
            self.col.find(query)
            .sort(sort_key, sort_direction)
            .skip(max(0, skip))
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def count(self, user_id: str, *, status: Optional[str] = None) -> int:
        query: dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status
        return await self.col.count_documents(query)

    async def update(
        self,
        user_id: str,
        draft_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict]:
        if not updates:
            return await self.get(user_id, draft_id)
        updates = dict(updates)
        updates["updated_at"] = _utcnow()
        result = await self.col.find_one_and_update(
            {"_id": draft_id, "user_id": user_id, "published_at": None},
            {"$set": updates},
            return_document=True,
        )
        return result

    async def delete(self, user_id: str, draft_id: str) -> bool:
        result = await self.col.delete_one({"_id": draft_id, "user_id": user_id})
        return result.deleted_count == 1

    async def mark_published(
        self,
        user_id: str,
        draft_id: str,
        *,
        linkedin_post_id: str,
    ) -> Optional[dict]:
        """Phase 8B P1-9 — idempotent publish marker.

        Only flips the row from unpublished to published. A second call
        for the same draft is a no-op and returns ``None`` so the caller
        can detect "already published" without a separate query.
        """
        return await self.col.find_one_and_update(
            {"_id": draft_id, "user_id": user_id, "published_at": None},
            {
                "$set": {
                    "published_at": _utcnow(),
                    "linkedin_post_id": linkedin_post_id,
                    "status": "published",
                    "updated_at": _utcnow(),
                }
            },
            return_document=True,
        )

    async def list_published(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        cursor = (
            self.col.find({"user_id": user_id, "published_at": {"$ne": None}})
            .sort("published_at", -1)
            .skip(max(0, skip))
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]