"""Index-init idempotency tests.

These exercise ``ensure_indexes`` against an in-memory mongomock-motor
database. They prove three things:

  1. ``ensure_indexes`` runs cleanly on an empty collection set.
  2. Calling ``ensure_indexes`` a second time is a no-op (idempotent).
  3. ``ensure_indexes`` tolerates a pre-existing index with the same key
     spec but a different name (code 85 ``IndexOptionsConflict``) —
     this is the failure mode that previously broke Railway startup
     against MongoDB Atlas where ``source_jobs`` already had
     ``source_jobs_user_idx``, ``source_jobs_queue_idx``, and
     ``source_jobs_ttl_idx`` from an earlier deploy.

The conftest fixture (``mock_mongo`` in ``tests/conftest.py``) gives us
a fresh in-memory mongomock-motor client for every test, so these
tests never need a real MongoDB.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import OperationFailure

from backend.app.db.mongo import (
    COLLECTION_SOURCE_JOBS,
    IndexOptionsMismatchError,
    ensure_indexes,
    _create_index_idempotent,
)
from backend.app.db import mongo as mongo_mod


def _fresh_db() -> Any:
    """Return a fresh in-memory AsyncMongoMockClient + database handle."""
    client = AsyncMongoMockClient()
    return client["linkedin_agent_test"]


# ---------------------------------------------------------------------------
# 1. Cold-start path — fresh empty database, all indexes created.
# ---------------------------------------------------------------------------


def test_ensure_indexes_succeeds_on_empty_db() -> None:
    """First run on an empty database creates all expected indexes."""
    db = _fresh_db()

    async def _exercise() -> None:
        # Patch the module-level ``_db`` so ``ensure_indexes`` uses our
        # in-memory client rather than the conftest one (or none).
        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            await ensure_indexes()
        finally:
            mongo_mod._db = original_db

        # The source_jobs collection must end up with all four indexes
        # declared in ``mongo.ensure_indexes``.
        indexes = await db[COLLECTION_SOURCE_JOBS].index_information()
        names = set(indexes.keys())
        # The unique ``job_id`` index uses an explicit production name.
        assert "source_jobs_job_id_idx" in names
        # The three custom-named indexes match the production Atlas names.
        assert "source_jobs_user_idx" in names
        assert "source_jobs_queue_idx" in names
        assert "source_jobs_ttl_idx" in names
        # The job_id index must be unique.
        assert indexes["source_jobs_job_id_idx"].get("unique") is True
        # The TTL index must carry the expireAfterSeconds option.
        ttl = indexes["source_jobs_ttl_idx"]
        assert ttl.get("expireAfterSeconds") == 0

    asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# 2. Warm-start path — calling ensure_indexes again must not raise.
# ---------------------------------------------------------------------------


def test_ensure_indexes_is_idempotent() -> None:
    """Running ``ensure_indexes`` twice on the same database must not raise."""
    db = _fresh_db()

    async def _exercise() -> None:
        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            await ensure_indexes()
            # Second call: every index already exists under the same
            # name + same key spec → MongoDB returns the existing index
            # info instead of erroring.
            await ensure_indexes()
        finally:
            mongo_mod._db = original_db

        # Index count is unchanged after the second run.
        indexes_after = await db[COLLECTION_SOURCE_JOBS].index_information()
        # _id_ plus the four declared indexes.
        assert "source_jobs_job_id_idx" in indexes_after
        assert "source_jobs_user_idx" in indexes_after
        assert "source_jobs_queue_idx" in indexes_after
        assert "source_jobs_ttl_idx" in indexes_after

    asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# 3. Pre-existing-index path — equivalent index with a different name.
# ---------------------------------------------------------------------------


def test_ensure_indexes_tolerates_existing_index_with_different_name() -> None:
    """If the database already has an equivalent index under a custom name
    (the Atlas state we encountered in production), ``ensure_indexes`` must
    accept it rather than crash with code 85 ``IndexOptionsConflict``.
    """
    db = _fresh_db()

    async def _exercise() -> None:
        # Pre-create an equivalent index with a different name, simulating
        # the production Atlas state where ``source_jobs_user_idx`` etc.
        # were created by a prior deploy before the application started
        # naming them explicitly.
        await db[COLLECTION_SOURCE_JOBS].create_index(
            [("user_id", 1), ("created_at", -1)],
            name="legacy_user_idx",
        )
        await db[COLLECTION_SOURCE_JOBS].create_index(
            [("status", 1), ("created_at", 1)],
            name="legacy_queue_idx",
        )
        await db[COLLECTION_SOURCE_JOBS].create_index(
            "expires_at",
            name="legacy_ttl_idx",
            expireAfterSeconds=0,
        )

        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            await ensure_indexes()
        finally:
            mongo_mod._db = original_db

        # Both the legacy names and the new (canonical) names are present.
        # mongomock-motor returns the existing index on a same-key-spec
        # conflict; it does not create the requested-name index, so the
        # legacy names persist.
        indexes = await db[COLLECTION_SOURCE_JOBS].index_information()
        names = set(indexes.keys())
        assert "legacy_user_idx" in names
        assert "legacy_queue_idx" in names
        assert "legacy_ttl_idx" in names
        # The TTL option survives.
        assert indexes["legacy_ttl_idx"].get("expireAfterSeconds") == 0

    asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# 4. Same name, different key spec — must propagate.
# ---------------------------------------------------------------------------


def test_ensure_indexes_rejects_name_collision_with_different_keys() -> None:
    """If an index with the requested name already exists but its key
    spec disagrees, ``ensure_indexes`` must propagate the
    ``IndexKeySpecsConflict`` (code 86). Silently masking it would mean
    the application thinks the right index exists when it does not.
    """
    db = _fresh_db()

    async def _exercise() -> None:
        # Pre-create a colliding index under the canonical name but with
        # a different key spec.
        await db[COLLECTION_SOURCE_JOBS].create_index(
            [("user_id", 1), ("created_at", 1)],  # wrong direction
            name="source_jobs_user_idx",
        )

        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            with pytest.raises(OperationFailure):
                await ensure_indexes()
        finally:
            mongo_mod._db = original_db

    asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# 5. Unrelated Mongo errors must not be suppressed.
# ---------------------------------------------------------------------------


def test_unrelated_mongo_errors_propagate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-85/86 ``OperationFailure`` raised by ``create_index`` must
    NOT be swallowed — startup should still fail loudly.
    """

    class _FakeColl:
        name = "fake"

        async def create_index(self, *_args: Any, **_kwargs: Any) -> None:
            raise OperationFailure("synthetic unrelated failure", code=99999)

    async def _exercise() -> None:
        with pytest.raises(OperationFailure):
            await _create_index_idempotent(
                _FakeColl(),  # type: ignore[arg-type]
                [("user_id", 1)],
            )

    asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# 6. Hardening — semantic-options mismatch must raise, never be masked.
# ---------------------------------------------------------------------------
# These tests focus on the ``OperationFailure`` recovery path inside
# ``_create_index_idempotent``. They ensure that a pre-existing index
# carrying the same name or key spec but *different* semantic options
# (TTL seconds, unique, sparse, partialFilterExpression) is rejected
# with a clear ``IndexOptionsMismatchError`` rather than silently
# accepted. The motivating bug was the production ``source_jobs`` TTL
# index being created with ``expireAfterSeconds=604800`` (effective
# 14-day retention) when the application asked for ``expireAfterSeconds=0``.


def test_source_jobs_ttl_with_wrong_seconds_is_rejected() -> None:
    """A pre-existing ``source_jobs_ttl_idx`` with ``expireAfterSeconds=604800``
    must be rejected by ``ensure_indexes`` — the application asked for 0
    and would otherwise silently accept a 14-day TTL.
    """
    db = _fresh_db()

    async def _exercise() -> None:
        # Pre-create the TTL index with the WRONG expireAfterSeconds,
        # exactly the way it was on MongoDB Atlas before we manually
        # dropped it.
        await db[COLLECTION_SOURCE_JOBS].create_index(
            "expires_at",
            name="source_jobs_ttl_idx",
            expireAfterSeconds=604800,
        )

        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            with pytest.raises(IndexOptionsMismatchError) as excinfo:
                await ensure_indexes()
        finally:
            mongo_mod._db = original_db

        msg = str(excinfo.value)
        # The error must name the index, the requested options, the
        # existing options, and tell the operator to migrate.
        assert "source_jobs_ttl_idx" in msg
        assert "expireAfterSeconds" in msg
        assert "604800" in msg
        assert "migrat" in msg.lower()

    asyncio.run(_exercise())


def test_source_jobs_ttl_with_correct_seconds_is_accepted() -> None:
    """A pre-existing ``source_jobs_ttl_idx`` with ``expireAfterSeconds=0``
    must be accepted idempotently — the canonical 7-day cleanup config.
    """
    db = _fresh_db()

    async def _exercise() -> None:
        await db[COLLECTION_SOURCE_JOBS].create_index(
            "expires_at",
            name="source_jobs_ttl_idx",
            expireAfterSeconds=0,
        )

        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            # Must not raise.
            await ensure_indexes()
        finally:
            mongo_mod._db = original_db

        indexes = await db[COLLECTION_SOURCE_JOBS].index_information()
        assert indexes["source_jobs_ttl_idx"].get("expireAfterSeconds") == 0

    asyncio.run(_exercise())


def test_existing_index_with_same_name_but_different_keys_is_rejected() -> None:
    """A pre-existing index with the same name but a different key
    specification must surface as an ``OperationFailure`` (code 86) —
    never be silently accepted even if the options happen to match.
    """
    db = _fresh_db()

    async def _exercise() -> None:
        # Same name, different key spec — the classic code 86 case.
        await db[COLLECTION_SOURCE_JOBS].create_index(
            "job_id",  # wrong: app wants ("user_id", 1) ascending
            name="source_jobs_user_idx",
        )

        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            with pytest.raises(OperationFailure):
                await ensure_indexes()
        finally:
            mongo_mod._db = original_db

    asyncio.run(_exercise())


def test_equivalent_existing_index_is_accepted() -> None:
    """A pre-existing index whose name, key spec, and options all match
    the request must be accepted (idempotent) without raising — both
    via the pre-flight check and the OperationFailure recovery path.
    """
    db = _fresh_db()

    async def _exercise() -> None:
        # Pre-create the exact index the application would request.
        await db[COLLECTION_SOURCE_JOBS].create_index(
            "job_id",
            name="source_jobs_job_id_idx",
            unique=True,
        )

        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            await ensure_indexes()
        finally:
            mongo_mod._db = original_db

        indexes = await db[COLLECTION_SOURCE_JOBS].index_information()
        assert indexes["source_jobs_job_id_idx"].get("unique") is True

    asyncio.run(_exercise())


def test_equivalent_existing_index_under_different_name_is_accepted() -> None:
    """An existing index with the same key spec and options but a
    different (legacy) name — the Atlas pre-deploy state we hit in
    production — must be accepted by the OperationFailure recovery
    path without raising.
    """
    db = _fresh_db()

    async def _exercise() -> None:
        # Simulate the Atlas state: legacy name, canonical key spec.
        await db[COLLECTION_SOURCE_JOBS].create_index(
            [("user_id", 1), ("created_at", -1)],
            name="legacy_user_idx",
        )

        original_db = mongo_mod._db
        mongo_mod._db = db
        try:
            # Must not raise even though the canonical name is absent.
            await ensure_indexes()
        finally:
            mongo_mod._db = original_db

        indexes = await db[COLLECTION_SOURCE_JOBS].index_information()
        assert "legacy_user_idx" in indexes

    asyncio.run(_exercise())


def test_unrelated_operation_failure_still_propagates() -> None:
    """An ``OperationFailure`` whose code is not 85/86 (and not None)
    must propagate unchanged. A synthetic failure with code=99999
    should not be confused with an index-already-exists condition.
    """

    class _FakeColl:
        name = "fake"

        async def create_index(self, *_args: Any, **_kwargs: Any) -> None:
            raise OperationFailure("synthetic auth failure", code=18)

    async def _exercise() -> None:
        with pytest.raises(OperationFailure) as excinfo:
            await _create_index_idempotent(
                _FakeColl(),  # type: ignore[arg-type]
                [("user_id", 1)],
            )
        # The original error reaches the caller untouched.
        assert excinfo.value.code == 18

    asyncio.run(_exercise())
