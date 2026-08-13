"""OAuth state repository.

Stores short-lived state nonces that bind a LinkedIn OAuth callback to
the Firebase user who initiated the flow. TTL index on ``expires_at``
ensures automatic cleanup.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.db.mongo import COLLECTION_OAUTH_STATES


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OAuthStateRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_OAUTH_STATES]

    @staticmethod
    def generate_state() -> str:
        return secrets.token_urlsafe(32)

    async def create(
        self,
        *,
        user_id: str,
        code_verifier: str,
        ttl_seconds: int = 600,
    ) -> dict:
        now = _utcnow()
        state = self.generate_state()
        doc: dict[str, Any] = {
            "_id": state,
            "state": state,
            "user_id": user_id,
            "code_verifier": code_verifier,
            "created_at": now,
            "expires_at": now + timedelta(seconds=ttl_seconds),
            "consumed": False,
        }
        await self.col.insert_one(doc)
        return doc

    async def consume(self, state: str) -> Optional[dict]:
        """Atomically read + mark consumed.

        Returns ``None`` if the state does not exist, has expired, has
        already been used, or the TTL has not yet expired.
        """
        now = _utcnow()
        return await self.col.find_one_and_update(
            {"_id": state, "consumed": False, "expires_at": {"$gt": now}},
            {"$set": {"consumed": True, "consumed_at": now}},
            return_document=True,
        )

    async def delete(self, state: str) -> None:
        await self.col.delete_one({"_id": state})