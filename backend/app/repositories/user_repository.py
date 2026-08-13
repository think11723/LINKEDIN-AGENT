"""User repository.

The Firebase UID is the canonical identity. The ``users`` collection stores
a thin profile record plus optional ``profile`` and ``preferences`` sub-docs
introduced in Phase 8B P1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.core.security import AuthenticatedUser
from backend.app.db.mongo import COLLECTION_USERS


# Phase 8B P1 — explicit allowlists for $set to prevent arbitrary-key writes.
PROFILE_FIELDS: frozenset[str] = frozenset(
    {"display_name", "headline", "bio", "linkedin_url", "github_url", "avatar_url"}
)
SETTINGS_FIELDS: frozenset[str] = frozenset(
    {"publishing_mode", "approval_mode", "notification_email", "timezone"}
)


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.col = db[COLLECTION_USERS]

    async def upsert_from_auth(self, user: AuthenticatedUser) -> dict:
        """Insert-or-update a user record from a verified Firebase identity.

        Idempotent: safe to call on every authenticated request. Does not
        mutate ``created_at`` after first insert.
        """
        now = datetime.now(timezone.utc)
        update_doc = {
            "$set": {
                "email": user.email,
                "email_verified": user.email_verified,
                "name": user.name,
                "picture": user.picture,
                "updated_at": now,
            },
            "$setOnInsert": {
                "_id": user.uid,
                "created_at": now,
            },
        }
        await self.col.update_one({"_id": user.uid}, update_doc, upsert=True)
        return await self.get(user.uid)  # type: ignore[return-value]

    async def get(self, user_id: str) -> Optional[dict]:
        return await self.col.find_one({"_id": user_id})

    async def get_by_email(self, email: str) -> Optional[dict]:
        return await self.col.find_one({"email": email})

    # ------------------------------------------------------------------
    # Phase 8B P1-10 — server-side profile persistence
    # ------------------------------------------------------------------
    async def get_or_seed(self, user_id: str, *, email: str, name: str | None, email_verified: bool) -> dict:
        """Return the user doc, creating an empty one on first access.

        Phase 8C — uses ``update_one(upsert=True)`` with ``$setOnInsert``
        so two concurrent first-time requests cannot race to insert
        a duplicate document. The previously-used ``insert_one`` would
        raise ``DuplicateKeyError`` on the second request, surfacing
        as a 500.
        """
        now = datetime.now(timezone.utc)
        await self.col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "email": email,
                    "email_verified": email_verified,
                    "name": name,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        return await self.get(user_id)  # type: ignore[return-value]

    async def get_profile(self, user_id: str) -> Optional[dict]:
        # No projection — mongomock-motor is inconsistent with projection
        # semantics; the full doc is small and the projection optimization
        # is not worth the bug surface.
        return await self.col.find_one({"_id": user_id})

    async def update_profile(self, user_id: str, **fields: Any) -> Optional[dict]:
        """Read-modify-write of the ``profile`` sub-doc.

        Uses full-doc fetch + ``replace_one`` to work around a
        mongomock-motor limitation with ``$set`` on missing sub-doc paths.
        """
        if not fields:
            return await self.get_profile(user_id)
        safe = {k: v for k, v in fields.items() if k in PROFILE_FIELDS}
        if not safe:
            return await self.get_profile(user_id)
        doc = await self.col.find_one({"_id": user_id}) or {}
        merged = {**(doc.get("profile") or {}), **safe}
        new_doc = {
            **doc,
            "profile": merged,
            "updated_at": datetime.now(timezone.utc),
        }
        await self.col.replace_one({"_id": user_id}, new_doc, upsert=True)
        return await self.get_profile(user_id)

    # ------------------------------------------------------------------
    # Phase 8B P1-11 — server-side settings persistence
    # ------------------------------------------------------------------
    async def get_preferences(self, user_id: str) -> Optional[dict]:
        return await self.col.find_one({"_id": user_id})

    async def update_preferences(self, user_id: str, **fields: Any) -> Optional[dict]:
        """Read-modify-write of the ``preferences`` sub-doc.

        Uses full-doc fetch + ``replace_one`` (see ``update_profile`` for
        the rationale).
        """
        if not fields:
            return await self.get_preferences(user_id)
        safe = {k: v for k, v in fields.items() if k in SETTINGS_FIELDS}
        if not safe:
            return await self.get_preferences(user_id)
        doc = await self.col.find_one({"_id": user_id}) or {}
        merged = {**(doc.get("preferences") or {}), **safe}
        new_doc = {
            **doc,
            "preferences": merged,
            "updated_at": datetime.now(timezone.utc),
        }
        await self.col.replace_one({"_id": user_id}, new_doc, upsert=True)
        return await self.get_preferences(user_id)