"""MongoDB client lifecycle (Motor) wired into FastAPI's lifespan."""

from __future__ import annotations

import logging
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import OperationFailure

from backend.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# MongoDB error codes raised when ``create_index`` collides with an index
# that already exists on the collection.
#   85 — IndexOptionsConflict: same key spec, different name (or partial
#        option differs). An equivalent index already exists; we may
#        safely reuse it rather than fail startup.
#   86 — IndexKeySpecsConflict: same name, different key spec. This is a
#        real mismatch and is NOT silently swallowed.
_INDEX_ALREADY_EXISTS_CODES = frozenset({85, 86})

COLLECTION_USERS = "users"
COLLECTION_DRAFTS = "drafts"
COLLECTION_APPROVALS = "approvals"
COLLECTION_SCHEDULED_JOBS = "scheduled_jobs"
COLLECTION_LINKEDIN_ACCOUNTS = "linkedin_accounts"
COLLECTION_OAUTH_STATES = "oauth_states"
COLLECTION_AUDIT_EVENTS = "audit_events"
COLLECTION_SOURCE_JOBS = "source_jobs"  # Phase 8D / URL-to-LinkedIn
COLLECTION_RESUMES = "resumes"  # Phase 10 / AI Resume Studio
COLLECTION_ATS_ANALYSES = "ats_analyses"  # Phase 10 / AI Resume Studio

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def init_mongo(
    settings: Optional[Settings] = None,
) -> AsyncIOMotorDatabase:
    """Initialise the global Mongo client. Fails loudly if unreachable."""
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


async def _create_index_idempotent(
    collection: Any,
    keys: Any,
    *,
    name: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """Create an index; tolerate a pre-existing equivalent index.

    Behaviour:
      * Pre-existing index whose name + key spec + options match the
        request → skip (true no-op, idempotent on both real MongoDB
        and in-memory test doubles).
      * Pre-existing index with the same name but *different* key spec
        → re-raise ``OperationFailure`` (code 86). This is a real
        schema mismatch and must not be silently masked.
      * Pre-existing index with the same key spec but a *different*
        name → log a warning and accept the existing index. Production
        databases sometimes pre-create indexes under a custom name; we
        must not fail startup over that.
      * Any other ``OperationFailure`` propagates unchanged.

    The pre-check covers the common idempotency case (subsequent
    startups). The ``OperationFailure`` catch covers the remaining
    race-condition case where a sibling process / startup created an
    equivalent index between the pre-check and our create_index call.
    """
    existing = await _find_equivalent_index(collection, keys, name, **kwargs)
    if existing is not None:
        logger.info(
            "Index already present on %s (name=%r keys=%r); skipping.",
            collection.name,
            existing.get("name"),
            keys,
        )
        return

    try:
        await collection.create_index(keys, name=name, **kwargs)
    except OperationFailure as exc:
        code = getattr(exc, "code", None)
        if code is not None and code not in _INDEX_ALREADY_EXISTS_CODES:
            # Unrelated error (auth, network, …) — surface it.
            raise

        # MongoDB rejected the create because an index with the same
        # name or same key spec already exists. Re-inspect to decide
        # whether to accept (equivalent) or refuse (semantic mismatch).
        requested_keys = _normalize_keys(keys)
        existing = await _find_conflicting_index(
            collection, keys, name, **kwargs
        )
        if existing is None:
            # No conflicting index found via introspection (e.g. the
            # error came from a transient race we can no longer
            # observe). Surface the original failure rather than mask it.
            raise

        existing_name = existing.get("name")
        existing_keys = _normalize_keys(
            existing.get("key", existing.get("keys"))
        )

        # If the same name was given but the key spec differs, this is
        # a real schema mismatch (code 86) — never mask it.
        if (
            name is not None
            and existing_name == name
            and existing_keys != requested_keys
        ):
            raise

        # Same key spec (matched by name or by key list) — compare
        # semantic options. If they match we accept the existing
        # index; if they differ we refuse with a clear error so the
        # operator can migrate it.
        if _index_options_match(existing, keys, kwargs):
            logger.info(
                "Index already present on %s (name=%r); reusing.",
                collection.name,
                existing_name,
            )
            return

        existing_opts = {
            k: v
            for k, v in existing.items()
            if k not in {"key", "keys", "v", "ns"}
        }
        requested_opts = {k: v for k, v in kwargs.items() if v is not None}
        raise IndexOptionsMismatchError(
            collection_name=collection.name,
            index_name=name,
            existing_name=existing_name,
            existing_keys=existing_keys,
            requested_keys=requested_keys,
            existing_options=existing_opts,
            requested_options=requested_opts,
            original_error=exc,
        )


async def _find_conflicting_index(
    collection: Any,
    keys: Any,
    name: Optional[str],
    **kwargs: Any,
) -> Optional[dict]:
    """Return the existing index that conflicts with the requested one.

    "Conflict" here means the same name OR the same key spec — the two
    conditions under which ``create_index`` raises
    ``IndexOptionsConflict`` (code 85) on a real MongoDB server.

    Used only inside the ``OperationFailure`` recovery path. The
    idempotent pre-flight check (``_find_equivalent_index``) is what
    we normally rely on; this function exists so the recovery path can
    decide whether a race-condition failure is benign (the index
    already exists and matches) or hard (semantic option mismatch —
    e.g. ``expireAfterSeconds`` drift on a TTL index).
    """
    try:
        info = await collection.index_information()
    except Exception:  # noqa: BLE001
        return None

    requested_keys = _normalize_keys(keys)

    # 1) Same name wins — that's the most explicit conflict.
    if name is not None and name in info and name != "_id_":
        spec = dict(info[name])
        spec.setdefault("name", name)
        return spec

    # 2) Same key spec under a different name (Atlas / legacy state).
    for existing_name, spec in info.items():
        if existing_name == "_id_":
            continue
        existing_keys = _normalize_keys(spec.get("key", spec.get("keys")))
        if existing_keys == requested_keys:
            enriched = dict(spec)
            enriched.setdefault("name", existing_name)
            return enriched
    return None


def _index_options_match(
    existing: dict, keys: Any, requested_kwargs: dict
) -> bool:
    """Return True iff ``existing`` carries the same semantic options.

    Used by the ``OperationFailure`` recovery path. A real MongoDB
    server considers two indexes "equivalent" for the purposes of
    ``create_index`` only if the key spec *and* the semantic options
    (``unique``, ``sparse``, ``expireAfterSeconds``,
    ``partialFilterExpression``) match.
    """
    existing_opts = _normalize_index_options(
        {
            k: v
            for k, v in existing.items()
            if k not in {"key", "keys", "v", "ns"}
        }
    )
    requested_opts = _normalize_index_options(requested_kwargs)
    return existing_opts == requested_opts


class IndexOptionsMismatchError(RuntimeError):
    """Raised when an existing index collides on name or key spec
    but has different semantic options (TTL seconds, unique, sparse,
    partialFilterExpression, …).

    We refuse to silently accept such a state because the application
    would otherwise believe the index has the requested semantics
    (e.g. a 7-day TTL) when the existing one differs (e.g. a 14-day
    TTL — the very bug that motivated this hardening). The operator
    must explicitly migrate the index.
    """

    def __init__(
        self,
        *,
        collection_name: str,
        index_name: Optional[str],
        existing_name: Optional[str],
        existing_keys: list,
        requested_keys: list,
        existing_options: dict,
        requested_options: dict,
        original_error: Exception,
    ) -> None:
        self.collection_name = collection_name
        self.index_name = index_name
        self.existing_name = existing_name
        self.existing_keys = existing_keys
        self.requested_keys = requested_keys
        self.existing_options = existing_options
        self.requested_options = requested_options
        self.original_error = original_error
        super().__init__(self._format())

    def _format(self) -> str:
        return (
            f"Index options conflict on collection {self.collection_name!r} "
            f"for index {self.index_name!r}: an existing index with the "
            f"same name or key spec has different semantic options and "
            f"must be migrated before the application can start. "
            f"existing_name={self.existing_name!r} "
            f"existing_keys={self.existing_keys!r} "
            f"existing_options={self.existing_options!r} "
            f"requested_name={self.index_name!r} "
            f"requested_keys={self.requested_keys!r} "
            f"requested_options={self.requested_options!r}. "
            f"Drop or rebuild the existing index to match the requested "
            f"definition. Original error: {self.original_error!r}."
        )


async def _find_equivalent_index(
    collection: Any,
    keys: Any,
    name: Optional[str],
    **kwargs: Any,
) -> Optional[dict]:
    """Return the existing index spec if one matches by name OR by key spec.

    The match is structural — we compare the requested key list and
    options (``unique``, ``expireAfterSeconds``, ``sparse``,
    ``partialFilterExpression``, …) against every existing index and
    return the first one that matches. Returning ``None`` means there
    is no equivalent index and ``create_index`` must be called.
    """
    # Normalise keys to a list-of-tuples for comparison.
    requested_keys = _normalize_keys(keys)
    requested_opts = _normalize_index_options(kwargs)

    # ``index_information`` is the canonical way to introspect indexes
    # without needing ``list_indexes`` cursor support.
    try:
        info = await collection.index_information()
    except Exception:  # noqa: BLE001
        return None

    for existing_name, spec in info.items():
        # Skip the implicit _id_ index — it is not under our control.
        if existing_name == "_id_":
            continue
        existing_keys = _normalize_keys(spec.get("key", spec.get("keys")))
        if existing_keys != requested_keys:
            continue
        existing_opts = _normalize_index_options(
            {
                k: v
                for k, v in spec.items()
                if k not in {"key", "keys", "v", "ns"}
            }
        )
        if existing_opts != requested_opts:
            # Same key spec but different options (uniqueness, TTL,
            # partial filter, etc.). That's a real conflict — let the
            # caller's create_index path surface it.
            continue
        return spec
    return None


def _normalize_keys(keys: Any) -> list:
    """Coerce keys into a comparable list of (field, direction) tuples.

    Direction may be ``1``/``-1`` for standard indexes or the string
    ``"text"`` for a MongoDB text index. Both forms are returned
    unchanged so structural equality works in ``_find_equivalent_index``.
    """
    if isinstance(keys, str):
        return [(keys, 1)]
    if isinstance(keys, dict):
        return [(k, v) for k, v in keys.items()]
    if isinstance(keys, list):
        out = []
        for k, v in keys:
            try:
                out.append((k, int(v)))
            except (TypeError, ValueError):
                out.append((k, v))
        return out
    return list(keys)


def _normalize_index_options(opts: dict) -> dict:
    """Strip ``None`` values and drop fields that are not user-controlled."""
    cleaned: dict = {}
    for k, v in opts.items():
        if v is None:
            continue
        if k in {"v", "ns", "background", "key", "keys"}:
            continue
        cleaned[k] = v
    return cleaned


async def ensure_indexes() -> None:
    """Create the indexes required for user-scoped lookups.

    Idempotent against pre-existing indexes on production MongoDB
    (Atlas may have indexes created under custom names by prior
    deploys or migrations — those are reused, not recreated).

    Every index is created with an explicit ``name``. This is required
    by the in-memory ``mongomock-motor`` test double, which stores an
    index with ``name=None`` when no name is given and then raises
    ``OperationFailure`` when a second index on the same collection is
    requested without a name. Real MongoDB tolerates ``name=None``
    (it auto-generates one) but the production-vs-test asymmetry makes
    bugs harder to catch, so we name every index explicitly here.
    """
    db = get_database()

    # users --------------------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_USERS], "email", name="users_email_idx", sparse=True
    )

    # drafts --------------------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_DRAFTS],
        [("user_id", 1), ("updated_at", -1)],
        name="drafts_user_updated_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_DRAFTS],
        [("user_id", 1), ("status", 1)],
        name="drafts_user_status_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_DRAFTS],
        [("user_id", 1), ("title", "text"), ("topic", "text")],
        name="drafts_user_text",
    )

    # approvals -----------------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_APPROVALS],
        "token",
        name="approvals_token_idx",
        unique=True,
    )
    await _create_index_idempotent(
        db[COLLECTION_APPROVALS],
        [("user_id", 1), ("draft_id", 1)],
        name="approvals_user_draft_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_APPROVALS],
        [("user_id", 1), ("status", 1)],
        name="approvals_user_status_idx",
    )

    # scheduled_jobs ------------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_SCHEDULED_JOBS],
        [("user_id", 1), ("scheduled_time", 1)],
        name="scheduled_jobs_user_time_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_SCHEDULED_JOBS],
        [("status", 1), ("scheduled_time", 1)],
        name="scheduled_jobs_status_time_idx",
    )

    # linkedin_accounts ---------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_LINKEDIN_ACCOUNTS],
        "expires_at",
        name="linkedin_accounts_expires_idx",
    )

    # oauth_states --------------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_OAUTH_STATES],
        "expires_at",
        name="oauth_states_expires_idx",
        expireAfterSeconds=0,
    )
    await _create_index_idempotent(
        db[COLLECTION_OAUTH_STATES],
        "state",
        name="oauth_states_state_idx",
        unique=True,
    )

    # audit_events --------------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_AUDIT_EVENTS],
        [("user_id", 1), ("timestamp", -1)],
        name="audit_events_user_time_idx",
    )

    # source_jobs --------------------------------------------------------
    # Phase 8D / URL-to-LinkedIn.
    # Index names match the existing production indexes in MongoDB Atlas:
    #   source_jobs_job_id_idx — unique on ``job_id``
    #   source_jobs_user_idx   — user-scoped history
    #   source_jobs_queue_idx  — runner claim query
    #   source_jobs_ttl_idx    — TTL on ``expires_at`` (7-day cleanup)
    # Explicit names let ``create_index`` resolve to the existing index
    # when present (same name + same key spec → no-op) and stay valid on
    # fresh databases where Atlas has not yet created them.
    await _create_index_idempotent(
        db[COLLECTION_SOURCE_JOBS],
        "job_id",
        name="source_jobs_job_id_idx",
        unique=True,
    )
    await _create_index_idempotent(
        db[COLLECTION_SOURCE_JOBS],
        [("user_id", 1), ("created_at", -1)],
        name="source_jobs_user_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_SOURCE_JOBS],
        [("status", 1), ("created_at", 1)],
        name="source_jobs_queue_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_SOURCE_JOBS],
        "expires_at",
        name="source_jobs_ttl_idx",
        expireAfterSeconds=0,
    )

    # resumes (Phase 10) -------------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_RESUMES],
        [("user_id", 1), ("updated_at", -1)],
        name="resumes_user_updated_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_RESUMES],
        [("user_id", 1), ("title", 1)],
        name="resumes_user_title_idx",
    )

    # ats_analyses (Phase 10) ---------------------------------------------
    await _create_index_idempotent(
        db[COLLECTION_ATS_ANALYSES],
        [("user_id", 1), ("resume_id", 1), ("created_at", -1)],
        name="ats_analyses_user_resume_time_idx",
    )
    await _create_index_idempotent(
        db[COLLECTION_ATS_ANALYSES],
        [("user_id", 1), ("created_at", -1)],
        name="ats_analyses_user_time_idx",
    )

    logger.info("MongoDB indexes ensured.")
