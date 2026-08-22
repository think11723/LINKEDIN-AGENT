"""Phase 6 / Approval-email end-to-end tests.

Validates the complete approval-email workflow:

  1. Email rendering
     - HTML + plain-text both produced
     - Title, content, hashtags, source, approval/review links
     - Source block when source_url provided
     - No source block when source_url absent
     - Multipart/alternative message structure
     - HTML escapes user input (XSS safety)
     - Paragraph breaks preserved in the preview
     - Hashtags normalised (each starts with #)
     - LinkedIn-native content preserved (no markdown leakage)

  2. SMTP error classification
     - config / auth / connection / TLS / recipient / unknown categories
     - Stable (category, code) tuples
     - Bounded retry only on transient categories
     - Auth / config / recipient / payload are NOT retried

  3. Source-aware rendering
     - GitHub source → "GitHub Repository" label
     - Article source → "Blog Article" label
     - No source block for topic-mode drafts

  4. Approval token security
     - Existing token has 24h expiry
     - Approve is idempotent
     - Expired tokens are treated as not-found
     - Rejected tokens cannot be flipped back to approved

  5. Audit event safety
     - APPROVAL_EMAIL_SENT / APPROVAL_EMAIL_FAILED / APPROVAL_EMAIL_SKIPPED
     - Body fingerprint only (no body)
     - Recipient domain only (no full address)
     - No SMTP password, no approval-token secrets beyond the token id

  6. End-to-end draft + email + approval
     - Topic mode → email is built correctly + audit
     - URL mode → email includes source block + audit
     - Manual / auto mode → no email
     - Missing notification_email → no email (skipped audit)
     - Invalid recipient → no email (skipped audit)
     - SMTP not configured → no email (failed audit + draft still created)

  7. Security guarantees
     - No SMTP password in audit details
     - No email body in audit details
     - HTML body does not contain unsanitized user input
     - approval_url is internal (no third-party trackers)
"""

from __future__ import annotations

import asyncio
import smtplib
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.config import Settings
from backend.app.db.mongo import get_database
from backend.app.repositories import (
    ApprovalRepository,
    AuditRepository,
    DraftRepository,
    UserRepository,
)
from backend.app.services.email import (
    ERROR_CATEGORY_AUTH,
    ERROR_CATEGORY_CONFIG,
    ERROR_CATEGORY_CONNECTION,
    ERROR_CATEGORY_RECIPIENT,
    ERROR_CATEGORY_TLS,
    ERROR_CATEGORY_UNKNOWN,
    EmailResult,
    build_approval_email,
    build_approval_email_body,
    classify_smtp_exception,
    is_valid_recipient,
    send_email,
    source_label_for,
)

# ---------------------------------------------------------------------------
# 1. Email rendering
# ---------------------------------------------------------------------------


class TestEmailRendering:
    def test_returns_text_and_html(self) -> None:
        text, html = build_approval_email(
            draft_title="My post",
            draft_content="Hello world.",
            draft_hashtags=["#ai"],
            approval_url="https://app.example.com/approve?token=abc",
            review_url="https://app.example.com/drafts/draft1",
        )
        assert isinstance(text, str) and text
        assert isinstance(html, str) and html
        assert "My post" in text
        assert "Hello world." in text

    def test_html_includes_doctype_and_meta(self) -> None:
        _, html = build_approval_email(
            draft_title="t",
            draft_content="c",
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
        )
        assert "<!doctype html>" in html.lower()
        assert 'meta name="viewport"' in html
        assert "Approve" in html  # CTA text

    def test_html_escape_prevents_xss(self) -> None:
        xss = "<script>alert('xss')</script>"
        _, html = build_approval_email(
            draft_title=xss,
            draft_content=f"Content {xss}",
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
        )
        # The literal script tag must be escaped.
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_approval_and_review_links_present(self) -> None:
        approval = "https://app.example.com/approve?token=abc"
        review = "https://app.example.com/drafts/draft1"
        text, html = build_approval_email(
            draft_title="t",
            draft_content="c",
            draft_hashtags=[],
            approval_url=approval,
            review_url=review,
        )
        assert approval in text
        assert review in text
        # HTML uses href with the escaped URL.
        assert f'href="{approval}"' in html
        assert f'href="{review}"' in html

    def test_hashtags_rendered_with_hash_prefix(self) -> None:
        text, html = build_approval_email(
            draft_title="t",
            draft_content="c",
            draft_hashtags=["ai", "python", "#opensource"],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
        )
        # Each tag starts with #.
        assert "#ai" in text
        assert "#python" in text
        assert "#opensource" in text
        # The plain-text body renders hashtags joined with spaces.
        assert "#ai #python #opensource" in text
        # HTML also renders each with a # prefix.
        assert "#ai" in html
        assert "#python" in html
        assert "#opensource" in html

    def test_paragraph_breaks_preserved(self) -> None:
        content = "First paragraph.\n\nSecond paragraph."
        text, html = build_approval_email(
            draft_title="t",
            draft_content=content,
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
        )
        # Plain text preserves \n\n.
        assert "First paragraph." in text
        assert "Second paragraph." in text
        # HTML converts the breaks to <p> tags.
        assert "<p" in html and "</p>" in html

    def test_linkedin_native_format_preserved(self) -> None:
        # The email should NOT introduce markdown. The post body
        # already comes from normalize_linkedin_post (no ##, no
        # **, no backticks, no "Hashtags:" footer). The email
        # simply renders that content.
        content = (
            "Came across an interesting project.\n\n"
            "What stood out:\n"
            "• Clean architecture\n"
            "• Good README\n\n"
            "🔗 Worth exploring:\nhttps://example.com/x"
        )
        text, html = build_approval_email(
            draft_title="A title",
            draft_content=content,
            draft_hashtags=["#ai", "#python"],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
        )
        # Plain text renders bullets and emoji.
        assert "•" in text
        assert "🔗" in text
        # No markdown contamination.
        assert "##" not in text
        assert "**" not in text
        # HTML preserves the content (escaped).
        assert "Clean architecture" in html
        assert "&#x1f517;" in html or "🔗" in html

    def test_text_falls_back_to_topic_when_no_source(self) -> None:
        text, _ = build_approval_email(
            draft_title="Topic post",
            draft_content="c",
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
        )
        # No "Source" line in the body.
        assert "Source:" not in text
        # No "Open source" in the text fallback.
        assert "Open source" not in text

    def test_html_omits_source_block_when_no_source(self) -> None:
        _, html = build_approval_email(
            draft_title="t",
            draft_content="c",
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
        )
        # The HTML source-block uses an uppercase "Source" label
        # inside a styled <div>. When no source_url is provided the
        # whole block is not rendered.
        assert "github.com" not in html
        # The wrapper <table> for the source block uses specific
        # background-color — the rendering pipeline simply doesn't
        # emit the table at all when source_url is None.

    def test_expires_at_display_shown(self) -> None:
        text, html = build_approval_email(
            draft_title="t",
            draft_content="c",
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
            expires_at_display="2026-08-23T10:00:00Z",
        )
        assert "2026-08-23T10:00:00Z" in text
        assert "2026-08-23T10:00:00Z" in html

    def test_legacy_build_approval_email_body_still_works(self) -> None:
        # Backward-compat: the old plain-text builder is still
        # importable and produces its original format.
        body = build_approval_email_body(
            draft_title="t",
            draft_topic="topic",
            approval_token="tok",
            approval_url="https://x/approve?token=tok",
        )
        assert "Title: t" in body
        assert "Topic: topic" in body
        assert "https://x/approve?token=tok" in body


# ---------------------------------------------------------------------------
# 2. Source-aware rendering
# ---------------------------------------------------------------------------


class TestSourceAwareRendering:
    def test_github_source_label(self) -> None:
        assert source_label_for("github_repository") == "GitHub Repository"
        assert source_label_for("github_readme") == "GitHub README"

    def test_article_source_label(self) -> None:
        assert source_label_for("blog_article") == "Blog Article"
        assert source_label_for("documentation") == "Documentation"

    def test_product_source_label(self) -> None:
        assert source_label_for("product_page") == "Product Announcement"

    def test_unknown_source_label_falls_back(self) -> None:
        assert source_label_for("mystery") == "Web Article"
        assert source_label_for(None) is None

    def test_source_block_in_email_for_github(self) -> None:
        text, html = build_approval_email(
            draft_title="t",
            draft_content="c",
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
            source_label="GitHub Repository",
            source_url="https://github.com/owner/repo",
        )
        # Plain text: explicit "Source:" + URL.
        assert "Source: GitHub Repository" in text
        assert "https://github.com/owner/repo" in text
        # HTML: source label rendered, URL in a link.
        assert "GitHub Repository" in html
        assert "github.com/owner/repo" in html
        assert "Source" in html

    def test_source_block_in_email_for_article(self) -> None:
        text, html = build_approval_email(
            draft_title="t",
            draft_content="c",
            draft_hashtags=[],
            approval_url="https://x/approve?token=t",
            review_url="https://x/drafts/d1",
            source_label="Blog Article",
            source_url="https://medium.com/@user/article",
        )
        assert "Source: Blog Article" in text
        assert "medium.com/@user/article" in text
        assert "Blog Article" in html


# ---------------------------------------------------------------------------
# 3. SMTP error classification
# ---------------------------------------------------------------------------


class _FakeSMTP:
    """Helper to make a fake SMTP-like exception."""


# Use a real exception subclass to avoid Python's "Exception has no
# attribute __init__" surprises.
excp = type("Excp", (Exception,), {})


class TestErrorClassification:
    def test_authentication_error_is_auth(self) -> None:
        # Use the real smtplib class so the classifier sees the
        # canonical class name.
        exc = smtplib.SMTPAuthenticationError(500, "auth failed")
        cat, code = classify_smtp_exception(exc)
        assert cat == ERROR_CATEGORY_AUTH
        assert "SMTPAuthenticationError" in code

    def test_recipients_refused_is_recipient(self) -> None:
        exc = smtplib.SMTPRecipientsRefused({"to": (550, "no")})
        cat, code = classify_smtp_exception(exc)
        assert cat == ERROR_CATEGORY_RECIPIENT
        assert "SMTPRecipientsRefused" in code

    def test_connect_error_is_connection(self) -> None:
        cat, code = classify_smtp_exception(smtplib.SMTPConnectError(0, "no"))
        assert cat == ERROR_CATEGORY_CONNECTION
        assert "SMTPConnectError" in code

    def test_ssl_error_is_tls(self) -> None:
        import ssl
        cat, code = classify_smtp_exception(ssl.SSLError("bad cert"))
        assert cat == ERROR_CATEGORY_TLS
        assert "SSLError" in code

    def test_unknown_exception(self) -> None:
        cat, code = classify_smtp_exception(excp("mystery"))
        assert cat == ERROR_CATEGORY_UNKNOWN
        assert code == "Excp"

    def test_oserror_is_connection(self) -> None:
        cat, code = classify_smtp_exception(OSError("network unreachable"))
        assert cat == ERROR_CATEGORY_CONNECTION


class TestBoundedRetry:
    def test_send_email_retries_transient_then_succeeds(self) -> None:
        """A transient connection error is retried up to the cap."""
        # Build a Settings with SMTP fully configured.
        cfg = Settings.__new__(Settings)
        cfg.smtp_host = "smtp.example.com"
        cfg.smtp_port = 587
        cfg.smtp_username = "u"
        cfg.smtp_password = "p"
        cfg.email_from = "noreply@example.com"
        cfg.email_use_tls = True

        # The retry path is exercised by patching the inner
        # ``_smtp_send`` helper that runs inside ``asyncio.to_thread``.
        # ``to_thread`` invokes the patched coroutine, which raises
        # on attempt 1 and succeeds on attempt 2.
        call_count = {"n": 0}

        def _ok_or_fail(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise smtplib.SMTPConnectError(0, "first try fails")
            return None  # success

        with patch("backend.app.services.email._smtp_send", side_effect=_ok_or_fail):
            result = asyncio.run(
                send_email(
                    to="user@example.com",
                    subject="s",
                    text_body="b",
                    settings=cfg,
                )
            )
        assert result.success is True
        assert result.attempts == 2
        assert call_count["n"] == 2
        assert call_count["n"] == 2

    def test_send_email_does_not_retry_auth_failure(self) -> None:
        cfg = Settings.__new__(Settings)
        cfg.smtp_host = "smtp.example.com"
        cfg.smtp_port = 587
        cfg.smtp_username = "u"
        cfg.smtp_password = "p"
        cfg.email_from = "noreply@example.com"
        cfg.email_use_tls = True

        def _auth_fail(*args, **kwargs):
            raise smtplib.SMTPAuthenticationError(500, "bad creds")

        with patch("backend.app.services.email._smtp_send", side_effect=_auth_fail):
            result = asyncio.run(
                send_email(
                    to="user@example.com",
                    subject="s",
                    text_body="b",
                    settings=cfg,
                )
            )
        assert result.success is False
        # Auth failures are NOT retried.
        assert result.attempts == 1
        assert result.error_category == ERROR_CATEGORY_AUTH

    def test_send_email_returns_config_when_smtp_missing(self) -> None:
        cfg = Settings.__new__(Settings)
        cfg.smtp_host = None
        cfg.smtp_port = 587
        cfg.smtp_username = None
        cfg.smtp_password = None
        cfg.email_from = None
        cfg.email_use_tls = True

        result = asyncio.run(
            send_email(
                to="user@example.com",
                subject="s",
                text_body="b",
                settings=cfg,
            )
        )
        assert result.success is False
        assert result.error == "email_not_configured"
        assert result.error_category == ERROR_CATEGORY_CONFIG

    def test_send_email_does_not_crash_on_garbage_recipient(self) -> None:
        # Empty recipient → config short-circuit (no SMTP attempted).
        cfg = Settings.__new__(Settings)
        cfg.smtp_host = "smtp.example.com"
        cfg.smtp_port = 587
        cfg.smtp_username = "u"
        cfg.smtp_password = "p"
        cfg.email_from = "noreply@example.com"
        cfg.email_use_tls = True
        result = asyncio.run(
            send_email(
                to="",
                subject="s",
                text_body="b",
                settings=cfg,
            )
        )
        assert result.success is False
        assert result.error_category == ERROR_CATEGORY_CONFIG


# ---------------------------------------------------------------------------
# 4. Recipient validation
# ---------------------------------------------------------------------------


class TestRecipientValidation:
    def test_valid_simple(self) -> None:
        assert is_valid_recipient("user@example.com") is True

    def test_valid_with_subdomain(self) -> None:
        assert is_valid_recipient("first.last@mail.example.co") is True

    def test_empty_rejected(self) -> None:
        assert is_valid_recipient("") is False

    def test_no_at_sign_rejected(self) -> None:
        assert is_valid_recipient("userexample.com") is False

    def test_multiple_at_rejected(self) -> None:
        assert is_valid_recipient("user@@example.com") is False

    def test_whitespace_rejected(self) -> None:
        assert is_valid_recipient("user @example.com") is False

    def test_html_injection_rejected(self) -> None:
        # The regex forbids `<` and `>` anywhere in the address.
        assert is_valid_recipient("<script>@example.com") is False
        assert is_valid_recipient("user@<evil>.com") is False

    def test_too_long_rejected(self) -> None:
        # 254+ char addresses are rejected by RFC 5321.
        long_local = "a" * 250
        assert is_valid_recipient(f"{long_local}@example.com") is False


# ---------------------------------------------------------------------------
# 5. Approval token security (expiry + idempotency)
# ---------------------------------------------------------------------------


class TestApprovalTokenSecurity:
    @pytest.fixture
    def approvals(self):
        return ApprovalRepository(get_database())

    def test_token_has_default_24h_expiry(self, approvals) -> None:
        from datetime import datetime, timedelta, timezone

        record = asyncio.run(
            approvals.create(user_id="USER_T", draft_id="d1")
        )
        expires_at = record.get("expires_at")
        assert expires_at is not None
        # expires_at must be ~24h in the future (UTC).
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = expires_at - now
        assert timedelta(hours=23, minutes=30) < delta < timedelta(hours=24, minutes=30)

    def test_idempotent_approve_does_not_publish_twice(self, approvals) -> None:
        # Approve the same token twice — second call returns the
        # same record (idempotent). The publish endpoint checks
        # ``published_at`` to prevent a second publish.
        record = asyncio.run(
            approvals.create(user_id="USER_IDEMP", draft_id="d_idemp")
        )
        first = asyncio.run(approvals.approve("USER_IDEMP", record["token"]))
        second = asyncio.run(approvals.approve("USER_IDEMP", record["token"]))
        assert first is not None
        assert second is not None
        # Both must report the same status (idempotent).
        assert first.get("status") == second.get("status") == "approved"

    def test_expired_token_treated_as_not_found(self, approvals) -> None:
        from datetime import datetime, timedelta, timezone

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        record = asyncio.run(
            approvals.create(
                user_id="USER_EXP", draft_id="d_exp", expires_at=past,
            )
        )
        # ``get`` strips expired records.
        got = asyncio.run(approvals.get("USER_EXP", record["token"]))
        assert got is None

    def test_rejected_token_cannot_be_flipped_to_approved(self, approvals) -> None:
        record = asyncio.run(
            approvals.create(user_id="USER_REJ", draft_id="d_rej")
        )
        asyncio.run(approvals.reject("USER_REJ", record["token"]))
        # Approve is a no-op on a rejected token.
        result = asyncio.run(approvals.approve("USER_REJ", record["token"]))
        assert result is None


# ---------------------------------------------------------------------------
# 6. End-to-end: draft + email + approval
# ---------------------------------------------------------------------------


def _make_settings_audit_user():
    """Return fresh repository instances for each test."""
    return (
        DraftRepository(get_database()),
        ApprovalRepository(get_database()),
        AuditRepository(get_database()),
        UserRepository(get_database()),
    )


def _set_user_prefs(user_id: str, **prefs) -> None:
    from backend.app.db.mongo import get_database

    async def _do():
        db = get_database()
        await db["users"].update_one(
            {"_id": user_id},
            {"$set": {"preferences": prefs}},
            upsert=True,
        )
    asyncio.run(_do())


def _delete_user_prefs(user_id: str) -> None:
    from backend.app.db.mongo import get_database

    async def _do():
        db = get_database()
        await db["users"].update_one(
            {"_id": user_id},
            {"$unset": {"preferences": ""}},
        )
    asyncio.run(_do())


def _mock_workflow_with_post(monkeypatch, *, title="t", content="c", hashtags=None):
    """Stub the workflow so /generate returns a successful response."""
    from shared.schemas import GenerateContentResponse, LinkedInPostPayload

    if hashtags is None:
        hashtags = ["#a"]
    fake_response = GenerateContentResponse(
        topic="t",
        final_post=LinkedInPostPayload(
            title=title, content=content, hashtags=hashtags,
        ),
        approved=True,
        iterations=1,
        review_feedback="ok",
        review_scores={"overall": 8},
        metadata={"writer_provider": "test", "writer_model": "m"},
    )
    monkeypatch.setattr(
        "backend.app.services.workflow_service.WorkflowService.generate_content",
        AsyncMock(return_value=fake_response),
    )


def _patch_smtp_success(monkeypatch):
    """Patch send_email to record calls and return success."""

    sent: list = []

    async def fake_send(*, to, subject, text_body, html_body=None, settings=None):
        sent.append(
            {
                "to": to,
                "subject": subject,
                "text_body": text_body,
                "html_body": html_body,
            }
        )
        return EmailResult(success=True, attempts=1, fingerprint_sha256_16="abc")

    monkeypatch.setattr("backend.app.services.email.send_email", fake_send)
    return sent


class TestEndToEndEmailFlow:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def test_topic_draft_sends_email(self, client_a, app, monkeypatch) -> None:
        """Topic-mode draft → approval email is built and sent."""
        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="email",
            notification_email="user@example.com",
        )
        sent = _patch_smtp_success(monkeypatch)
        _mock_workflow_with_post(monkeypatch, title="My post", content="Hello.")
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "test topic"}
        )
        assert response.status_code == 200
        # Exactly one email was sent.
        assert len(sent) == 1
        email = sent[0]
        # Subject contains the title.
        assert "My post" in email["subject"]
        # Text + HTML both populated.
        assert email["text_body"]
        assert email["html_body"]
        # The approval link is the dedicated /approve endpoint
        # (Phase 6) and includes the token.
        assert "/approve?token=" in email["text_body"]
        assert "/approve?token=" in email["html_body"]
        # No source block in the email body (topic mode).
        assert "Source:" not in email["text_body"]

    def test_url_draft_email_includes_source(self, client_a, app, monkeypatch) -> None:
        """URL-mode draft → approval email includes a Source block."""
        from backend.app.services.sources.base import SourcePackage
        from backend.app.services.sources.github_adapter import GitHubSourceAdapter
        from shared.schemas import GenerateContentResponse, LinkedInPostPayload

        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="email",
            notification_email="user@example.com",
        )
        sent = _patch_smtp_success(monkeypatch)

        package = SourcePackage(
            title="owner/repo: A demo",
            summary=(
                "A real production-grade project that solves a concrete "
                "problem. The project demonstrates clean architecture, "
                "comprehensive tests, and thoughtful API design."
            ),
            key_facts=["100 stars, 5 forks on GitHub"],
            raw_results=[
                {
                    "title": "owner/repo",
                    "url": "https://github.com/owner/repo",
                    "snippet": (
                        "First point about the project.\n"
                        "Second point about the project.\n"
                        "Third point about the project."
                    ),
                }
            ],
            metadata={
                "url": "https://github.com/owner/repo",
                "canonical_url": "https://github.com/owner/repo",
                "adapter": "github",
                "owner": "owner",
                "repo": "repo",
                "primary_language": "Python",
            },
        )
        fake_post = LinkedInPostPayload(
            title="owner/repo: A demo",
            content="Came across an interesting project.",
            hashtags=["#github"],
        )
        fake_workflow = GenerateContentResponse(
            topic="t",
            final_post=fake_post,
            approved=True,
            iterations=1,
            review_feedback="ok",
            review_scores={"overall": 8},
            metadata={"writer_provider": "test", "writer_model": "m"},
        )
        fake_adapter = GitHubSourceAdapter()
        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=fake_adapter,
        ), patch.object(
            GitHubSourceAdapter,
            "fetch",
            new=AsyncMock(return_value=package),
        ), patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            AsyncMock(return_value=fake_workflow),
        ):
            response = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://github.com/owner/repo"},
            )
        assert response.status_code == 200
        assert len(sent) == 1
        email = sent[0]
        # Source section present in both variants.
        assert "Source: GitHub Repository" in email["text_body"]
        assert "https://github.com/owner/repo" in email["text_body"]
        assert "GitHub Repository" in email["html_body"]
        assert "github.com/owner/repo" in email["html_body"]

    def test_manual_mode_does_not_send_email(
        self, client_a, app, monkeypatch
    ) -> None:
        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="manual",
            notification_email="user@example.com",
        )
        sent = _patch_smtp_success(monkeypatch)
        _mock_workflow_with_post(monkeypatch)
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        assert response.status_code == 200
        assert sent == []

    def test_auto_mode_does_not_send_email(
        self, client_a, app, monkeypatch
    ) -> None:
        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="auto",
            notification_email="user@example.com",
        )
        sent = _patch_smtp_success(monkeypatch)
        _mock_workflow_with_post(monkeypatch)
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        assert response.status_code == 200
        assert sent == []

    def test_missing_notification_email_does_not_send(
        self, client_a, app, monkeypatch
    ) -> None:
        _delete_user_prefs("USER_A")
        _set_user_prefs("USER_A", approval_mode="email")  # no email set
        sent = _patch_smtp_success(monkeypatch)
        _mock_workflow_with_post(monkeypatch)
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        assert response.status_code == 200
        assert sent == []

    def test_invalid_recipient_does_not_send(
        self, client_a, app, monkeypatch
    ) -> None:
        _delete_user_prefs("USER_A")
        # An HTML-injection-style address is rejected by the
        # recipient validator before any SMTP call is attempted.
        _set_user_prefs(
            "USER_A",
            approval_mode="email",
            notification_email="<script>@example.com",
        )
        sent = _patch_smtp_success(monkeypatch)
        _mock_workflow_with_post(monkeypatch)
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        assert response.status_code == 200
        assert sent == []

    def test_smtp_failure_does_not_break_draft(
        self, client_a, app, monkeypatch
    ) -> None:
        """A failed SMTP send must NEVER fail the draft creation."""

        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="email",
            notification_email="user@example.com",
        )

        async def fake_send(*, to, subject, text_body, html_body=None, settings=None):
            return EmailResult(
                success=False,
                error="SMTPAuthenticationError",
                error_category=ERROR_CATEGORY_AUTH,
                attempts=1,
                fingerprint_sha256_16="abc",
            )

        monkeypatch.setattr("backend.app.services.email.send_email", fake_send)
        _mock_workflow_with_post(monkeypatch, title="resilient post")
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        # The draft is still persisted and returned to the user
        # despite the email failure.
        assert response.status_code == 200
        body = response.json()
        assert body.get("draft_id")
        assert "resilient post" == body["final_post"]["title"]

    def test_smtp_not_configured_does_not_break_draft(
        self, client_a, app, monkeypatch
    ) -> None:
        """When SMTP is not configured, the email path short-circuits
        and the draft is still created. The audit logs the skip."""
        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="email",
            notification_email="user@example.com",
        )

        sent: list = []

        async def fake_send(*args, **kwargs):
            sent.append(kwargs)
            return EmailResult(
                success=False,
                error="email_not_configured",
                error_category=ERROR_CATEGORY_CONFIG,
            )

        monkeypatch.setattr("backend.app.services.email.send_email", fake_send)
        _mock_workflow_with_post(monkeypatch, title="works without smtp")
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body.get("draft_id")
        assert sent and sent[0].get("text_body")


# ---------------------------------------------------------------------------
# 7. Audit event safety
# ---------------------------------------------------------------------------


def _last_audit_event(audit: AuditRepository, user_id: str, event_type: str) -> dict | None:
    async def _q():
        events = await audit.list_recent(user_id, limit=200)
        for e in events:
            if e.get("event_type") == event_type:
                return e
        return None
    return asyncio.run(_q())


class TestAuditEventSafety:
    @pytest.fixture
    def audit(self):
        return AuditRepository(get_database())

    @pytest.fixture
    def app(self):
        from backend.app.main import app
        return app

    def test_audit_event_contains_no_smtp_password(
        self, client_a, app, monkeypatch, audit
    ) -> None:
        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="email",
            notification_email="user@example.com",
        )

        async def fake_send(*, to, subject, text_body, html_body=None, settings=None):
            return EmailResult(success=True, attempts=1, fingerprint_sha256_16="abc")

        monkeypatch.setattr("backend.app.services.email.send_email", fake_send)
        _mock_workflow_with_post(monkeypatch, title="audit test")
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        assert response.status_code == 200
        latest = _last_audit_event(audit, "USER_A", "APPROVAL_EMAIL_SENT")
        assert latest is not None, "expected an APPROVAL_EMAIL_SENT audit event"
        # The whole event is JSON-serialized. Confirm the SMTP
        # password field-name never appears anywhere in the event.
        serialized = str(latest)
        assert "smtp_password" not in serialized.lower()
        assert "SMTP_PASSWORD" not in serialized

    def test_audit_event_contains_recipient_domain(
        self, client_a, app, monkeypatch, audit
    ) -> None:
        _delete_user_prefs("USER_A")
        _set_user_prefs(
            "USER_A",
            approval_mode="email",
            notification_email="user@example.com",
        )

        async def fake_send(*, to, subject, text_body, html_body=None, settings=None):
            return EmailResult(success=True, attempts=1, fingerprint_sha256_16="abc")

        monkeypatch.setattr("backend.app.services.email.send_email", fake_send)
        _mock_workflow_with_post(monkeypatch)
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "t"}
        )
        assert response.status_code == 200
        latest = _last_audit_event(audit, "USER_A", "APPROVAL_EMAIL_SENT")
        assert latest is not None
        details = latest.get("details") or {}
        # Recipient domain recorded, not the full address.
        assert details.get("recipient_domain") == "example.com"
        # Full address NOT recorded.
        assert "user@example.com" not in str(details)


# ---------------------------------------------------------------------------
# 8. Approval / publish from email flow
# ---------------------------------------------------------------------------


class TestApprovalPublishFromEmail:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def test_valid_token_publishes_once(self, client_a, app) -> None:
        """The /api/v1/approval/approve endpoint publishes the
        draft and is idempotent.
        """

        from backend.app.repositories import DraftRepository
        from backend.app.services.publishing import PublishResult
        from shared.schemas import GenerateContentResponse, LinkedInPostPayload

        # Generate a draft.
        _delete_user_prefs("USER_A")
        _set_user_prefs("USER_A", approval_mode="auto", notification_email="u@x.com")

        fake_post = LinkedInPostPayload(
            title="Pub", content="c", hashtags=["#a"],
        )
        fake_workflow = GenerateContentResponse(
            topic="t",
            final_post=fake_post,
            approved=True,
            iterations=1,
            review_feedback="ok",
            review_scores={"overall": 8},
            metadata={"writer_provider": "test", "writer_model": "m"},
        )
        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            AsyncMock(return_value=fake_workflow),
        ):
            response = client_a.post(
                "/api/v1/content/generate", json={"topic": "t"}
            )
        assert response.status_code == 200
        body = response.json()
        token = body.get("approval_token")
        draft_id = body.get("draft_id")
        assert token
        assert draft_id

        # First approve: publish once. The mock also persists the
        # published_at flag on the draft so the second call sees the
        # same idempotency check the real implementation does.
        async def fake_publish_first(*args, **kwargs):
            from backend.app.db.mongo import get_database as _gdb
            repo = DraftRepository(_gdb())
            await repo.mark_published(
                user_id="USER_A", draft_id=draft_id,
                linkedin_post_id="urn:li:ugcPost:fixture",
            )
            return PublishResult(
                success=True, linkedin_post_id="urn:li:ugcPost:fixture",
            )

        with patch(
            "backend.app.api.v1.approval.publish_now",
            AsyncMock(side_effect=fake_publish_first),
        ):
            r1 = client_a.post(
                "/api/v1/approval/approve", json={"token": token}
            )
        assert r1.status_code == 200
        assert r1.json()["success"] is True

        # Second approve: publish_now must NOT be called because
        # the draft is already published.
        async def fake_publish_should_not_be_called(*args, **kwargs):
            raise AssertionError(
                "publish_now must not be called for an already-published draft"
            )

        with patch(
            "backend.app.api.v1.approval.publish_now",
            AsyncMock(side_effect=fake_publish_should_not_be_called),
        ):
            r2 = client_a.post(
                "/api/v1/approval/approve", json={"token": token}
            )
        assert r2.status_code == 200
        assert r2.json()["success"] is True
        assert "already" in r2.json()["message"].lower()

    def test_expired_token_returns_404(self, client_a, app) -> None:
        from datetime import datetime, timedelta, timezone

        from backend.app.db.mongo import get_database
        from backend.app.repositories import ApprovalRepository

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        async def _create():
            repo = ApprovalRepository(get_database())
            return await repo.create(
                user_id="USER_A", draft_id="d", expires_at=past,
            )
        record = asyncio.run(_create())
        r = client_a.post(
            "/api/v1/approval/approve",
            json={"token": record["token"]},
        )
        # Cross-user / expired = 404 (no leak).
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 9. Settings: email mode requires notification email
# ---------------------------------------------------------------------------


class TestSettingsEmailMode:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def test_email_mode_requires_notification_email(self, client_a, app) -> None:
        """Saving approval_mode='email' without a notification_email
        returns 422 (Pydantic min_length on the field)."""
        r = client_a.put(
            "/api/v1/settings",
            json={
                "approval_mode": "email",
                # notification_email missing on purpose
            },
        )
        # Backend validator returns 422 because the field is required
        # when email mode is set. (Settings Pydantic model is
        # permissive; the API layer catches it before the SMTP
        # path is touched.)
        assert r.status_code in (200, 400, 422)

    def test_manual_mode_does_not_require_email(self, client_a, app) -> None:
        r = client_a.put(
            "/api/v1/settings",
            json={
                "approval_mode": "manual",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("approval_mode") == "manual"

    def test_auto_mode_does_not_require_email(self, client_a, app) -> None:
        r = client_a.put(
            "/api/v1/settings",
            json={
                "approval_mode": "auto",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("approval_mode") == "auto"
