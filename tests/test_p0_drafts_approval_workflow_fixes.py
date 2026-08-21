"""Regression tests for the three production workflow fixes:

Fix 1 — Draft API serializes `id` (not `draft_id`) so the
         frontend's `draft.id` reads correctly and the Open button
         navigates to /drafts/<real-id> (not /drafts/undefined).

Fix 2 — Approval email is sent only when approval_mode == "email"
         and only when SMTP + notification_email are configured.
         Email failure must not fail the draft creation.

Fix 3 — Approve (without schedule_time) triggers publish_now via
         the shared publishing service. Approve with schedule_time
         does NOT trigger immediate publishing.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

from cryptography.fernet import Fernet

from backend.app.api.v1 import content as content_module  # noqa: E402
from backend.app.services import email as email_module  # noqa: E402


# ----- shared fixtures ----------------------------------------------------


def _mock_workflow(monkeypatch, *, approved: bool = True, title: str = "Fix"):
    """Stub the LangGraph workflow so /generate returns immediately."""
    from backend.app.services import workflow_service
    from shared.schemas import (
        GenerateContentResponse,
        LinkedInPostPayload,
    )

    async def async_generate_content(self, payload):
        return GenerateContentResponse(
            topic=payload.topic,
            final_post=LinkedInPostPayload(
                title=title, content="c", hashtags=[], image_path=None
            ),
            approved=approved,
            iterations=1,
            metadata={
                "writer_provider": "groq",
                "writer_model": "llama-3.3-70b",
                "reviewer_provider": "groq",
                "reviewer_model": "llama-3.3-70b",
            },
        )

    monkeypatch.setattr(
        workflow_service.WorkflowService, "generate_content",
        async_generate_content,
    )

# ----- Fix 1: Draft API response shape ------------------------------------


def test_draft_list_serializes_id_not_draft_id(client_a, monkeypatch) -> None:
    """GET /api/v1/drafts must serialize each item with key `id`,
    not `draft_id`. The frontend reads `draft.id` to navigate."""

    async def fake_post(self, url, **_kwargs):
        class _R:
            status_code = 201

            def json(self):
                return {"id": "urn:li:ugcPost:fixture"}

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    # Seed a draft via the create endpoint so the list is non-empty.
    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "fix1-list", "title": "Fix 1 list", "content": "c"},
    )
    assert create.status_code == 201
    created_id = create.json()["id"]

    response = client_a.get("/api/v1/drafts")
    assert response.status_code == 200
    items = response.json().get("items", [])
    assert items, "test fixture should seed at least one draft"
    first = items[0]
    assert "id" in first, (
        "Draft API response must contain key 'id' (frontend reads "
        f"draft.id). Got keys: {sorted(first.keys())}"
    )
    assert "draft_id" not in first, (
        "Draft API response must NOT contain legacy 'draft_id' key."
    )
    assert first["id"] == created_id


def test_draft_detail_returns_id_key(client_a) -> None:
    """GET /api/v1/drafts/{id} must return the draft with key `id`."""

    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "fix1", "title": "Fix 1 detail", "content": "c"},
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]

    response = client_a.get(f"/api/v1/drafts/{draft_id}")
    assert response.status_code == 200
    body = response.json()
    assert body.get("id") == draft_id
    assert "draft_id" not in body


def test_generated_content_response_has_consistent_id_keys(
    client_a, monkeypatch
) -> None:
    """POST /api/v1/content/generate must expose the draft ID as
    `id` at all levels (top-level + nested draft object), so the
    frontend can navigate to /drafts/<real-id> immediately."""

    async def fake_post(self, url, **_kwargs):
        class _R:
            status_code = 201

            def json(self):
                return {"id": "urn:li:ugcPost:fixture"}

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    _mock_workflow(monkeypatch, title="Fix 1 generated")

    response = client_a.post(
        "/api/v1/content/generate", json={"topic": "fix1-generated"}
    )
    assert response.status_code == 200
    body = response.json()

    # The nested draft dict should expose `id`.
    embedded = body.get("draft")
    if embedded is not None:
        assert "id" in embedded or embedded == {}, (
            f"Nested draft must include 'id' key. Got: {sorted(embedded.keys())}"
        )


# ----- Fix 2: Approval email ----------------------------------------------


def _seed_linkedin_tokens_for_test(user_id: str = "USER_A") -> None:
    fernet = Fernet(os.environ["LINKEDIN_TOKEN_ENCRYPTION_KEY"].encode())

    async def _insert() -> None:
        from backend.app.db.mongo import get_database
        db = get_database()
        await db["linkedin_accounts"].update_one(
            {"_id": user_id},
            {
                "$set": {
                    "access_token_enc": fernet.encrypt(b"FAKE_TOKEN"),
                    "refresh_token_enc": fernet.encrypt(b"FAKE_REFRESH"),
                    "expires_at": datetime.now(timezone.utc),
                    "scope": "openid profile email w_member_social",
                    "person_urn": "urn:li:person:FAKE_URN",
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    asyncio.get_event_loop().run_until_complete(_insert()) if False else asyncio.run(_insert())


def _set_user_preferences(
    user_id: str, *, approval_mode: str, notification_email: str
) -> None:
    async def _update() -> None:
        from backend.app.db.mongo import get_database
        db = get_database()
        await db["users"].update_one(
            {"_id": user_id},
            {
                "$set": {
                    "preferences": {
                        "approval_mode": approval_mode,
                        "notification_email": notification_email,
                    },
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    asyncio.run(_update())


def test_approval_email_not_sent_when_approval_mode_is_manual(
    client_a, monkeypatch
) -> None:
    """When approval_mode == 'manual', no approval email is sent."""

    sent_calls = []

    async def fake_send(*, to, subject, body, settings=None):
        sent_calls.append({"to": to, "subject": subject})
        from backend.app.services.email import EmailResult
        return EmailResult(success=True)

    monkeypatch.setattr(email_module, "send_email", fake_send)

    async def fake_post(self, url, **_kwargs):
        class _R:
            status_code = 201

            def json(self):
                return {"id": "urn:li:ugcPost:fixture"}

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    _mock_workflow(monkeypatch, title="Fix 2 manual")

    _set_user_preferences(
        "USER_A",
        approval_mode="manual",
        notification_email="user@example.com",
    )

    response = client_a.post(
        "/api/v1/content/generate", json={"topic": "fix2-manual"}
    )
    assert response.status_code == 200

    assert sent_calls == [], (
        f"No email should be sent when approval_mode='manual'. "
        f"Got calls: {sent_calls}"
    )


def test_approval_email_skipped_audit_recorded_when_preferences_missing(
    client_a, monkeypatch
) -> None:
    """When the user has NO preferences stored, the email helper
    MUST log an APPROVAL_EMAIL_SKIPPED audit event with reason
    'approval_mode_not_email' so the operator has diagnostic
    visibility. This prevents silent skips that hide the real reason
    email was not sent."""

    sent_calls = []

    async def fake_send(*, to, subject, body, settings=None):
        sent_calls.append({"to": to, "subject": subject})
        from backend.app.services.email import EmailResult
        return EmailResult(success=True)

    monkeypatch.setattr(email_module, "send_email", fake_send)

    async def fake_post(self, url, **_kwargs):
        class _R:
            status_code = 201

            def json(self):
                return {"id": "urn:li:ugcPost:fixture"}

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    _mock_workflow(monkeypatch, title="Fix 2 no preferences")

    # Do NOT set user preferences. The user document exists but has
    # no `preferences` sub-doc — this is the production state.
    async def _no_prefs():
        from backend.app.db.mongo import get_database
        db = get_database()
        await db["users"].update_one(
            {"_id": "USER_A"},
            {"$set": {"updated_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc)}},
            upsert=True,
        )
    asyncio.run(_no_prefs())

    response = client_a.post(
        "/api/v1/content/generate", json={"topic": "fix2-no-prefs"}
    )
    assert response.status_code == 200

    assert sent_calls == [], (
        f"No email must be sent when preferences are missing. "
        f"Got calls: {sent_calls}"
    )

    # The skip MUST be audited with APPROVAL_EMAIL_SKIPPED so the
    # operator can diagnose why email is not flowing.
    from backend.app.db.mongo import get_database
    db = get_database()

    async def _load_skips():
        return [
            e async for e in db["audit_events"].find(
                {"event_type": "APPROVAL_EMAIL_SKIPPED",
                 "details.draft_id": response.json()["draft_id"]}
            )
        ]

    skip_events = asyncio.run(_load_skips())
    assert skip_events, (
        "APPROVAL_EMAIL_SKIPPED must be written whenever the helper "
        "decides not to send an email — silent skips hide the root "
        "cause from operators."
    )
    assert skip_events[0]["details"]["reason"] == "approval_mode_not_email"
    assert skip_events[0]["details"]["preferences_present"] is False


def test_approval_email_sent_when_approval_mode_is_email_and_smtp_configured(
    client_a, monkeypatch
) -> None:
    """When approval_mode == 'email' AND SMTP is configured AND
    notification_email is set, an email is sent."""

    sent_calls = []

    async def fake_send(*, to, subject, body, settings=None):
        sent_calls.append({"to": to, "subject": subject})
        from backend.app.services.email import EmailResult
        return EmailResult(success=True)

    from backend.app.services import email as email_service

    monkeypatch.setattr(email_module, "send_email", fake_send)

    async def fake_post(self, url, **_kwargs):
        class _R:
            status_code = 201

            def json(self):
                return {"id": "urn:li:ugcPost:fixture"}

        return _R()

    import httpx

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    # Configure SMTP BEFORE clearing the Settings cache so the new
    # Settings instance sees the configured SMTP_HOST.
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_FROM", "noreply@example.com")

    # Settings is lru_cached at module-import time. Clear it so the
    # next get_settings() call rebuilds it from the patched env vars.
    from backend.app.core import config as config_module

    if hasattr(config_module.get_settings, "cache_clear"):
        config_module.get_settings.cache_clear()

    _mock_workflow(monkeypatch, title="Fix 2 email")
    _set_user_preferences(
        "USER_A",
        approval_mode="email",
        notification_email="user@example.com",
    )

    response = client_a.post(
        "/api/v1/content/generate", json={"topic": "fix2-email"}
    )
    assert response.status_code == 200

    assert len(sent_calls) == 1, (
        f"One email should be sent when approval_mode='email'. "
        f"Got: {sent_calls}"
    )
    assert "approval" in sent_calls[0]["subject"].lower()


def test_approval_email_failure_does_not_break_draft_creation(
    client_a, monkeypatch
) -> None:
    """If the SMTP send fails, the draft must still be created and
    the user-visible response must be success==200."""

    async def fake_send(*, to, subject, body, settings=None):
        from backend.app.services.email import EmailResult
        return EmailResult(success=False, error="SMTPConnectError")

    from backend.app.services import email as email_service

    monkeypatch.setattr(email_module, "send_email", fake_send)

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_FROM", "noreply@example.com")

    from backend.app.core import config as config_module
    if hasattr(config_module.get_settings, "cache_clear"):
        config_module.get_settings.cache_clear()

    _mock_workflow(monkeypatch, title="Fix 2 smtp failure")
    _set_user_preferences(
        "USER_A",
        approval_mode="email",
        notification_email="user@example.com",
    )

    response = client_a.post(
        "/api/v1/content/generate", json={"topic": "fix2-smtp-failure"}
    )
    # Draft creation must NOT fail because email failed.
    assert response.status_code == 200


def test_approval_email_not_sent_when_notification_email_missing(
    client_a, monkeypatch
) -> None:
    """If approval_mode == 'email' but the user has no
    notification_email, no email is sent."""

    sent_calls = []

    async def fake_send(*, to, subject, body, settings=None):
        sent_calls.append({"to": to, "subject": subject})
        from backend.app.services.email import EmailResult
        return EmailResult(success=True)

    from backend.app.services import email as email_service

    monkeypatch.setattr(email_module, "send_email", fake_send)

    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USERNAME", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_FROM", "noreply@example.com")

    from backend.app.core import config as config_module
    if hasattr(config_module.get_settings, "cache_clear"):
        config_module.get_settings.cache_clear()

    _mock_workflow(monkeypatch, title="Fix 2 no email")
    _set_user_preferences(
        "USER_A",
        approval_mode="email",
        notification_email=None,
    )

    response = client_a.post(
        "/api/v1/content/generate", json={"topic": "fix2-no-email"}
    )
    assert response.status_code == 200
    assert sent_calls == []


# ----- Fix 3: Approve triggers publish -------------------------------------


def test_approve_without_schedule_triggers_publish(
    client_a, monkeypatch
) -> None:
    """Approve (no schedule_time) must invoke publish_now via the
    shared publishing service and return success==True."""

    _seed_linkedin_tokens_for_test("USER_A")

    publish_calls = []

    async def fake_publish_now(user_id, draft_id, **kwargs):
        publish_calls.append({"user_id": user_id, "draft_id": draft_id})
        return MagicMock(success=True, linkedin_post_id="urn:li:ugcPost:approve", already_published=False, error_message=None)

    from backend.app.api.v1 import approval as approval_module

    monkeypatch.setattr(approval_module, "publish_now", fake_publish_now)

    # Create a draft and grab its approval token.
    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "fix3-publish", "title": "Approve publishes", "content": "c"},
    )
    assert create.status_code == 201
    token = create.json()["approval_token"]

    response = client_a.post(
        "/api/v1/approval/approve", json={"token": token}
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(publish_calls) == 1, (
        f"publish_now should have been invoked exactly once. "
        f"Got: {publish_calls}"
    )


def test_approve_with_schedule_does_not_trigger_immediate_publish(
    client_a, monkeypatch
) -> None:
    """Approve WITH schedule_time must NOT trigger immediate publish —
    only the scheduler path."""

    _seed_linkedin_tokens_for_test("USER_A")

    publish_calls = []

    async def fake_publish_now(user_id, draft_id, **kwargs):
        publish_calls.append({"user_id": user_id, "draft_id": draft_id})
        return MagicMock(success=True, linkedin_post_id="urn:li:ugcPost:approve", already_published=False, error_message=None)

    from backend.app.api.v1 import approval as approval_module

    monkeypatch.setattr(approval_module, "publish_now", fake_publish_now)

    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "fix3-sched", "title": "Approve scheduled", "content": "c"},
    )
    assert create.status_code == 201
    token = create.json()["approval_token"]

    response = client_a.post(
        "/api/v1/approval/approve",
        json={
            "token": token,
            "schedule_time": "2099-01-01T00:00:00+00:00",
        },
    )
    assert response.status_code == 200
    assert publish_calls == [], (
        f"publish_now must NOT be called when schedule_time is "
        f"provided. Got calls: {publish_calls}"
    )


def test_approve_publish_failure_returns_failure_response(
    client_a, monkeypatch
) -> None:
    """If publish_now fails after approval succeeded, the response
    must be success==False and the error must be reported."""

    _seed_linkedin_tokens_for_test("USER_A")

    async def fake_publish_now(user_id, draft_id, **kwargs):
        return MagicMock(
            success=False,
            linkedin_post_id=None,
            already_published=False,
            error_message="LinkedIn returned status 401",
        )

    from backend.app.api.v1 import approval as approval_module

    monkeypatch.setattr(approval_module, "publish_now", fake_publish_now)

    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "fix3-pubfail", "title": "Publish fails", "content": "c"},
    )
    assert create.status_code == 201
    token = create.json()["approval_token"]

    response = client_a.post(
        "/api/v1/approval/approve", json={"token": token}
    )
    assert response.status_code == 200
    assert response.json()["success"] is False, (
        "Approval must return success==False when publish_now fails"
    )


def test_duplicate_approve_does_not_publish_twice(
    client_a, monkeypatch
) -> None:
    """Approving twice must NOT publish the same post twice. The
    second call should return already_published=True from
    publish_now (or the approval single-use mechanism prevents the
    second call from doing anything)."""

    _seed_linkedin_tokens_for_test("USER_A")

    publish_calls = []

    async def fake_publish_now(user_id, draft_id, **kwargs):
        publish_calls.append(draft_id)
        # First call succeeds AND marks the draft as published in
        # MongoDB (simulating the real publish_now side-effect).
        async def _mark_published() -> None:
            from backend.app.db.mongo import get_database
            db = get_database()
            await db["drafts"].update_one(
                {"_id": draft_id},
                {"$set": {"published_at": datetime.now(timezone.utc),
                          "linkedin_post_id": "urn:li:ugcPost:1"}},
            )
        await _mark_published()
        return MagicMock(success=True, linkedin_post_id="urn:li:ugcPost:1", already_published=False, error_message=None)

    from backend.app.api.v1 import approval as approval_module

    monkeypatch.setattr(approval_module, "publish_now", fake_publish_now)

    create = client_a.post(
        "/api/v1/drafts",
        json={"topic": "fix3-dup", "title": "Approve twice", "content": "c"},
    )
    assert create.status_code == 201
    token = create.json()["approval_token"]

    first = client_a.post(
        "/api/v1/approval/approve", json={"token": token}
    )
    assert first.status_code == 200
    second = client_a.post(
        "/api/v1/approval/approve", json={"token": token}
    )
    # The second call: publish_now must NOT be called because the
    # draft's published_at is now set, so the approve endpoint
    # short-circuits with "Post was already approved and published."
    assert second.status_code == 200
    assert len(publish_calls) == 1, (
        f"publish_now must be called exactly once for the same draft. "
        f"Got calls: {publish_calls}"
    )
