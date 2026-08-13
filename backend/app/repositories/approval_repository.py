"""Approval repository — Mongo-backed tokens + idempotent actions.

The legacy ``approval/store.py`` + JSON file store is preserved for the CLI.
The SaaS path uses this repository exclusively.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import COLLECTION_APPROVALS


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(record: Optional[dict]) -> bool:
    """Return True if the approval record has an ``expires_at`` in the past.

    Records missing ``expires_at`` are treated as non-expiring (legacy data).
    Naive datetimes are interpreted as UTC.
    """
    if not record:
        return False
    expires_at = record.get("expires_at")
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _utcnow()


def _strip_expired(record: Optional[dict]) -> Optional[dict]:
    """Return the record only if it exists AND has not expired."""
    if record is None:
        return None
    if _is_expired(record):
        return None
    return record


class ApprovalRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_APPROVALS]

    @staticmethod
    def generate_token() -> str:
        # URL-safe, ~190 bits of entropy; UUID4 was used previously but token() is
        # explicitly supported by secrets and is shorter.
        return secrets.token_urlsafe(24)

    @staticmethod
    def is_expired(record: Optional[dict]) -> bool:
        """Public helper — exposes ``_is_expired`` for callers / tests."""
        return _is_expired(record)

    async def create(
        self,
        *,
        user_id: str,
        draft_id: str,
        expires_at: Optional[datetime] = None,
    ) -> dict:
        now = _utcnow()
        token = self.generate_token()
        doc: dict[str, Any] = {
            "_id": token,
            "token": token,
            "user_id": user_id,
            "draft_id": draft_id,
            "status": "pending",
            "used": False,
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at or (now + timedelta(hours=24)),
        }
        await self.col.insert_one(doc)
        return doc

    async def get(self, user_id: str, token: str) -> Optional[dict]:
        """Return the token record only if it is owned by ``user_id`` AND not expired.

        Phase 8A / P0-4: expired tokens are treated as not-found so the
        SPA cannot act on them, even though the Mongo row still exists.
        """
        record = await self.col.find_one({"_id": token, "user_id": user_id})
        return _strip_expired(record)

    async def get_for_user(self, user_id: str, token: str) -> Optional[dict]:
        """Used by /approval/draft — the caller must own the token."""
        return await self.get(user_id, token)

    async def list_for_drafts(
        self,
        user_id: str,
        draft_ids: list[str],
        *,
        status: Optional[str] = None,
    ) -> list[dict]:
        query: dict[str, Any] = {"user_id": user_id, "draft_id": {"$in": draft_ids}}
        if status:
            query["status"] = status
        cursor = self.col.find(query)
        return [doc async for doc in cursor]

    async def list_pending_for_user(
        self,
        user_id: str,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[dict]:
        cursor = (
            self.col.find({"user_id": user_id, "status": "pending"})
            .sort("created_at", -1)
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

    async def approve(self, user_id: str, token: str) -> Optional[dict]:
        """Idempotent approve. Returns None if token is missing, owned by
        another user, expired, or already-rejected.

        Already-approved records return the existing record unchanged —
        we do not double-fire publish.
        """
        record = await self.get(user_id, token)
        if not record:
            return None
        if record.get("status") == "rejected":
            return None  # rejected is terminal; refuse to flip back to approved
        if record.get("status") == "approved":
            return record
        return await self.col.find_one_and_update(
            {"_id": token, "user_id": user_id},
            {
                "$set": {
                    "status": "approved",
                    "used": True,
                    "updated_at": _utcnow(),
                    "approved_at": _utcnow(),
                }
            },
            return_document=True,
        )

    async def reject(self, user_id: str, token: str) -> Optional[dict]:
        record = await self.get(user_id, token)
        if not record:
            return None
        if record.get("status") == "rejected":
            return record
        if record.get("status") == "approved":
            # Do not silently overwrite an approved token. Reject must be a
            # separate, explicit decision by the operator.
            return None
        return await self.col.find_one_and_update(
            {"_id": token, "user_id": user_id},
            {
                "$set": {
                    "status": "rejected",
                    "used": True,
                    "updated_at": _utcnow(),
                    "rejected_at": _utcnow(),
                }
            },
            return_document=True,
        )

    async def list_for_draft(self, user_id: str, draft_id: str) -> list[dict]:
        cursor = self.col.find({"user_id": user_id, "draft_id": draft_id}).sort(
            "created_at", -1
        )
        return [doc async for doc in cursor]

    async def latest_for_draft(
        self, user_id: str, draft_id: str
    ) -> Optional[dict]:
        cursor = (
            self.col.find({"user_id": user_id, "draft_id": draft_id})
            .sort("created_at", -1)
            .limit(1)
        )
        async for doc in cursor:
            return doc
        return None