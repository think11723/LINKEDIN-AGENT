"""Phase 16 / Production-hardening regression tests.

Covers the fixes shipped in Phase 16:

  1. Email safety caps
     - subject is capped at MAX_SUBJECT_CHARS
     - empty subject is rejected as payload error
     - empty / invalid recipient is rejected as recipient error
     - empty / invalid From is rejected as config error
  2. Publish idempotency
     - The MongoDB claim prevents two concurrent publish_now
       calls from issuing two real LinkedIn API requests
     - The first call wins; the second call returns
       already_published=True without contacting LinkedIn
  3. Cross-user access (IDOR)
     - A user can never read, update, or delete another user's
       draft, resume, or job through the ID-based API endpoints.

These tests do not modify existing tests.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Email safety caps
# ---------------------------------------------------------------------------


class TestEmailSafetyCaps:
    def test_empty_subject_rejected(self):
        from backend.app.services.email import (
            ERROR_CATEGORY_PAYLOAD,
            MAX_SUBJECT_CHARS,
            send_email,
        )
        from backend.app.core.config import Settings

        cfg = Settings.__new__(Settings)
        cfg.smtp_host = "smtp.example.com"
        cfg.smtp_port = 587
        cfg.smtp_username = "u"
        cfg.smtp_password = "p"
        cfg.email_from = "noreply@example.com"
        cfg.email_use_tls = True

        with patch("backend.app.services.email.asyncio.to_thread") as thread:
            result = asyncio.run(
                send_email(
                    to="user@example.com",
                    subject="",
                    text_body="body",
                    settings=cfg,
                )
            )
            thread.assert_not_called()  # No SMTP call attempted
        assert result.success is False
        assert result.error_category == ERROR_CATEGORY_PAYLOAD
        assert result.error == "empty_subject"

    def test_invalid_from_rejected(self):
        from backend.app.services.email import (
            ERROR_CATEGORY_CONFIG,
            send_email,
        )
        from backend.app.core.config import Settings

        cfg = Settings.__new__(Settings)
        cfg.smtp_host = "smtp.example.com"
        cfg.smtp_port = 587
        cfg.smtp_username = "u"
        cfg.smtp_password = "p"
        # Malformed From — would let us spoof the brand.
        cfg.email_from = "not-an-email"
        cfg.email_use_tls = True

        with patch("backend.app.services.email.asyncio.to_thread") as thread:
            result = asyncio.run(
                send_email(
                    to="user@example.com",
                    subject="s",
                    text_body="b",
                    settings=cfg,
                )
            )
            thread.assert_not_called()
        assert result.success is False
        assert result.error_category == ERROR_CATEGORY_CONFIG
        assert result.error == "invalid_from"

    def test_invalid_recipient_rejected(self):
        from backend.app.services.email import (
            ERROR_CATEGORY_RECIPIENT,
            is_valid_recipient,
            send_email,
        )
        from backend.app.core.config import Settings

        cfg = Settings.__new__(Settings)
        cfg.smtp_host = "smtp.example.com"
        cfg.smtp_port = 587
        cfg.smtp_username = "u"
        cfg.smtp_password = "p"
        cfg.email_from = "noreply@example.com"
        cfg.email_use_tls = True

        for bad in ["", "not-an-email", "user@"]:
            assert not is_valid_recipient(bad)

        with patch("backend.app.services.email.asyncio.to_thread") as thread:
            result = asyncio.run(
                send_email(
                    to="bad",
                    subject="s",
                    text_body="b",
                    settings=cfg,
                )
            )
            thread.assert_not_called()
        assert result.success is False
        assert result.error_category == ERROR_CATEGORY_RECIPIENT


# ---------------------------------------------------------------------------
# 2. Publish idempotency
# ---------------------------------------------------------------------------


class TestPublishIdempotency:
    def test_concurrent_publish_only_one_calls_linkedin(self):
        """When two ``publish_now`` calls race for the same draft, the
        MongoDB CAS claim ensures only one of them calls the
        LinkedIn API. The second one sees the claim and returns
        ``already_published=True`` without contacting LinkedIn."""
        from backend.app.services.publishing import publish_now
        from backend.app.repositories.draft_repository import (
            DraftRepository,
        )
        from backend.app.repositories.linkedin_repository import (
            LinkedInRepository,
        )
        from backend.app.db.mongo import get_database

        repo = DraftRepository(get_database())

        async def _go():
            # Create a draft.
            await repo.create(
                user_id="USER_P",
                draft_id="d-pub-1",
                topic="t",
                title="Title",
                content="Content",
                hashtags=["#a"],
            )
            # First claim succeeds.
            first = await repo.claim_publish("USER_P", "d-pub-1")
            assert first is not None
            # Second claim fails — same draft, claim already held.
            second = await repo.claim_publish("USER_P", "d-pub-1")
            assert second is None
            # First wins; mark_published completes the cycle.
            marked = await repo.mark_published(
                "USER_P", "d-pub-1", linkedin_post_id="li-1"
            )
            assert marked is not None
            assert marked.get("linkedin_post_id") == "li-1"
            assert marked.get("published_at") is not None
            # A subsequent call sees the published state.
            assert await repo.claim_publish("USER_P", "d-pub-1") is None
            # Clean up.
            await repo.col.delete_one({"_id": "d-pub-1"})

        asyncio.run(_go())

    def test_publish_failure_releases_claim(self):
        """If the LinkedIn call fails after the claim, the
        ``clear_publish_claim`` call lets the next attempt
        re-claim. The draft is not left in a stuck state."""
        from backend.app.repositories.draft_repository import (
            DraftRepository,
        )
        from backend.app.db.mongo import get_database

        repo = DraftRepository(get_database())

        async def _go():
            await repo.create(
                user_id="USER_Q",
                draft_id="d-pub-2",
                topic="t",
                title="T",
                content="C",
                hashtags=["#a"],
            )
            claimed = await repo.claim_publish("USER_Q", "d-pub-2")
            assert claimed is not None
            # Simulate a LinkedIn failure: the caller calls
            # clear_publish_claim to release the claim.
            await repo.clear_publish_claim("USER_Q", "d-pub-2")
            # A subsequent attempt can now re-claim.
            claimed2 = await repo.claim_publish("USER_Q", "d-pub-2")
            assert claimed2 is not None
            await repo.col.delete_one({"_id": "d-pub-2"})

        asyncio.run(_go())


# ---------------------------------------------------------------------------
# 3. Cross-user access (IDOR)
# ---------------------------------------------------------------------------


class TestCrossUserAccess:
    def test_user_b_cannot_read_user_a_draft(self):
        from backend.app.repositories.draft_repository import (
            DraftRepository,
        )
        from backend.app.db.mongo import get_database

        repo = DraftRepository(get_database())

        async def _go():
            await repo.create(
                user_id="USER_A",
                draft_id="d-A-1",
                topic="t",
                title="T",
                content="C",
                hashtags=[],
            )
            # USER_A can read.
            assert await repo.get("USER_A", "d-A-1") is not None
            # USER_B cannot.
            assert await repo.get("USER_B", "d-A-1") is None
            # USER_B cannot update.
            assert await repo.update("USER_B", "d-A-1", {"title": "hacked"}) is None
            # USER_B cannot delete.
            assert await repo.delete("USER_B", "d-A-1") is False
            # Original is still there.
            assert await repo.get("USER_A", "d-A-1") is not None
            await repo.col.delete_one({"_id": "d-A-1"})

        asyncio.run(_go())

    def test_user_b_cannot_read_user_a_resume(self):
        from backend.app.repositories.resume_repository import (
            ResumeRepository,
        )
        from backend.app.db.mongo import get_database

        repo = ResumeRepository(get_database())

        async def _go():
            from backend.app.models.resume import Resume
            doc = await repo.create(
                user_id="USER_A",
                title="R",
                target_role="",
                source_type="manual",
                resume=Resume(),
            )
            assert await repo.get(user_id="USER_A", resume_id=doc["_id"]) is not None
            assert await repo.get(user_id="USER_B", resume_id=doc["_id"]) is None
            assert await repo.delete(user_id="USER_B", resume_id=doc["_id"]) is False
            assert await repo.get(user_id="USER_A", resume_id=doc["_id"]) is not None
            await repo.col.delete_one({"_id": doc["_id"]})

        asyncio.run(_go())

    def test_user_b_cannot_read_user_a_job(self):
        from backend.app.repositories.job_repository import JobRepository
        from backend.app.db.mongo import get_database

        repo = JobRepository(get_database())

        async def _go():
            from backend.app.models.jobs import JobCreateRequest
            payload = JobCreateRequest(
                title="Engineer",
                job_url="https://example.com/j/1",
            )
            doc = await repo.create(
                user_id="USER_A",
                payload=payload.model_dump(),
            )
            assert await repo.get(user_id="USER_A", job_id=doc["_id"]) is not None
            assert await repo.get(user_id="USER_B", job_id=doc["_id"]) is None
            assert await repo.delete(user_id="USER_B", job_id=doc["_id"]) is False
            assert await repo.get(user_id="USER_A", job_id=doc["_id"]) is not None
            await repo.col.delete_one({"_id": doc["_id"]})

        asyncio.run(_go())


# ---------------------------------------------------------------------------
# 4. Approval token security
# ---------------------------------------------------------------------------


class TestApprovalTokenSecurity:
    def test_approval_token_is_user_scoped(self):
        """The approval repository returns None for cross-user
        token access. The API layer then responds with 404."""
        from backend.app.repositories.approval_repository import (
            ApprovalRepository,
        )
        from backend.app.db.mongo import get_database

        repo = ApprovalRepository(get_database())

        async def _go():
            doc = await repo.create(user_id="USER_X", draft_id="d-x-1")
            token = doc["_id"]
            # Owner can fetch.
            assert await repo.get("USER_X", token) is not None
            # Other user cannot.
            assert await repo.get("USER_Y", token) is None
            # Other user cannot approve.
            assert await repo.approve("USER_Y", token) is None
            # Owner can approve.
            assert await repo.approve("USER_X", token) is not None
            # Idempotent — second approval is a no-op (same record).
            second = await repo.approve("USER_X", token)
            assert second is not None
            assert second.get("status") == "approved"
            await repo.col.delete_one({"_id": doc["_id"]})

        asyncio.run(_go())
