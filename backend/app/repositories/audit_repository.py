"""Audit repository — per-user activity log."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import COLLECTION_AUDIT_EVENTS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_AUDIT_EVENTS]

    async def log(
        self,
        *,
        user_id: str,
        event_type: str,
        description: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        await self.col.insert_one(
            {
                "user_id": user_id,
                "event_type": event_type,
                "description": description,
                "details": details or {},
                "timestamp": _utcnow(),
            }
        )

    async def list_recent(
        self, user_id: str, *, limit: int = 12
    ) -> list[dict]:
        cursor = (
            self.col.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(max(1, min(200, limit)))
        )
        return [doc async for doc in cursor]

    async def count_recent(self, user_id: str, *, limit: int = 12) -> int:
        cursor = (
            self.col.find({"user_id": user_id})
            .sort("timestamp", -1)
            .limit(max(1, min(200, limit)))
        )
        return sum(1 async for _ in cursor)