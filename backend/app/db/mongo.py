"""MongoDB client lifecycle (Motor) wired into FastAPI's lifespan."""

from __future__ import annotations

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from backend.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

COLLECTION_USERS = "users"
COLLECTION_DRAFTS = "drafts"
COLLECTION_APPROVALS = "approvals"
COLLECTION_SCHEDULED_JOBS = "scheduled_jobs"
COLLECTION_LINKEDIN_ACCOUNTS = "linkedin_accounts"
COLLECTION_OAUTH_STATES = "oauth_states"
COLLECTION_AUDIT_EVENTS = "audit_events"

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def init_mongo(settings: Optional[Settings] = None) -> AsyncIOMotorDatabase:
    """Initialise the global Mongo client. Fails loudly if Mongo is unreachable."""
    global _client, _db

    cfg = settings or get_settings()
    cfg.require_mongo()

    if _client is not None and _db is not None:
        return _db

    _client = AsyncIOMotorClient(
        cfg.mongodb_uri,
        serverSelectionTimeoutMS=5000,
        uuidRepresentation="standard",
    )
    _db = _client[cfg.mongodb_db_name]
    logger.info(
        "MongoDB client initialised against database %s", cfg.mongodb_db_name
    )
    return _db


def get_database() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError(
            "MongoDB is not initialised. Call init_mongo() during startup."
        )
    return _db


async def ping_mongo() -> None:
    """Ping the Mongo server; raises if unreachable."""
    db = get_database()
    await db.command("ping")


async def close_mongo() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None
    logger.info("MongoDB client closed.")


async def ensure_indexes() -> None:
    """Create the indexes required for user-scoped lookups."""
    db = get_database()

    # users --------------------------------------------------------------
    await db[COLLECTION_USERS].create_index("email", sparse=True)

    # drafts --------------------------------------------------------------
    await db[COLLECTION_DRAFTS].create_index([("user_id", 1), ("updated_at", -1)])
    await db[COLLECTION_DRAFTS].create_index([("user_id", 1), ("status", 1)])
    await db[COLLECTION_DRAFTS].create_index(
        [("user_id", 1), ("title", "text"), ("topic", "text")],
        name="drafts_user_text",
    )

    # approvals -----------------------------------------------------------
    await db[COLLECTION_APPROVALS].create_index("token", unique=True)
    await db[COLLECTION_APPROVALS].create_index([("user_id", 1), ("draft_id", 1)])
    await db[COLLECTION_APPROVALS].create_index([("user_id", 1), ("status", 1)])

    # scheduled_jobs ------------------------------------------------------
    await db[COLLECTION_SCHEDULED_JOBS].create_index(
        [("user_id", 1), ("scheduled_time", 1)]
    )
    await db[COLLECTION_SCHEDULED_JOBS].create_index(
        [("status", 1), ("scheduled_time", 1)]
    )

    # linkedin_accounts ---------------------------------------------------
    await db[COLLECTION_LINKEDIN_ACCOUNTS].create_index("expires_at")

    # oauth_states --------------------------------------------------------
    await db[COLLECTION_OAUTH_STATES].create_index("expires_at", expireAfterSeconds=0)
    await db[COLLECTION_OAUTH_STATES].create_index("state", unique=True)

    # audit_events --------------------------------------------------------
    await db[COLLECTION_AUDIT_EVENTS].create_index(
        [("user_id", 1), ("timestamp", -1)]
    )

    logger.info("MongoDB indexes ensured.")