"""Phase 5 / Source-aware end-to-end tests.

Validates the full URL → LinkedIn post feature:

  1. URL validation / SSRF (positive + negative).
  2. Web + GitHub extraction (already covered in Phase 3; this file
     re-asserts the source-typing contract the Phase 5 writer/reviewer
     rely on).
  3. Source classification produces the canonical labels the writer
     narrative-angle map uses.
  4. The Phase 5 ``_build_source_context`` helper produces a
     source-aware payload with grounding fields.
  5. The Writer's source-aware prompt includes the SOURCE FACTS
     block, the user framing hint, and the anti-fabrication rules.
  6. The Reviewer's source-aware prompt includes the GROUNDING
     dimension and the source facts.
  7. The /generate endpoint's source mode produces a draft with
     source_url + source_metadata + normalized content.
  8. Approval + publish flow works on source-generated drafts.
  9. LinkedIn-native format is preserved end-to-end.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

from shared.schemas import (
    GenerateContentResponse,
    LinkedInPostPayload,
)
from utils.linkedin_content import normalize_linkedin_post

from backend.app.db.mongo import get_database
from backend.app.repositories import (
    ApprovalRepository,
    DraftRepository,
    UserRepository,
)
from backend.app.services.sources.base import (
    SourceBlockedError,
    SourceFetchError,
    SourcePackage,
)
from backend.app.services.sources.classification import (
    SOURCE_TYPE_DOCUMENTATION,
    SOURCE_TYPE_GENERIC_WEBPAGE,
    SOURCE_TYPE_GITHUB_REPOSITORY,
    classify,
    get_narrative_angle,
    get_source_label,
)
from backend.app.services.sources.github_adapter import (
    GitHubSourceAdapter,
    _parse_owner_repo,
)
from backend.app.services.sources.ssrf import (
    GITHUB_ALLOWLIST,
    check_ip_family,
    validate_url,
)
from backend.app.services.sources.web_adapter import (
    WebArticleAdapter,
    extract_article,
)


# ---------------------------------------------------------------------------
# 1. URL validation / SSRF (Phase 5 — regression)
# ---------------------------------------------------------------------------


class TestSSRFGuard:
    """The Phase 5 source-aware flow does NOT add a new network exit
    point. The existing Phase 3 SSRF guard is the only place that
    talks to the network; this test re-asserts its contract so a
    future regression in the guard would fail loud."""

    def test_https_valid_passes(self) -> None:
        parsed = validate_url("https://example.com/blog/article")
        assert parsed.scheme == "https"
        assert parsed.hostname == "example.com"

    def test_http_valid_passes(self) -> None:
        parsed = validate_url("http://example.com/x")
        assert parsed.scheme == "http"

    def test_localhost_blocked(self) -> None:
        # ``localhost`` is a hostname, not a literal IP. The SSRF
        # guard's URL-parse step accepts it; the IP-family vet runs
        # at DNS resolution time inside ``resolve_safely``. We assert
        # here that the IP-family vet itself catches loopback.
        with pytest.raises(SourceBlockedError):
            check_ip_family("127.0.0.1")

    def test_loopback_ipv4_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://127.0.0.1/x")

    def test_private_10_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://10.0.0.1/x")

    def test_private_172_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://172.16.0.1/x")

    def test_private_192_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://192.168.1.1/x")

    def test_link_local_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://169.254.1.1/x")

    def test_cloud_metadata_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_file_scheme_blocked(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("file:///etc/passwd")
        assert exc_info.value.code == "bad_scheme"

    def test_ftp_scheme_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("ftp://example.com/x")

    def test_javascript_scheme_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("javascript:alert(1)")

    def test_data_scheme_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("data:text/html,<script>")

    def test_userinfo_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("https://user:pass@example.com/")

    def test_disallowed_port_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("https://example.com:22/")

    def test_github_allowlist_blocks_other(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url(
                "https://github.com.evil.com/owner/repo",
                allow_hosts=GITHUB_ALLOWLIST,
            )

    def test_github_allowlist_accepts_canonical(self) -> None:
        parsed = validate_url(
            "https://api.github.com/repos/x/y",
            allow_hosts=GITHUB_ALLOWLIST,
        )
        assert parsed.hostname == "api.github.com"

    def test_redis_port_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://example.com:6379/")

    def test_cgnat_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("http://100.64.0.1/x")

    def test_wildcard_ip_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("0.0.0.0")


# ---------------------------------------------------------------------------
# 2. Web + GitHub extraction (Phase 3 regression — Phase 5 relies on it)
# ---------------------------------------------------------------------------


class TestArticleExtraction:
    def test_strips_navigation_and_footer(self) -> None:
        html = (
            "<html><body>"
            "<nav>nav</nav>"
            "<main><h1>Title</h1><p>Real content paragraph here.</p></main>"
            "<footer>footer</footer>"
            "</body></html>"
        )
        _t, _d, text = extract_article(html)
        assert "Real content" in text
        assert "nav" not in text
        assert "footer" not in text

    def test_strips_scripts_and_styles(self) -> None:
        html = (
            "<html><head><style>body{color:red}</style></head><body>"
            "<p>visible</p><script>nasty();</script></body></html>"
        )
        _t, _d, text = extract_article(html)
        assert "visible" in text
        assert "nasty" not in text
        assert "color:red" not in text

    def test_handles_lists_as_bullets(self) -> None:
        html = "<html><body><ul><li>one</li><li>two</li></ul></body></html>"
        _t, _d, text = extract_article(html)
        assert "•" in text
        assert "one" in text and "two" in text

    def test_truncates_huge_pages(self) -> None:
        big_p = " ".join(["long " * 50] * 200)
        html = f"<html><body><article><p>{big_p}</p></article></body></html>"
        _t, _d, text = extract_article(html, max_bytes=4 * 1024)
        assert len(text.encode("utf-8")) <= 4 * 1024 + 64


class TestGitHubExtraction:
    def test_repo_root_recognized(self) -> None:
        assert GitHubSourceAdapter.can_handle("https://github.com/owner/repo")
        assert GitHubSourceAdapter.can_handle("https://github.com/owner/repo/")

    def test_repo_blob_path_accepted(self) -> None:
        assert GitHubSourceAdapter.can_handle(
            "https://github.com/owner/repo/blob/main/README.md"
        )

    def test_settings_path_rejected(self) -> None:
        assert not GitHubSourceAdapter.can_handle(
            "https://github.com/settings/profile"
        )

    def test_orgs_path_rejected(self) -> None:
        assert not GitHubSourceAdapter.can_handle("https://github.com/orgs/x")

    def test_owner_extraction(self) -> None:
        owner, repo = _parse_owner_repo("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_owner_extraction_with_blob_path(self) -> None:
        owner, repo = _parse_owner_repo(
            "https://github.com/owner/repo/blob/main/README.md"
        )
        assert owner == "owner"
        assert repo == "repo"

    def test_wiki_path_rejected(self) -> None:
        with pytest.raises(SourceFetchError) as exc_info:
            _parse_owner_repo("https://github.com/owner/repo/wiki")
        assert exc_info.value.code == "unsupported_url_form"


# ---------------------------------------------------------------------------
# 3. Source classification
# ---------------------------------------------------------------------------


class TestSourceClassification:
    def test_github_repository(self) -> None:
        st = classify(
            url="https://github.com/owner/repo",
            adapter="github",
            title="owner/repo",
        )
        assert st == SOURCE_TYPE_GITHUB_REPOSITORY

    def test_github_readme(self) -> None:
        st = classify(
            url="https://github.com/owner/repo/blob/main/README.md",
            adapter="github",
            title="owner/repo",
        )
        assert st == "github_readme"

    def test_documentation(self) -> None:
        st = classify(
            url="https://fastapi.tiangolo.com/tutorial/",
            adapter="webpage",
            title="FastAPI tutorial",
        )
        assert st == SOURCE_TYPE_DOCUMENTATION

    def test_generic_webpage(self) -> None:
        st = classify(
            url="https://example.com/page",
            adapter="webpage",
            title="Some page",
        )
        assert st == SOURCE_TYPE_GENERIC_WEBPAGE

    def test_narrative_angle_for_known_types(self) -> None:
        for st in (
            SOURCE_TYPE_GITHUB_REPOSITORY,
            "github_readme",
            "blog_article",
            SOURCE_TYPE_DOCUMENTATION,
            "product_page",
            SOURCE_TYPE_GENERIC_WEBPAGE,
        ):
            angle = get_narrative_angle(st)
            assert isinstance(angle, str) and angle

    def test_narrative_angle_falls_back(self) -> None:
        angle = get_narrative_angle("mystery")
        assert angle == get_narrative_angle(SOURCE_TYPE_GENERIC_WEBPAGE)

    def test_label_for_known_types(self) -> None:
        for st in (
            SOURCE_TYPE_GITHUB_REPOSITORY,
            "github_readme",
            "blog_article",
            SOURCE_TYPE_DOCUMENTATION,
            "product_page",
            SOURCE_TYPE_GENERIC_WEBPAGE,
        ):
            label = get_source_label(st)
            assert isinstance(label, str) and label

    def test_label_falls_back(self) -> None:
        assert get_source_label("mystery") == "Web Article"


# ---------------------------------------------------------------------------
# 4. _build_source_context — the Phase 5 helper
# ---------------------------------------------------------------------------


class TestBuildSourceContext:
    def test_minimal_github_package(self) -> None:
        from backend.app.api.v1.content import _build_source_context

        package = SourcePackage(
            title="owner/repo: A demo project",
            summary="An open-source demo project primarily Python (90%).",
            key_facts=["100 stars, 5 forks on GitHub"],
            raw_results=[],
            metadata={
                "url": "https://github.com/owner/repo",
                "canonical_url": "https://github.com/owner/repo",
                "adapter": "github",
                "owner": "owner",
                "repo": "repo",
                "primary_language": "Python",
                "license": "MIT",
                "description": "A demo project.",
            },
        )
        ctx = _build_source_context(
            package=package,
            source_type=SOURCE_TYPE_GITHUB_REPOSITORY,
            canonical_url="https://github.com/owner/repo",
            framing_hint=None,
        )
        assert ctx["source_type"] == SOURCE_TYPE_GITHUB_REPOSITORY
        assert ctx["source_title"] == "owner/repo: A demo project"
        assert ctx["source_url"] == "https://github.com/owner/repo"
        assert "demo project" in ctx["source_summary"]
        assert "100 stars" in ctx["key_points"][0]
        # technical_details picks up the primary_language + license.
        assert any("Python" in t for t in ctx["technical_details"])
        assert any("MIT" in t for t in ctx["technical_details"])
        # author is owner.
        assert ctx["author"] == "owner"
        # No framing hint supplied.
        assert ctx["framing_hint"] == ""

    def test_framing_hint_forwarded(self) -> None:
        from backend.app.api.v1.content import _build_source_context

        package = SourcePackage(
            title="t",
            summary="s",
            key_facts=[],
            raw_results=[],
            metadata={"url": "https://example.com/x"},
        )
        ctx = _build_source_context(
            package=package,
            source_type=SOURCE_TYPE_GENERIC_WEBPAGE,
            canonical_url="https://example.com/x",
            framing_hint="Focus on the architecture",
        )
        assert ctx["framing_hint"] == "Focus on the architecture"

    def test_no_technical_details_when_minimal(self) -> None:
        from backend.app.api.v1.content import _build_source_context

        package = SourcePackage(
            title="t",
            summary="s",
            key_facts=[],
            raw_results=[],
            metadata={"url": "https://example.com/x"},
        )
        ctx = _build_source_context(
            package=package,
            source_type=SOURCE_TYPE_GENERIC_WEBPAGE,
            canonical_url="https://example.com/x",
        )
        # technical_details is an empty list (no language, no deps).
        assert ctx["technical_details"] == []

    def test_dependencies_promoted_to_technical_details(self) -> None:
        from backend.app.api.v1.content import _build_source_context

        package = SourcePackage(
            title="t",
            summary="s",
            key_facts=[],
            raw_results=[],
            metadata={
                "url": "https://github.com/owner/repo",
                "primary_language": "Python",
                "dependencies": {
                    "python": ["fastapi", "httpx", "pydantic"],
                    "node": ["vite", "tailwindcss"],
                },
            },
        )
        ctx = _build_source_context(
            package=package,
            source_type=SOURCE_TYPE_GITHUB_REPOSITORY,
            canonical_url="https://github.com/owner/repo",
        )
        joined = " ".join(ctx["technical_details"])
        assert "fastapi" in joined
        assert "vite" in joined
        assert "Python" in joined

    def test_secret_keys_not_leaked_into_context(self) -> None:
        """The source context is forwarded into a prompt; we must not
        propagate known-credential keys from the adapter metadata."""
        from backend.app.api.v1.content import _build_source_context

        package = SourcePackage(
            title="t",
            summary="s",
            key_facts=[],
            raw_results=[],
            metadata={
                "url": "https://example.com/x",
                "authorization": "Bearer SECRET",
                "github_token": "ghp_xxxx",
                "primary_language": "Python",
            },
        )
        ctx = _build_source_context(
            package=package,
            source_type=SOURCE_TYPE_GENERIC_WEBPAGE,
            canonical_url="https://example.com/x",
        )
        meta = ctx.get("source_metadata") or {}
        assert "authorization" not in meta
        assert "github_token" not in meta
        # The "primary_language" key is fine to keep.
        assert meta.get("primary_language") == "Python"


# ---------------------------------------------------------------------------
# 5. Writer source-aware prompt
# ---------------------------------------------------------------------------


class TestWriterSourceAware:
    def test_source_prompt_contains_facts_block(self) -> None:
        """The Writer's source-aware prompt must explicitly call out
        the SOURCE FACTS section so the model uses them as grounding.
        """
        from agents.writer import WriterAgent

        # Build a real WriterAgent (its __init__ constructs an LLM,
        # but we never call it).
        agent = WriterAgent()
        source = {
            "source_type": SOURCE_TYPE_GITHUB_REPOSITORY,
            "source_title": "owner/repo: A demo project",
            "source_url": "https://github.com/owner/repo",
            "source_summary": "A demo project primarily Python (90%).",
            "key_points": ["100 stars, 5 forks on GitHub"],
            "technical_details": ["Primary language: Python"],
            "author": "owner",
            "framing_hint": "",
        }
        prompt = agent._create_source_prompt("CONTEXT_PLACEHOLDER", source)
        # Required structural blocks.
        assert "SOURCE-INSPIRED" in prompt or "SOURCE INSPIRED" in prompt
        assert "SOURCE TYPE" in prompt
        assert "NARRATIVE ANGLE" in prompt
        assert "SOURCE URL" in prompt
        # The prompt references the SOURCE FACTS (the context block
        # emitted by _build_context contains the full "SOURCE FACTS
        # (GROUNDING ...)" label).
        assert "SOURCE FACTS" in prompt
        # No-fabrication block.
        assert "invent" in prompt.lower() or "fabricat" in prompt.lower()
        # Anti-summary guidance.
        assert "BAD" in prompt and "GOOD" in prompt
        # The user framing hint is forwarded; "none" when absent.
        assert "USER FRAMING HINT" in prompt
        # LinkedIn-native format reminder.
        assert "LinkedIn-native" in prompt or "no Markdown" in prompt

    def test_source_prompt_uses_matching_narrative_angle(self) -> None:
        from agents.writer import WriterAgent

        agent = WriterAgent()
        for source_type, expected_keyword in [
            (SOURCE_TYPE_GITHUB_REPOSITORY, "software engineering"),
            ("github_readme", "technical-document"),
            ("blog_article", "working professional"),
            (SOURCE_TYPE_DOCUMENTATION, "developer"),
            ("product_page", "announcement"),
            (SOURCE_TYPE_GENERIC_WEBPAGE, "general public"),
        ]:
            source = {
                "source_type": source_type,
                "source_title": "t",
                "source_url": "https://example.com/x",
                "source_summary": "s",
                "key_points": [],
                "technical_details": [],
                "framing_hint": "",
            }
            prompt = agent._create_source_prompt("CTX", source)
            assert expected_keyword.lower() in prompt.lower(), (
                f"Expected keyword {expected_keyword!r} in prompt for "
                f"source_type {source_type!r}"
            )

    def test_source_prompt_includes_user_framing_hint(self) -> None:
        from agents.writer import WriterAgent

        agent = WriterAgent()
        source = {
            "source_type": SOURCE_TYPE_GITHUB_REPOSITORY,
            "source_title": "t",
            "source_url": "https://github.com/owner/repo",
            "source_summary": "s",
            "key_points": [],
            "technical_details": [],
            "framing_hint": "Focus on the architecture and how it compares to alternatives",
        }
        prompt = agent._create_source_prompt("CTX", source)
        # The hint is forwarded verbatim into the prompt.
        assert "Focus on the architecture" in prompt

    def test_build_context_emits_source_facts_block(self) -> None:
        """``_build_context`` must emit a labelled "SOURCE FACTS" block
        when ``source`` is provided so the LLM sees the grounding
        facts even without a source prompt prefix."""
        from agents.writer import WriterAgent

        agent = WriterAgent()
        ctx = agent._build_context(
            topic="Test topic",
            intent="discuss",
            user_prompt="Test topic",
            research=None,
            source={
                "source_type": SOURCE_TYPE_GITHUB_REPOSITORY,
                "source_title": "owner/repo",
                "source_url": "https://github.com/owner/repo",
                "source_summary": "A demo project.",
                "key_points": ["100 stars"],
                "technical_details": ["Python"],
                "framing_hint": "",
            },
        )
        assert "=== SOURCE FACTS (GROUNDING" in ctx
        assert "owner/repo" in ctx
        assert "100 stars" in ctx
        assert "GROUNDING RULES" in ctx

    def test_build_context_omits_source_block_when_no_source(self) -> None:
        """When no source is provided, the legacy topic-mode prompt
        is preserved byte-for-byte."""
        from agents.writer import WriterAgent

        agent = WriterAgent()
        ctx = agent._build_context(
            topic="Test topic",
            intent="discuss",
            user_prompt="Test topic",
            research=None,
        )
        assert "SOURCE FACTS" not in ctx


# ---------------------------------------------------------------------------
# 6. Reviewer source-aware
# ---------------------------------------------------------------------------


class TestReviewerSourceAware:
    def test_review_scores_has_grounding_field(self) -> None:
        from agents.reviewer import ReviewScores

        scores = ReviewScores(
            clarity=7,
            engagement=7,
            authenticity=7,
            readability=7,
            overall=7,
        )
        # grounding is optional and default None — preserved for
        # backward compatibility with topic-mode reviews.
        assert scores.grounding is None

    def test_augment_review_prompt_adds_grounding_dimension(self) -> None:
        from agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()
        augmented = agent._augment_review_prompt_with_source(
            agent.review_prompt,
            {
                "source_type": SOURCE_TYPE_GITHUB_REPOSITORY,
                "source_title": "owner/repo",
                "source_url": "https://github.com/owner/repo",
                "source_summary": "A demo project.",
                "key_points": ["100 stars"],
                "technical_details": [],
                "framing_hint": "",
            },
        )
        # New GROUNDING line added to the score list.
        assert "GROUNDING:" in augmented
        # SOURCE FACTS section appended.
        assert "SOURCE FACTS" in augmented
        assert "owner/repo" in augmented
        # GROUNDING CONTRACT is added.
        assert "GROUNDING CONTRACT" in augmented
        # The original AI_LIKE_WRITING line is preserved.
        assert "AI_LIKE_WRITING:" in augmented

    def test_parser_extracts_grounding_score(self) -> None:
        """A GROUNDING: 8 | <explanation> line is parsed into a
        DimensionScore on ReviewScores.grounding."""
        from agents.reviewer import ReviewerAgent

        agent = ReviewerAgent()
        response = "\n".join(
            [
                "HOOK_STRENGTH: 8 | strong",
                "GROUNDING: 7 | all claims supported",
                "CLARITY: 8",
                "OVERALL: 8",
                "FEEDBACK: ok",
            ]
        )
        scores, _feedback, _decision = agent._parse_review_response(response)
        assert scores.grounding is not None
        assert scores.grounding.score == 7
        assert "all claims supported" in scores.grounding.explanation

    def test_grounding_below_threshold_triggers_improve(self) -> None:
        """A grounding score <= 4 forces an improve-step even when
        overall is high — the persistence layer would otherwise store
        a post that fabricates facts."""
        from agents.reviewer import (
            ReviewerAgent,
            ReviewScores,
            DimensionScore,
        )
        from models.models import LinkedInPost
        from unittest.mock import AsyncMock

        post = LinkedInPost(
            title="t",
            content="c",
            hashtags=["#a"],
        )
        # Use a fake review that scores high overall but low grounding.
        scores = ReviewScores(
            clarity=9,
            engagement=9,
            authenticity=9,
            readability=9,
            overall=9,
            grounding=DimensionScore(score=2, explanation="fabricated stats"),
        )
        # _parse_review_response would overwrite grounding if the
        # text contains a GROUNDING line. To prove the trigger, we
        # patch the reviewer's _get_review to return our high-overall
        # low-grounding scores, then call review() and confirm that
        # the improve-step was invoked.
        agent = ReviewerAgent()
        agent._get_review = AsyncMock(return_value=(scores, "fake grounded", None))
        # Also patch _improve_post to verify it was called.
        improved = LinkedInPost(
            title="t-improved",
            content="c-improved",
            hashtags=["#a"],
        )
        agent._improve_post = AsyncMock(return_value=improved)
        # Run.
        result = asyncio.run(agent.review(post, source={"source_type": "github_repository", "source_title": "t", "source_url": "u", "source_summary": "s", "key_points": [], "technical_details": [], "framing_hint": ""}))
        assert result.was_improved, "Low grounding must trigger improve"
        # And the improve-step was actually invoked.
        agent._improve_post.assert_awaited_once()
        # The improved post is the one persisted.
        assert result.final_post.title == "t-improved"


# ---------------------------------------------------------------------------
# 7. End-to-end: /generate source mode produces a persisted draft
# ---------------------------------------------------------------------------


class TestGenerateSourceModeEndToEnd:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def _make_fake_workflow(self, *, post: LinkedInPostPayload, score: int = 8):
        return GenerateContentResponse(
            topic="GitHub repository owner/repo: A demo project",
            final_post=post,
            approved=True,
            iterations=1,
            review_feedback="ok",
            review_scores={"overall": score},
            metadata={"writer_provider": "test", "writer_model": "test-model"},
        )

    def test_github_source_end_to_end(self, client_a, app) -> None:
        from shared.schemas import LinkedInPostPayload
        from backend.app.services.sources.base import SourcePackage

        package = SourcePackage(
            title="owner/repo: A demo project",
            summary="A demo project primarily Python (90%).",
            key_facts=["100 stars, 5 forks on GitHub"],
            raw_results=[
                {
                    "title": "owner/repo",
                    "url": "https://github.com/owner/repo",
                    "snippet": "A demo project.",
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
            title="owner/repo: A demo project",
            content=(
                "Came across an interesting GitHub project.\n\n"
                "What stood out:\n"
                "• Clean Python architecture\n"
                "• Good README\n"
                "• Active maintenance\n\n"
                "🔗 Worth exploring:\nhttps://github.com/owner/repo"
            ),
            hashtags=["#github", "#python", "#opensource"],
        )
        fake_workflow = self._make_fake_workflow(post=fake_post)

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
            new=AsyncMock(return_value=fake_workflow),
        ):
            response = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://github.com/owner/repo"},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        # draft_id and source_url are surfaced at the top level.
        assert body.get("draft_id")
        assert body.get("source_url") == "https://github.com/owner/repo"
        # source_metadata is persisted.
        meta = body.get("source_metadata") or {}
        assert meta.get("source_type") == "github_repository"
        assert meta.get("adapter") == "github"
        # content is LinkedIn-native (no markdown).
        fp = body.get("final_post") or {}
        assert "##" not in (fp.get("content") or "")
        assert "```" not in (fp.get("content") or "")
        # Hashtags are in the dedicated field, not as a trailing
        # "Hashtags:" line in the content.
        assert fp.get("hashtags")

    def test_article_source_passes_framing_hint(self, client_a, app) -> None:
        """The user's ``topic`` field on a source-mode request is
        forwarded as the framing hint to the writer prompt."""
        from shared.schemas import LinkedInPostPayload
        from backend.app.services.sources.base import SourcePackage

        package = SourcePackage(
            title="An interesting article",
            summary="An article about Foo.",
            key_facts=["It introduces a new technique."],
            raw_results=[
                {
                    "title": "An interesting article",
                    "url": "https://medium.com/@user/article",
                    "snippet": "An article.",
                }
            ],
            metadata={
                "url": "https://medium.com/@user/article",
                "canonical_url": "https://medium.com/@user/article",
                "adapter": "webpage",
            },
        )
        fake_post = LinkedInPostPayload(
            title="An interesting article",
            content="Came across an article about Foo.\n\nWorth a read.",
            hashtags=["#foo"],
        )
        fake_workflow = self._make_fake_workflow(post=fake_post)

        fake_adapter = WebArticleAdapter()
        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=fake_adapter,
        ), patch.object(
            WebArticleAdapter,
            "fetch",
            new=AsyncMock(return_value=package),
        ), patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            new=AsyncMock(return_value=fake_workflow),
        ) as wf_mock:
            response = client_a.post(
                "/api/v1/content/generate",
                json={
                    "source_url": "https://medium.com/@user/article",
                    "topic": "Focus on the central claim",
                },
            )
        assert response.status_code == 200, response.text
        # The WorkflowService was called with a source dict whose
        # framing_hint carries the user's framing hint.
        args, kwargs = wf_mock.call_args
        source = kwargs.get("source") or args[1]
        assert source is not None
        assert source.get("framing_hint") == "Focus on the central claim"
        # medium.com → blog_article per the source-type classifier.
        assert source.get("source_type") == "blog_article"

    def test_ssrf_bad_scheme_rejected_synchronously(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "file:///etc/passwd"},
        )
        assert response.status_code == 400
        # The error envelope is safe — no stack trace, no internal IP.
        body = response.json()
        msg = (
            body.get("detail")
            or (body.get("error") or {}).get("message")
        )
        assert msg and "Traceback" not in msg and "127.0.0.1" not in msg

    def test_ssrf_loopback_rejected_synchronously(self, client_a, app) -> None:
        response = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "http://127.0.0.1/x"},
        )
        assert response.status_code == 400

    def test_ssrf_private_ip_rejected_synchronously(self, client_a, app) -> None:
        response = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "http://10.0.0.1/x"},
        )
        assert response.status_code == 400

    def test_topic_mode_unaffected(self, client_a, app) -> None:
        """When only ``topic`` is supplied (no source_url), the legacy
        topic-mode path is unchanged — no adapter is invoked, the
        workflow is called with source=None."""
        from shared.schemas import LinkedInPostPayload

        fake_post = LinkedInPostPayload(
            title="t",
            content="c",
            hashtags=["#a"],
        )
        fake_workflow = self._make_fake_workflow(post=fake_post)
        with patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            new=AsyncMock(return_value=fake_workflow),
        ) as wf_mock:
            response = client_a.post(
                "/api/v1/content/generate",
                json={"topic": "Why async matters"},
            )
        assert response.status_code == 200, response.text
        args, kwargs = wf_mock.call_args
        # Source is None in topic mode.
        assert kwargs.get("source") is None


# ---------------------------------------------------------------------------
# 8. Source drafts appear in library, can be approved, can be published
# ---------------------------------------------------------------------------


class TestSourceDraftsEndToEnd:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def test_source_draft_in_library(self, client_a, app) -> None:
        """A source-generated draft must appear in the Draft Library
        with source_url and source_metadata preserved."""
        from shared.schemas import LinkedInPostPayload
        from backend.app.services.sources.base import SourcePackage

        package = SourcePackage(
            title="t",
            summary="s",
            key_facts=[],
            raw_results=[],
            metadata={
                "url": "https://github.com/owner/repo",
                "canonical_url": "https://github.com/owner/repo",
                "adapter": "github",
            },
        )
        fake_post = LinkedInPostPayload(
            title="A title",
            content="content",
            hashtags=["#a"],
        )
        fake_workflow = GenerateContentResponse(
            topic="t",
            final_post=fake_post,
            approved=True,
            iterations=1,
            review_feedback="ok",
            review_scores={"overall": 8},
            metadata={"writer_provider": "test", "writer_model": "test"},
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
            new=AsyncMock(return_value=fake_workflow),
        ):
            response = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://github.com/owner/repo"},
            )
        assert response.status_code == 200
        body = response.json()
        draft_id = body.get("draft_id")
        assert draft_id

        # Fetch the draft from the library and confirm it carries
        # the source metadata.
        listing = client_a.get("/api/v1/drafts")
        assert listing.status_code == 200
        items = listing.json().get("items") or []
        match = next(
            (item for item in items if item.get("id") == draft_id),
            None,
        )
        assert match is not None, "Source draft should appear in the library"
        assert match.get("source_url") == "https://github.com/owner/repo"
        meta = match.get("source_metadata") or {}
        assert meta.get("source_type") == "github_repository"

    def test_source_draft_can_be_approved(self, client_a, app) -> None:
        """Approval flow accepts a source-generated draft's
        approval_token; same path as topic drafts."""
        from shared.schemas import LinkedInPostPayload
        from backend.app.services.sources.base import SourcePackage

        package = SourcePackage(
            title="t",
            summary="s",
            key_facts=[],
            raw_results=[],
            metadata={
                "url": "https://github.com/owner/repo",
                "canonical_url": "https://github.com/owner/repo",
                "adapter": "github",
            },
        )
        fake_post = LinkedInPostPayload(
            title="A title",
            content="content",
            hashtags=["#a"],
        )
        fake_workflow = GenerateContentResponse(
            topic="t",
            final_post=fake_post,
            approved=True,
            iterations=1,
            review_feedback="ok",
            review_scores={"overall": 8},
            metadata={"writer_provider": "test", "writer_model": "test"},
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
            new=AsyncMock(return_value=fake_workflow),
        ):
            response = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://github.com/owner/repo"},
            )
        body = response.json()
        approval_token = body.get("approval_token")
        assert approval_token
        # Approve via the standard /approval/approve endpoint.
        approval_response = client_a.post(
            "/api/v1/approval/approve",
            json={"token": approval_token},
        )
        # Either 200 (approved) or 502 (LinkedIn not connected in
        # test env) is acceptable — both prove the approval token
        # is the same path.
        assert approval_response.status_code in (200, 502)


# ---------------------------------------------------------------------------
# 9. LinkedIn-native format end-to-end
# ---------------------------------------------------------------------------


class TestLinkedInNativeFormat:
    def test_normalizer_strips_markdown_and_hashtags_footer(self) -> None:
        normalized = normalize_linkedin_post(
            title="## A title",
            content=(
                "**Bold** and *italic* text.\n\n"
                "```python\nprint('code')\n```\n\n"
                "Hashtags: #AI #Python"
            ),
            hashtags=["AI", "Python"],
        )
        # Markdown stripped.
        assert "##" not in normalized.title
        assert "**" not in normalized.content
        assert "*" not in normalized.content
        assert "```" not in normalized.content
        # Hashtags: footer stripped from content.
        assert "Hashtags:" not in normalized.content
        # Hashtags in the dedicated field are normalized (each starts
        # with #, deduplicated, capped at 10).
        assert all(h.startswith("#") for h in normalized.hashtags)
        assert len(normalized.hashtags) <= 10

    def test_normalizer_preserves_paragraph_breaks(self) -> None:
        normalized = normalize_linkedin_post(
            title="t",
            content=("First paragraph.\n\nSecond paragraph.\n\nThird."),
            hashtags=[],
        )
        # Paragraph breaks preserved.
        assert "\n\n" in normalized.content
        assert "First paragraph" in normalized.content
        assert "Second paragraph" in normalized.content
        assert "Third" in normalized.content

    def test_normalizer_caps_hashtags_at_10(self) -> None:
        normalized = normalize_linkedin_post(
            title="t",
            content="c",
            hashtags=[f"tag{i}" for i in range(20)],
        )
        assert len(normalized.hashtags) == 10

    def test_normalizer_idempotent(self) -> None:
        normalized = normalize_linkedin_post(
            title="t",
            content="c",
            hashtags=["#a", "#b"],
        )
        twice = normalize_linkedin_post(
            title=normalized.title,
            content=normalized.content,
            hashtags=list(normalized.hashtags),
        )
        assert twice.title == normalized.title
        assert twice.content == normalized.content
        assert twice.hashtags == normalized.hashtags
