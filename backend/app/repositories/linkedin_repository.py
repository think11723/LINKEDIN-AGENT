"""LinkedIn repository — Mongo-backed per-user OAuth tokens (encrypted at rest).

Tokens are encrypted using Fernet with a key sourced from
``LINKEDIN_TOKEN_ENCRYPTION_KEY``. The repository never returns the raw
``access_token`` or ``refresh_token`` — only safe metadata (``status``,
``person_urn``, ``expires_at``).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.core.config import Settings, get_settings
from backend.app.db.mongo import COLLECTION_LINKEDIN_ACCOUNTS

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LinkedInTokenCrypto:
    def __init__(self, key: bytes) -> None:
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> bytes:
        return self.fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> Optional[str]:
        try:
            return self.fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken:
            logger.warning("Invalid Fernet token encountered while decrypting LinkedIn credentials.")
            return None


class LinkedInRepository:
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        crypto: Optional[LinkedInTokenCrypto] = None,
    ) -> None:
        self.col = db[COLLECTION_LINKEDIN_ACCOUNTS]
        self.crypto = crypto or self._default_crypto()

    @staticmethod
    def _default_crypto() -> LinkedInTokenCrypto:
        settings = get_settings()
        key = settings.require_linkedin_encryption_key()
        return LinkedInTokenCrypto(key)

    async def upsert_tokens(
        self,
        *,
        user_id: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: Optional[datetime],
        scope: Optional[str],
        person_urn: Optional[str] = None,
    ) -> dict:
        enc_access = self.crypto.encrypt(access_token)
        enc_refresh = self.crypto.encrypt(refresh_token) if refresh_token else None
        now = _utcnow()
        doc = {
            "access_token_enc": enc_access,
            "refresh_token_enc": enc_refresh,
            "expires_at": expires_at,
            "scope": scope,
            "person_urn": person_urn,
            "connected_at": now,
            "updated_at": now,
        }
        await self.col.update_one(
            {"_id": user_id},
            {"$set": doc, "$setOnInsert": {"_id": user_id}},
            upsert=True,
        )
        return await self.get(user_id)  # type: ignore[return-value]

    async def get(self, user_id: str) -> Optional[dict]:
        return await self.col.find_one({"_id": user_id})

    async def disconnect(self, user_id: str) -> bool:
        result = await self.col.delete_one({"_id": user_id})
        return result.deleted_count == 1

    async def status(self, user_id: str) -> dict:
        record = await self.get(user_id)
        if not record:
            return {"connected": False}
        expires_at: Optional[datetime] = record.get("expires_at")
        return {
            "connected": True,
            "person_urn": record.get("person_urn"),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "scope": record.get("scope"),
        }

    async def get_decrypted_tokens(self, user_id: str) -> Optional[dict]:
        """Return plaintext tokens to internal callers only.

        MUST NOT be exposed via API responses.
        """
        record = await self.get(user_id)
        if not record:
            return None
        access = self.crypto.decrypt(record["access_token_enc"])
        if access is None:
            return None
        refresh = (
            self.crypto.decrypt(record["refresh_token_enc"])
            if record.get("refresh_token_enc")
            else None
        )
        return {
            "access_token": access,
            "refresh_token": refresh,
            "expires_at": record.get("expires_at"),
            "scope": record.get("scope"),
            "person_urn": record.get("person_urn"),
        }

    def public_view(self, user_id: str) -> dict:
        """Synchronous status helper used by routers — fetches and returns only safe fields."""
        return self.status(user_id)  # type: ignore[return-value]