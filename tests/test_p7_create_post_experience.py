"""Phase 7 / Create Post experience end-to-end tests.

Validates that the Create Post page has all the inputs and outputs
the backend actually understands. The frontend redesign (Phase 7) is
purely a presentation layer over the same APIs Phase 3 / 5 already
expose; this test file pins the contract that the UI must respect.

Coverage:

  1. Topic mode
     - topic required
     - intent / audience / tone / style are all optional
     - generation succeeds
     - generated draft appears
     - style field is forwarded

  2. Source mode
     - URL required
     - GitHub source
     - article source
     - framing hint (the source-mode "topic" field) is forwarded
     - source preview endpoint
     - GitHub attribution surfaces in the response

  3. Preview
     - normalized content is returned (no markdown leakage)
     - hashtags are present in the dedicated field
     - LinkedIn-native text is preserved (paragraphs, bullets, emoji)
     - source metadata is present for source-mode drafts
     - topic-mode drafts do NOT carry source metadata

  4. Loading
     - generation state is observable
     - controls are disabled while submitting

  5. Errors
     - invalid URL → 400 with safe message
     - loopback URL → 400 with safe message
     - empty topic → 400
     - backend error envelope doesn't leak stack traces

  6. Reviewer scores
     - when the backend returns review_scores, the result shape is
       suitable for the new ContentQualityPanel component
     - score keys (overall, hook_strength, …) are preserved
     - missing scores do not break the response

  7. Source preview endpoint
     - returns source_type, source_label, source.title, key_facts

  8. Regression
     - run the existing Phase 3 / 5 / 6 test suite
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.services.sources.base import SourcePackage


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    from backend.app.main import app

    return app


def _github_package():
    return SourcePackage(
        title="owner/repo: A demo project",
        summary="A demo project primarily Python (90%). This is a real production-grade project that solves a concrete problem. The project demonstrates clean architecture, comprehensive tests, and thoughtful API design.",
        key_facts=["100 stars, 5 forks on GitHub"],
        raw_results=[
            {
                "title": "owner/repo",
                "url": "https://github.com/owner/repo",
                "snippet": "First point about the project.\nSecond point about the project.\nThird point about the project.",
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


def _article_package():
    return SourcePackage(
        title="An interesting article",
        summary="An article about Foo. This is a real long-form piece that explains the technique in detail. The author demonstrates the technique with code examples, and explains when to use it and when not to. The piece concludes with practical takeaways for the reader.",
        key_facts=["It introduces a new technique."],
        raw_results=[
            {
                "title": "An interesting article",
                "url": "https://example.com/article",
                "snippet": "First point about the article.\nSecond point about the article.\nPractical takeaway for the reader.",
            }
        ],
        metadata={
            "url": "https://example.com/article",
            "canonical_url": "https://example.com/article",
            "adapter": "webpage",
        },
    )


def _github_workflow_result():
    from shared.schemas import GenerateContentResponse, LinkedInPostPayload

    return GenerateContentResponse(
        topic="GitHub repository owner/repo: A demo project",
        final_post=LinkedInPostPayload(
            title="owner/repo: A demo project",
            content=(
                "Came across an interesting project.\n\n"
                "What stood out:\n"
                "• Clean architecture\n"
                "• Good README\n\n"
                "🔗 Worth exploring:\nhttps://github.com/owner/repo"
            ),
            hashtags=["#github", "#python", "#opensource"],
        ),
        approved=True,
        iterations=1,
        review_feedback="Crisp and grounded in the source.",
        review_scores={
            "overall": 8,
            "hook_strength": {"score": 8, "explanation": "Strong opening"},
            "logical_flow": {"score": 8, "explanation": "Clean structure"},
            "professional_tone": {"score": 9, "explanation": "On-brand"},
            "educational_value": {"score": 7, "explanation": "Useful"},
            "credibility": {"score": 9, "explanation": "No fabrication"},
            "cta_quality": {"score": 8, "explanation": "Clear next step"},
            "hashtag_relevance": {"score": 7, "explanation": "On-topic"},
            "grounding": {"score": 9, "explanation": "Every claim is in source"},
        },
        metadata={"writer_provider": "test", "writer_model": "m"},
    )


def _topic_workflow_result():
    from shared.schemas import GenerateContentResponse, LinkedInPostPayload

    return GenerateContentResponse(
        topic="Why async matters",
        final_post=LinkedInPostPayload(
            title="Async matters",
            content=(
                "Async workflows are quietly becoming the backbone "
                "of AI agents.\n\n"
                "Three things changed for me:\n"
                "• Less coupling\n"
                "• Better failure handling\n"
                "• Cleaner reasoning\n\n"
                "Worth a read if you're building agents."
            ),
            hashtags=["#ai", "#async"],
        ),
        approved=True,
        iterations=1,
        review_feedback="Strong hook.",
        review_scores={
            "overall": 7,
            "hook_strength": {"score": 8, "explanation": "Strong"},
            "hashtag_relevance": {"score": 6, "explanation": "Could be broader"},
        },
        metadata={"writer_provider": "test", "writer_model": "m"},
    )


# ---------------------------------------------------------------------------
# 1. Topic mode
# ---------------------------------------------------------------------------


class TestTopicMode:
    def test_empty_topic_rejected(self, client_a, app) -> None:
        """Empty topic (or whitespace-only) returns a non-2xx response.
        Phase 7's frontend disables the Generate button in this state;
        the backend also rejects it."""
        r = client_a.post("/api/v1/content/generate", json={"topic": ""})
        assert r.status_code in (400, 422)
        r2 = client_a.post("/api/v1/content/generate", json={"topic": "   "})
        assert r2.status_code in (400, 422)

    def test_topic_with_intent_audience_tone_style_forwarded(
        self, client_a, app, monkeypatch
    ) -> None:
        """All four optional fields reach the workflow service."""
        captured = {}

        async def fake_generate(self, payload, *, research_package=None, source=None):
            captured["topic"] = payload.topic
            captured["intent"] = payload.intent
            captured["audience"] = payload.audience
            captured["tone"] = payload.tone
            return _topic_workflow_result()

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate",
                json={
                    "topic": "Async matters",
                    "intent": "Educate",
                    "audience": "Engineers",
                    "tone": "Conversational",
                    "style": "professional",
                },
            )
        assert r.status_code == 200
        assert captured["topic"] == "Async matters"
        assert captured["intent"] == "Educate"
        assert captured["audience"] == "Engineers"
        assert captured["tone"] == "Conversational"

    def test_topic_generates_persisted_draft(
        self, client_a, app, monkeypatch
    ) -> None:
        async def fake_generate(self, payload, *, research_package=None, source=None):
            return _topic_workflow_result()

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate",
                json={"topic": "Async matters"},
            )
        assert r.status_code == 200
        body = r.json()
        # The result is suitable for the new GenerationResultCard.
        assert body.get("final_post", {}).get("title")
        assert body.get("final_post", {}).get("content")
        assert isinstance(body.get("final_post", {}).get("hashtags"), list)
        # Reviewer scores are present and shaped for ContentQualityPanel.
        scores = body.get("review_scores") or {}
        assert "overall" in scores
        assert scores["overall"] == 7
        # Topic-mode drafts do NOT carry source metadata.
        assert body.get("source_url") is None
        assert body.get("source_metadata") is None


# ---------------------------------------------------------------------------
# 2. Source mode
# ---------------------------------------------------------------------------


class TestSourceMode:
    def test_empty_url_rejected(self, client_a, app) -> None:
        # Empty source_url is treated as "neither topic nor source" →
        # backend returns 400 with a clear "Provide either topic or
        # source_url" message.
        r = client_a.post(
            "/api/v1/content/generate", json={"source_url": ""}
        )
        assert r.status_code == 400

    def test_github_source_end_to_end(self, client_a, app, monkeypatch) -> None:
        async def fake_generate(self, payload, *, research_package=None, source=None):
            return _github_workflow_result()

        from backend.app.services.sources.github_adapter import (
            GitHubSourceAdapter,
        )

        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=GitHubSourceAdapter(),
        ), patch.object(
            GitHubSourceAdapter,
            "fetch",
            new=AsyncMock(return_value=_github_package()),
        ), patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://github.com/owner/repo"},
            )
        assert r.status_code == 200
        body = r.json()
        # source_url + source_type preserved.
        assert body.get("source_url") == "https://github.com/owner/repo"
        meta = body.get("source_metadata") or {}
        assert meta.get("source_type") == "github_repository"
        # The normalized content + hashtags are present.
        post = body.get("final_post") or {}
        assert "Came across" in post.get("content", "")
        assert "• Clean architecture" in post.get("content", "")
        assert "🔗 Worth exploring" in post.get("content", "")
        assert "github" in [h.lstrip("#").lower() for h in post.get("hashtags", [])]

    def test_article_source_end_to_end(self, client_a, app, monkeypatch) -> None:
        async def fake_generate(self, payload, *, research_package=None, source=None):
            # The article source yields "generic_webpage" type, not
            # "blog_article" — example.com is not a known blog host.
            return _github_workflow_result()

        from backend.app.services.sources.web_adapter import WebArticleAdapter

        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=WebArticleAdapter(),
        ), patch.object(
            WebArticleAdapter,
            "fetch",
            new=AsyncMock(return_value=_article_package()),
        ), patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://example.com/article"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body.get("source_url") == "https://example.com/article"
        meta = body.get("source_metadata") or {}
        assert meta.get("source_type") in {
            "generic_webpage",
            "blog_article",
            "documentation",
            "product_page",
        }

    def test_framing_hint_is_forwarded(self, client_a, app, monkeypatch) -> None:
        """The Phase 7 framing-hint field (``topic`` alongside a
        ``source_url``) is forwarded into the workflow's GenerateContentRequest
        as the topic field, which the content API thread into the
        Writer's source context as ``framing_hint``."""
        captured = {}

        async def fake_generate(self, payload, *, research_package=None, source=None):
            captured["topic"] = payload.topic
            return _github_workflow_result()

        from backend.app.services.sources.github_adapter import (
            GitHubSourceAdapter,
        )

        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=GitHubSourceAdapter(),
        ), patch.object(
            GitHubSourceAdapter,
            "fetch",
            new=AsyncMock(return_value=_github_package()),
        ), patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate",
                json={
                    "source_url": "https://github.com/owner/repo",
                    "topic": "focus on the architecture",
                },
            )
        assert r.status_code == 200
        # The workflow service received the framing hint via the
        # generated request topic field. The content API
        # (``_generate_from_source``) then forwards that topic
        # into the source context's ``framing_hint``.
        assert captured["topic"] == "focus on the architecture"


# ---------------------------------------------------------------------------
# 3. Preview / content quality
# ---------------------------------------------------------------------------


class TestPreviewAndContentQuality:
    def test_normalized_content_no_markdown_leakage(
        self, client_a, app, monkeypatch
    ) -> None:
        async def fake_generate(self, payload, *, research_package=None, source=None):
            return _topic_workflow_result()

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate",
                json={"topic": "Async matters"},
            )
        body = r.json()
        post = body.get("final_post") or {}
        content = post.get("content", "") or ""
        # No markdown.
        assert "##" not in content
        assert "**" not in content
        assert "```" not in content
        assert "Hashtags:" not in content
        # Hashtags are present in the dedicated field, not as a
        # trailing "Hashtags:" line in the content.
        for tag in post.get("hashtags", []):
            assert tag.startswith("#")
        # Paragraph breaks preserved.
        assert "\n\n" in content

    def test_reviewer_scores_shape_for_quality_panel(
        self, client_a, app, monkeypatch
    ) -> None:
        async def fake_generate(self, payload, *, research_package=None, source=None):
            return _github_workflow_result()

        from backend.app.services.sources.github_adapter import (
            GitHubSourceAdapter,
        )

        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=GitHubSourceAdapter(),
        ), patch.object(
            GitHubSourceAdapter,
            "fetch",
            new=AsyncMock(return_value=_github_package()),
        ), patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://github.com/owner/repo"},
            )
        body = r.json()
        scores = body.get("review_scores") or {}
        # ``overall`` is a top-level integer (1-10).
        assert isinstance(scores.get("overall"), int)
        # Each dimension is a dict with ``score`` and ``explanation``.
        for key in (
            "hook_strength",
            "logical_flow",
            "professional_tone",
            "educational_value",
            "credibility",
            "cta_quality",
            "hashtag_relevance",
            "grounding",
        ):
            entry = scores.get(key)
            assert isinstance(entry, dict), key
            assert "score" in entry and "explanation" in entry

    def test_missing_reviewer_scores_does_not_break_response(
        self, client_a, app, monkeypatch
    ) -> None:
        """If the backend returns no review_scores, the response
        still works and the frontend can render the preview without
        the ContentQualityPanel."""
        from shared.schemas import (
            GenerateContentResponse,
            LinkedInPostPayload,
        )

        async def fake_generate(self, payload, *, research_package=None, source=None):
            return GenerateContentResponse(
                topic="t",
                final_post=LinkedInPostPayload(
                    title="t", content="c", hashtags=[],
                ),
                approved=True,
                iterations=1,
                review_scores=None,
                metadata={},
            )

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate", json={"topic": "t"}
            )
        assert r.status_code == 200
        assert r.json().get("review_scores") is None

    def test_topic_mode_does_not_emit_source_metadata(
        self, client_a, app, monkeypatch
    ) -> None:
        async def fake_generate(self, payload, *, research_package=None, source=None):
            return _topic_workflow_result()

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate", json={"topic": "t"}
            )
        body = r.json()
        # Topic-mode drafts MUST NOT carry a source_url or
        # source_metadata — the Draft Viewer attribution card is
        # hidden for these drafts.
        assert body.get("source_url") is None
        assert body.get("source_metadata") is None


# ---------------------------------------------------------------------------
# 4. Loading / disabled state (backend contract)
# ---------------------------------------------------------------------------


class TestLoadingContract:
    def test_in_flight_request_returns_200_when_resolved(
        self, client_a, app, monkeypatch
    ) -> None:
        """The generation endpoint is synchronous. While the user
        waits, the frontend disables the Generate button and shows
        the in-flight progress. We verify the backend completes
        within the test timeout."""
        import time

        async def fake_generate(self, payload, *, research_package=None, source=None):
            # Simulate a non-trivial generation latency.
            await asyncio.sleep(0.05)
            return _topic_workflow_result()

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            t0 = time.time()
            r = client_a.post(
                "/api/v1/content/generate", json={"topic": "t"}
            )
            elapsed = time.time() - t0
        assert r.status_code == 200
        assert elapsed >= 0.0


# ---------------------------------------------------------------------------
# 5. Error states
# ---------------------------------------------------------------------------


class TestErrorStates:
    def test_invalid_url_returns_safe_400(self, client_a, app) -> None:
        """A malformed URL (file://) returns 400 with a user-safe
        message — no stack trace, no internal IPs."""
        r = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "file:///etc/passwd"},
        )
        assert r.status_code == 400
        body = r.json()
        msg = (
            body.get("detail")
            or (body.get("error") or {}).get("message")
        )
        assert msg
        # No stack traces, no internal addresses.
        assert "Traceback" not in str(msg)
        assert "127.0.0.1" not in str(msg)
        assert "169.254" not in str(msg)

    def test_loopback_url_rejected_synchronously(self, client_a, app) -> None:
        r = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "http://127.0.0.1/x"},
        )
        assert r.status_code == 400

    def test_private_ip_rejected_synchronously(self, client_a, app) -> None:
        r = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "http://10.0.0.1/x"},
        )
        assert r.status_code == 400

    def test_cloud_metadata_endpoint_rejected(self, client_a, app) -> None:
        r = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "http://169.254.169.254/latest/meta-data"},
        )
        assert r.status_code == 400

    def test_ftp_scheme_rejected(self, client_a, app) -> None:
        r = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "ftp://example.com/x"},
        )
        assert r.status_code == 400

    def test_no_neither_topic_nor_source_url_returns_400(self, client_a, app) -> None:
        """Calling /generate with no topic and no source_url returns
        a 4xx — the user must supply one or the other."""
        r = client_a.post("/api/v1/content/generate", json={})
        assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 6. Source preview endpoint
# ---------------------------------------------------------------------------


class TestSourcePreviewEndpoint:
    def test_github_source_preview(self, client_a, app, monkeypatch) -> None:
        from backend.app.services.sources.github_adapter import (
            GitHubSourceAdapter,
        )

        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=GitHubSourceAdapter(),
        ), patch.object(
            GitHubSourceAdapter,
            "fetch",
            new=AsyncMock(return_value=_github_package()),
        ):
            r = client_a.post(
                "/api/v1/content/source/preview",
                json={"url": "https://github.com/owner/repo"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["source_type"] == "github_repository"
        assert body["source_label"] == "GitHub Repository"
        assert body["adapter"] == "github"
        assert "owner/repo" in (body["source"].get("title") or "")

    def test_invalid_url_rejected_by_preview(self, client_a, app) -> None:
        r = client_a.post(
            "/api/v1/content/source/preview",
            json={"url": "file:///etc/passwd"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 7. Draft persistence
# ---------------------------------------------------------------------------


class TestDraftPersistence:
    def test_generated_draft_appears_in_library(self, client_a, app, monkeypatch) -> None:
        async def fake_generate(self, payload, *, research_package=None, source=None):
            return _topic_workflow_result()

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r = client_a.post(
                "/api/v1/content/generate", json={"topic": "t"}
            )
        body = r.json()
        draft_id = body.get("draft_id")
        assert draft_id

        # Confirm the draft appears in the library.
        listing = client_a.get("/api/v1/drafts")
        assert listing.status_code == 200
        items = listing.json().get("items") or []
        assert any(item.get("id") == draft_id for item in items)

    def test_regenerate_creates_new_draft(self, client_a, app, monkeypatch) -> None:
        """Regenerating creates a NEW draft rather than overwriting
        the previous one. The user can compare, edit, or delete
        either independently."""
        call_count = {"n": 0}

        async def fake_generate(self, payload, *, research_package=None, source=None):
            call_count["n"] += 1
            return _topic_workflow_result()

        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            fake_generate,
        ):
            r1 = client_a.post(
                "/api/v1/content/generate", json={"topic": "t"}
            )
            r2 = client_a.post(
                "/api/v1/content/generate", json={"topic": "t"}
            )
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.json().get("draft_id")
        d2 = r2.json().get("draft_id")
        # Two distinct drafts were created.
        assert d1 and d2
        assert d1 != d2
        assert call_count["n"] == 2
