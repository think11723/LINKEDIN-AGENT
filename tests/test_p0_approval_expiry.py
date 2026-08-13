"""Tests for Phase 8A P0-4: approval token expiry."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.db.mongo import get_database
from backend.app.repositories.approval_repository import ApprovalRepository


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _seed(repo: ApprovalRepository, *, expires_at: datetime) -> str:
    record = await repo.create(
        user_id="USER_A",
        draft_id="draft-1",
        expires_at=expires_at,
    )
    return record["_id"]


def test_get_returns_valid_token():
    repo = ApprovalRepository(get_database())
    future = _utcnow() + timedelta(hours=1)
    token = asyncio.run(_seed(repo, expires_at=future))
    record = asyncio.run(repo.get("USER_A", token))
    assert record is not None
    assert record["_id"] == token


def test_get_returns_none_for_expired_token():
    repo = ApprovalRepository(get_database())
    past = _utcnow() - timedelta(seconds=1)
    token = asyncio.run(_seed(repo, expires_at=past))
    record = asyncio.run(repo.get("USER_A", token))
    assert record is None, "Expired token must NOT be returned by get()."


def test_approve_rejects_expired_token():
    repo = ApprovalRepository(get_database())
    past = _utcnow() - timedelta(seconds=1)
    token = asyncio.run(_seed(repo, expires_at=past))
    result = asyncio.run(repo.approve("USER_A", token))
    assert result is None

    # Verify the underlying row was NOT mutated.
    raw = asyncio.run(repo.col.find_one({"_id": token}))
    assert raw["status"] == "pending", "Expired token must remain pending."


def test_reject_rejects_expired_token():
    repo = ApprovalRepository(get_database())
    past = _utcnow() - timedelta(seconds=1)
    token = asyncio.run(_seed(repo, expires_at=past))
    result = asyncio.run(repo.reject("USER_A", token))
    assert result is None
    raw = asyncio.run(repo.col.find_one({"_id": token}))
    assert raw["status"] == "pending"


def test_get_returns_none_for_wrong_user():
    """Ownership must still be enforced alongside the expiry check."""
    repo = ApprovalRepository(get_database())
    future = _utcnow() + timedelta(hours=1)
    token = asyncio.run(_seed(repo, expires_at=future))
    record = asyncio.run(repo.get("USER_B", token))
    assert record is None


def test_approve_already_used_token_still_works_when_valid():
    """Idempotency: a second approve on a non-expired approved token returns the record."""
    repo = ApprovalRepository(get_database())
    future = _utcnow() + timedelta(hours=1)
    token = asyncio.run(_seed(repo, expires_at=future))
    first = asyncio.run(repo.approve("USER_A", token))
    second = asyncio.run(repo.approve("USER_A", token))
    assert first is not None and first["status"] == "approved"
    assert second is not None and second["status"] == "approved"


def test_reject_after_approve_is_refused():
    """Once a token is approved, reject must NOT silently overwrite it."""
    repo = ApprovalRepository(get_database())
    future = _utcnow() + timedelta(hours=1)
    token = asyncio.run(_seed(repo, expires_at=future))
    asyncio.run(repo.approve("USER_A", token))
    rejected = asyncio.run(repo.reject("USER_A", token))
    assert rejected is None

    raw = asyncio.run(repo.col.find_one({"_id": token}))
    assert raw["status"] == "approved", "Approved token must remain approved after reject attempt."


def test_naive_expires_at_is_interpreted_as_utc():
    """Mongo may store naive datetimes; treat as UTC."""
    from backend.app.repositories import approval_repository

    naive_past = (_utcnow() - timedelta(seconds=5)).replace(tzinfo=None)
    assert approval_repository._is_expired({"expires_at": naive_past}) is True
    naive_future = (_utcnow() + timedelta(hours=1)).replace(tzinfo=None)
    assert approval_repository._is_expired({"expires_at": naive_future}) is False


def test_missing_expires_at_is_not_expired():
    from backend.app.repositories import approval_repository

    assert approval_repository._is_expired({"expires_at": None}) is False
    assert approval_repository._is_expired({}) is False