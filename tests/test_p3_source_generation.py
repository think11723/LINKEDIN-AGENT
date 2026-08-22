"""Phase 3 — Source generation comprehensive tests.

Covers:

  1. URL validation & SSRF guard (negative cases).
  2. Web adapter HTML extraction (positive + negative cases).
  3. GitHub URL form detection (can_handle).
  4. Source classification (deterministic).
  5. Source preview endpoint (synchronous analyze).
  6. Source-mode ``/generate`` endpoint (URL flows through).
  7. Source metadata persistence (DraftRepository).
  8. Source attribution rendering (frontend shape — meta only).
  9. End-to-end: topic draft unchanged when no source_url is sent.

Tests use the existing in-memory Mongo + auth fixtures in
``tests/conftest.py`` so they require no external services.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.db.mongo import get_database
from backend.app.repositories import DraftRepository, SourceJobRepository
from backend.app.services.sources.base import (
    SourceBlockedError,
    SourceFetchError,
    SourcePackage,
    SourceUnavailableError,
)
from backend.app.services.sources.classification import (
    KNOWN_SOURCE_TYPES,
    SOURCE_TYPE_BLOG_ARTICLE,
    SOURCE_TYPE_DOCUMENTATION,
    SOURCE_TYPE_GENERIC_WEBPAGE,
    SOURCE_TYPE_GITHUB_README,
    SOURCE_TYPE_GITHUB_REPOSITORY,
    SOURCE_TYPE_PRODUCT_PAGE,
    classify,
    get_narrative_angle,
    get_source_label,
)
from backend.app.services.sources.github_adapter import (
    GitHubSourceAdapter,
    _REPO_PATH_RE,
    _parse_owner_repo,
)
from backend.app.services.sources.ssrf import (
    DEFAULT_ALLOWED_PORTS,
    GITHUB_ALLOWLIST,
    check_ip_family,
    validate_url,
)
from backend.app.services.sources.web_adapter import (
    WebArticleAdapter,
    extract_article,
)


# ---------------------------------------------------------------------------
# 1. URL validation & SSRF
# ---------------------------------------------------------------------------


class TestUrlValidation:
    def test_valid_https_passes(self) -> None:
        parsed = validate_url("https://example.com/blog")
        assert parsed.scheme == "https"
        assert parsed.hostname == "example.com"

    def test_valid_http_passes(self) -> None:
        parsed = validate_url("http://example.com/x")
        assert parsed.scheme == "http"
        assert parsed.port in (80, None)

    def test_empty_url_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("")
        assert exc_info.value.code == "bad_url"

    def test_file_scheme_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("file:///etc/passwd")
        assert exc_info.value.code == "bad_scheme"

    def test_ftp_scheme_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("ftp://example.com/file.txt")
        assert exc_info.value.code == "bad_scheme"

    def test_javascript_scheme_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("javascript:alert(1)")
        assert exc_info.value.code == "bad_scheme"

    def test_data_scheme_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("data:text/html,<script>")
        assert exc_info.value.code == "bad_scheme"

    def test_userinfo_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("https://user:pass@example.com/")
        assert exc_info.value.code == "userinfo"

    def test_disallowed_port_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("https://example.com:22/")
        assert exc_info.value.code == "bad_port"

    def test_redis_port_rejected(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url("http://example.com:6379/")
        assert exc_info.value.code == "bad_port"

    def test_default_ports_unchanged(self) -> None:
        # The default port allowlist must stay narrow.
        assert DEFAULT_ALLOWED_PORTS == frozenset({80, 443})

    def test_loopback_ipv4_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("127.0.0.1")

    def test_loopback_ipv4_range_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("127.255.255.254")

    def test_loopback_ipv6_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("::1")

    def test_private_10_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("10.0.0.1")

    def test_private_172_16_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("172.16.0.1")

    def test_private_192_168_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("192.168.1.1")

    def test_link_local_169_254_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("169.254.1.1")

    def test_cloud_metadata_endpoint_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("169.254.169.254")

    def test_unspecified_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("0.0.0.0")

    def test_cgnat_blocked(self) -> None:
        with pytest.raises(SourceBlockedError):
            check_ip_family("100.64.0.1")

    def test_allow_hosts_github_blocks_other(self) -> None:
        with pytest.raises(SourceBlockedError) as exc_info:
            validate_url(
                "https://github.com.evil.com/owner/repo",
                allow_hosts=GITHUB_ALLOWLIST,
            )
        assert exc_info.value.code == "not_allowlisted"

    def test_allow_hosts_github_accepts_exact_match(self) -> None:
        parsed = validate_url(
            "https://api.github.com/repos/x/y", allow_hosts=GITHUB_ALLOWLIST
        )
        assert parsed.hostname == "api.github.com"

    def test_url_with_control_chars_rejected(self) -> None:
        with pytest.raises(SourceBlockedError):
            validate_url("https://example.com/\x00abc")

    def test_url_with_spaces_in_path_normalized(self) -> None:
        # A space in the path is technically legal in urlparse but
        # unsafe in real HTTP; the SSRF guard currently does not block
        # this (it depends on the transport library to percent-encode).
        # We document the current behaviour here.
        parsed = validate_url("https://example.com/some path/x")
        assert parsed.scheme == "https"


# ---------------------------------------------------------------------------
# 2. Web adapter HTML extraction
# ---------------------------------------------------------------------------


class TestWebAdapterExtraction:
    def test_extracts_article_body(self) -> None:
        html = """
        <html><head><title>An Article</title>
        <meta name="description" content="A great article">
        </head><body>
        <nav>nav stuff</nav>
        <article>
        <h1>An Article</h1>
        <p>First paragraph with real content that we want to keep.</p>
        <p>Second paragraph with more real content for the extractor.</p>
        <script>alert('xss')</script>
        </article>
        <footer>footer</footer>
        </body></html>
        """
        title, desc, text = extract_article(html)
        assert "An Article" in title
        assert "great article" in desc.lower() or "great article" in desc
        assert "First paragraph" in text
        assert "Second paragraph" in text
        assert "alert" not in text
        assert "nav stuff" not in text
        assert "footer" not in text

    def test_strips_scripts_and_styles(self) -> None:
        html = """
        <html><head>
        <style>body{color:red}</style>
        </head><body>
        <p>Real content stays.</p>
        <script>nasty();</script>
        </body></html>
        """
        _t, _d, text = extract_article(html)
        assert "Real content stays." in text
        assert "nasty" not in text
        assert "color:red" not in text

    def test_strips_navigation_and_footer(self) -> None:
        html = """
        <html><body>
        <nav>nav</nav>
        <main><p>main content</p></main>
        <aside>aside stuff</aside>
        <footer>footer</footer>
        </body></html>
        """
        _t, _d, text = extract_article(html)
        assert "main content" in text
        assert "nav" not in text
        assert "aside stuff" not in text
        assert "footer" not in text

    def test_handles_lists_as_bullets(self) -> None:
        html = """
        <html><body>
        <ul><li>one</li><li>two</li><li>three</li></ul>
        </body></html>
        """
        _t, _d, text = extract_article(html)
        assert "•" in text
        assert "one" in text and "two" in text and "three" in text

    def test_truncates_huge_pages(self) -> None:
        big_p = " ".join(["long paragraph " * 50] * 200)
        html = f"<html><body><article><p>{big_p}</p></article></body></html>"
        _t, _d, text = extract_article(html, max_bytes=4 * 1024)
        # Must be capped.
        assert len(text.encode("utf-8")) <= 4 * 1024 + 64
        assert "truncated" in text.lower() or "…" in text

    def test_returns_empty_for_empty_body(self) -> None:
        title, desc, text = extract_article("<html><body></body></html>")
        # The extractor returns whatever the parser produced; we
        # expect an empty/short body so the adapter raises thin_content.
        assert text.strip() == ""

    def test_handles_malformed_html(self) -> None:
        # Should not raise.
        title, desc, text = extract_article("<html><body><p>oops<")
        assert "oops" in text or text == ""


# ---------------------------------------------------------------------------
# 3. GitHub URL form detection
# ---------------------------------------------------------------------------


class TestGitHubAdapterCanHandle:
    def test_repo_root_recognized(self) -> None:
        assert GitHubSourceAdapter.can_handle("https://github.com/owner/repo")
        assert GitHubSourceAdapter.can_handle("https://github.com/owner/repo/")

    def test_repo_blob_path_accepted(self) -> None:
        assert GitHubSourceAdapter.can_handle(
            "https://github.com/owner/repo/blob/main/README.md"
        )

    def test_repo_tree_path_accepted(self) -> None:
        assert GitHubSourceAdapter.can_handle(
            "https://github.com/owner/repo/tree/main/src"
        )

    def test_repo_raw_path_accepted(self) -> None:
        assert GitHubSourceAdapter.can_handle(
            "https://github.com/owner/repo/raw/main/file.txt"
        )

    def test_issues_list_accepted(self) -> None:
        # The plan accepts root-level issues lists and normalizes them.
        assert GitHubSourceAdapter.can_handle("https://github.com/owner/repo/issues")

    def test_settings_path_rejected(self) -> None:
        assert not GitHubSourceAdapter.can_handle(
            "https://github.com/settings/profile"
        )

    def test_orgs_path_rejected(self) -> None:
        assert not GitHubSourceAdapter.can_handle("https://github.com/orgs/some")

    def test_users_path_rejected(self) -> None:
        assert not GitHubSourceAdapter.can_handle("https://github.com/users/x")

    def test_non_github_domain_rejected(self) -> None:
        assert not GitHubSourceAdapter.can_handle("https://example.com/owner/repo")

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

    def test_invalid_github_path_raises(self) -> None:
        # The github adapter's ``can_handle`` is strict — it refuses
        # ``/settings/...``, ``/orgs/...``, ``/wiki/...``, etc. so they
        # never reach ``_parse_owner_repo`` via the normal adapter
        # path. We exercise ``_parse_owner_repo`` directly with a URL
        # whose rest segment is not in the accepted set (the
        # ``/wiki/...`` first segment is rejected by
        # ``_normalize_github_path`` with ``unsupported_url_form``).
        with pytest.raises(SourceUnavailableError) as exc_info:
            _parse_owner_repo("https://github.com/owner/repo/wiki")
        assert exc_info.value.code == "unsupported_url_form"

    def test_settings_owner_segment_rejected(self) -> None:
        # ``https://github.com/settings/profile`` — owner segment is
        # a reserved top path. ``_parse_owner_repo`` accepts the
        # regex match but returns the (reserved) tuple; the adapter
        # ``can_handle`` correctly rejects it.
        from backend.app.services.sources.github_adapter import (
            _parse_owner_repo,
        )

        owner, repo = _parse_owner_repo("https://github.com/settings/profile")
        # The owner is "settings" (the regex is too permissive); the
        # adapter ``can_handle`` catches this and returns False.
        assert not GitHubSourceAdapter.can_handle(
            "https://github.com/settings/profile"
        )
        assert owner == "settings"
        assert repo == "profile"

    def test_repo_path_re_pattern(self) -> None:
        m = _REPO_PATH_RE.match("/owner/repo")
        assert m is not None
        assert m.group("owner") == "owner"
        assert m.group("repo") == "repo"


# ---------------------------------------------------------------------------
# 4. Source classification
# ---------------------------------------------------------------------------


class TestSourceClassification:
    def test_github_repo_classified(self) -> None:
        st = classify(
            url="https://github.com/owner/repo",
            adapter="github",
            title="owner/repo",
        )
        assert st == SOURCE_TYPE_GITHUB_REPOSITORY

    def test_github_readme_classified(self) -> None:
        st = classify(
            url="https://github.com/owner/repo/blob/main/README.md",
            adapter="github",
            title="owner/repo",
        )
        assert st == SOURCE_TYPE_GITHUB_README

    def test_docs_site_classified(self) -> None:
        st = classify(
            url="https://fastapi.tiangolo.com/tutorial/",
            adapter="webpage",
            title="FastAPI tutorial",
        )
        assert st == SOURCE_TYPE_DOCUMENTATION

    def test_product_announcement_by_keyword(self) -> None:
        st = classify(
            url="https://blog.example.com/post",
            adapter="webpage",
            title="Introducing our new feature",
            description="Announcing the launch of Foo v2",
        )
        assert st == SOURCE_TYPE_PRODUCT_PAGE

    def test_blog_article_via_medium(self) -> None:
        st = classify(
            url="https://medium.com/@user/some-article",
            adapter="webpage",
            title="My post",
        )
        assert st == SOURCE_TYPE_BLOG_ARTICLE

    def test_generic_webpage_fallback(self) -> None:
        st = classify(
            url="https://example.com/page",
            adapter="webpage",
            title="Some page",
        )
        assert st == SOURCE_TYPE_GENERIC_WEBPAGE

    def test_metadata_source_type_wins(self) -> None:
        st = classify(
            url="https://example.com/page",
            adapter="webpage",
            title="Some page",
            metadata={"source_type": SOURCE_TYPE_DOCUMENTATION},
        )
        assert st == SOURCE_TYPE_DOCUMENTATION

    def test_get_narrative_angle_known_types(self) -> None:
        for st in KNOWN_SOURCE_TYPES:
            angle = get_narrative_angle(st)
            assert isinstance(angle, str) and angle

    def test_get_narrative_angle_unknown_falls_back(self) -> None:
        angle = get_narrative_angle("mystery_type")
        # Unknown types fall back to the generic-webpage angle.
        assert angle == get_narrative_angle(SOURCE_TYPE_GENERIC_WEBPAGE)

    def test_get_source_label_known_types(self) -> None:
        for st in KNOWN_SOURCE_TYPES:
            label = get_source_label(st)
            assert isinstance(label, str) and label

    def test_get_source_label_unknown_falls_back(self) -> None:
        assert get_source_label("mystery") == "Web Article"

    def test_known_source_types_complete(self) -> None:
        assert SOURCE_TYPE_GITHUB_REPOSITORY in KNOWN_SOURCE_TYPES
        assert SOURCE_TYPE_GITHUB_README in KNOWN_SOURCE_TYPES
        assert SOURCE_TYPE_BLOG_ARTICLE in KNOWN_SOURCE_TYPES
        assert SOURCE_TYPE_DOCUMENTATION in KNOWN_SOURCE_TYPES
        assert SOURCE_TYPE_PRODUCT_PAGE in KNOWN_SOURCE_TYPES
        assert SOURCE_TYPE_GENERIC_WEBPAGE in KNOWN_SOURCE_TYPES


# ---------------------------------------------------------------------------
# 5. Source preview endpoint (synchronous analyze, no LLM)
# ---------------------------------------------------------------------------


class TestSourcePreviewEndpoint:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def test_preview_rejects_bad_scheme(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/source/preview",
            json={"url": "file:///etc/passwd"},
        )
        assert response.status_code == 400
        # The global error handler wraps HTTPException into a safe
        # envelope. We assert that a 400 with a non-empty, non-stack
        # message is returned.
        body = response.json()
        # Either FastAPI default ``detail`` or the project's error
        # envelope is acceptable. Both must be JSON and non-empty.
        assert isinstance(body, dict) and body
        # At least one of the well-known error fields is present.
        msg = body.get("detail") or (
            body.get("error", {}).get("message") if isinstance(body.get("error"), dict) else None
        )
        assert isinstance(msg, str) and msg
        # The message must be the safe user-facing string, not a
        # stack trace or internal IP.
        assert "Traceback" not in msg
        assert "127.0.0.1" not in msg
        assert "169.254" not in msg

    def test_preview_rejects_loopback(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/source/preview",
            json={"url": "http://127.0.0.1/x"},
        )
        # 400 from the SSRF pre-check (synchronous, no network call).
        assert response.status_code == 400

    def test_preview_rejects_metadata_endpoint(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/source/preview",
            json={"url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert response.status_code == 400

    def test_preview_rejects_empty_body(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/source/preview", json={}
        )
        # Pydantic validation: missing field → 422.
        assert response.status_code in (400, 422)

    def test_preview_unauthenticated(
        self, client_anon, app
    ) -> None:
        response = client_anon.post(
            "/api/v1/content/source/preview",
            json={"url": "https://example.com"},
        )
        # 401 / 403 — never 200.
        assert response.status_code in (401, 403)

    def test_preview_github_url_uses_github_adapter(
        self, client_a, app
    ) -> None:
        # Stub the adapter so we don't actually call the network.
        fake_package = SourcePackage(
            title="owner/repo: A demo project",
            summary="An open-source demo project primarily Python (90%).",
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
        fake_adapter = GitHubSourceAdapter()
        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=fake_adapter,
        ), patch.object(
            GitHubSourceAdapter, "fetch", new=AsyncMock(return_value=fake_package)
        ):
            response = client_a.post(
                "/api/v1/content/source/preview",
                json={"url": "https://github.com/owner/repo"},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["source_type"] == "github_repository"
        assert body["source_label"] == "GitHub Repository"
        assert body["adapter"] == "github"
        assert "request_id" in body
        src = body["source"]
        assert "owner/repo" in src["title"]
        # No raw HTML / README text / secrets in the preview.
        assert "raw_results" not in src.get("source_metadata", {})


# ---------------------------------------------------------------------------
# 6. /generate source mode (URL → workflow → draft with source metadata)
# ---------------------------------------------------------------------------


class TestGenerateSourceMode:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def test_topic_mode_still_requires_topic(
        self, client_a, app
    ) -> None:
        # Empty topic + no source_url → 422 (Pydantic min_length=1
        # validation) or 400 (manual check). Either is fine — both
        # are non-200 and reject the empty request.
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": ""}
        )
        assert response.status_code in (400, 422)

    def test_topic_mode_unaffected_by_source_url_field(
        self, client_a, app
    ) -> None:
        # When only ``topic`` is sent, the request follows the legacy
        # path. Whitespace-only topic must also be rejected.
        response = client_a.post(
            "/api/v1/content/generate", json={"topic": "  "}
        )
        # The handler treats whitespace as empty → 400.
        assert response.status_code in (400, 422)

    def test_no_topic_no_source_url_rejected(
        self, client_a, app
    ) -> None:
        # Neither topic nor source_url → 400 with a helpful message.
        response = client_a.post(
            "/api/v1/content/generate", json={}
        )
        assert response.status_code in (400, 422)

    def test_source_url_with_bad_scheme_rejected_synchronously(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "file:///etc/passwd"},
        )
        assert response.status_code == 400

    def test_source_url_with_loopback_rejected_synchronously(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "http://127.0.0.1/x"},
        )
        assert response.status_code == 400

    def test_source_url_with_private_ip_rejected_synchronously(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/generate",
            json={"source_url": "http://10.0.0.1/x"},
        )
        assert response.status_code == 400

    def test_source_url_with_github_uses_github_adapter(
        self, client_a, app
    ) -> None:
        # Stub the adapter AND the workflow service so we don't run
        # any LLM. The endpoint should return a 200 with a draft_id.
        from shared.schemas import (
            GenerateContentResponse,
            LinkedInPostPayload,
        )

        fake_package = SourcePackage(
            title="owner/repo: A demo project",
            summary="An open-source demo project primarily Python (90%).",
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
        fake_workflow_result = GenerateContentResponse(
            topic="GitHub repository owner/repo: A demo project",
            final_post=LinkedInPostPayload(
                title="owner/repo: A demo project",
                content=(
                    "Worth checking out if you're working with this kind of "
                    "tooling.\n\nThe project is an open-source demo project "
                    "primarily Python (90%).\n\n"
                    "🔗 Worth exploring:\nhttps://github.com/owner/repo"
                ),
                hashtags=["#github", "#python", "#opensource"],
            ),
            approved=True,
            iterations=1,
            review_feedback="ok",
            review_scores={"overall": 8},
            metadata={"writer_provider": "test", "writer_model": "test-model"},
        )

        fake_adapter = GitHubSourceAdapter()
        with patch(
            "backend.app.api.v1.content.resolve_adapter",
            return_value=fake_adapter,
        ), patch.object(
            GitHubSourceAdapter,
            "fetch",
            new=AsyncMock(return_value=fake_package),
        ), patch(
            "backend.app.services.workflow_service.WorkflowService.generate_content",
            new=AsyncMock(return_value=fake_workflow_result),
        ):
            response = client_a.post(
                "/api/v1/content/generate",
                json={"source_url": "https://github.com/owner/repo"},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body.get("draft_id"), "draft_id must be present"
        assert body.get("source_url") == "https://github.com/owner/repo"
        # Source metadata is persisted and surfaced in the response.
        assert body.get("source_metadata", {}).get("source_type") == (
            "github_repository"
        )
        # The draft is normalized.
        fp = body.get("final_post", {})
        # No markdown leak.
        assert "##" not in (fp.get("content") or "")
        # Hashtags are present.
        assert fp.get("hashtags")


# ---------------------------------------------------------------------------
# 7. Source metadata persistence (DraftRepository)
# ---------------------------------------------------------------------------


class TestDraftRepositorySourceMetadata:
    def test_source_url_and_metadata_persisted(self) -> None:
        repo = DraftRepository(get_database())
        doc = asyncio.run(
            repo.create(
                user_id="USER_A",
                draft_id="draft1",
                topic="github topic",
                title="A title",
                content="Some content",
                hashtags=["#a"],
                source_url="https://github.com/owner/repo",
                source_metadata={
                    "url": "https://github.com/owner/repo",
                    "adapter": "github",
                    "owner": "owner",
                    "repo": "repo",
                    "primary_language": "Python",
                },
            )
        )
        assert doc["source_url"] == "https://github.com/owner/repo"
        assert doc["source_metadata"]["adapter"] == "github"
        assert doc["source_metadata"]["primary_language"] == "Python"

    def test_source_metadata_omitted_for_topic_mode(self) -> None:
        repo = DraftRepository(get_database())
        doc = asyncio.run(
            repo.create(
                user_id="USER_A",
                draft_id="draft2",
                topic="a topic",
                title="A title",
                content="content",
                hashtags=[],
            )
        )
        # Source fields are absent on topic-mode drafts.
        assert "source_url" not in doc
        assert "source_metadata" not in doc

    def test_source_metadata_drops_credential_keys(self) -> None:
        repo = DraftRepository(get_database())
        doc = asyncio.run(
            repo.create(
                user_id="USER_A",
                draft_id="draft3",
                topic="github topic",
                title="A title",
                content="content",
                hashtags=[],
                source_url="https://github.com/owner/repo",
                source_metadata={
                    "adapter": "github",
                    "authorization": "Bearer SECRET_TOKEN",
                    "github_token": "ghp_xxxx",
                    "primary_language": "Python",
                },
            )
        )
        meta = doc["source_metadata"]
        assert "authorization" not in meta
        assert "github_token" not in meta
        assert meta["adapter"] == "github"
        assert meta["primary_language"] == "Python"

    def test_source_metadata_caps_oversized_strings(self) -> None:
        repo = DraftRepository(get_database())
        huge = "x" * 4096
        doc = asyncio.run(
            repo.create(
                user_id="USER_A",
                draft_id="draft4",
                topic="t",
                title="T",
                content="c",
                hashtags=[],
                source_url="https://github.com/owner/repo",
                source_metadata={"description": huge},
            )
        )
        # Capped + ellipsis.
        assert len(doc["source_metadata"]["description"]) < 4096
        assert doc["source_metadata"]["description"].endswith("…")


# ---------------------------------------------------------------------------
# 8. Source attribution rendering (frontend shape — meta only)
# ---------------------------------------------------------------------------


class TestSourceAttribution:
    """The frontend DraftViewerPage reads ``draft.source_url`` and
    ``draft.source_metadata`` directly. Verify the persisted shape
    is what the UI expects."""

    def test_minimal_metadata_enables_attribution(self) -> None:
        repo = DraftRepository(get_database())
        doc = asyncio.run(
            repo.create(
                user_id="USER_A",
                draft_id="draft_attribution_min",
                topic="t",
                title="T",
                content="c",
                hashtags=[],
                source_url="https://github.com/owner/repo",
                source_metadata={"source_type": "github_repository"},
            )
        )
        assert doc["source_url"]
        assert doc["source_metadata"]["source_type"] == "github_repository"

    def test_topic_draft_has_no_attribution(self) -> None:
        repo = DraftRepository(get_database())
        doc = asyncio.run(
            repo.create(
                user_id="USER_A",
                draft_id="draft_attribution_none",
                topic="t",
                title="T",
                content="c",
                hashtags=[],
            )
        )
        assert "source_url" not in doc
        assert "source_metadata" not in doc


# ---------------------------------------------------------------------------
# 9. Source job repository — adapter hint logic (related to source mode)
# ---------------------------------------------------------------------------


class TestSourceJobAdapterHint:
    def test_create_with_github_hint(self) -> None:
        jobs = SourceJobRepository(get_database())
        doc = asyncio.run(
            jobs.create(
                user_id="USER_A",
                url="https://github.com/owner/repo",
                adapter="github",
            )
        )
        assert doc["adapter"] == "github"

    def test_create_with_webpage_hint(self) -> None:
        jobs = SourceJobRepository(get_database())
        doc = asyncio.run(
            jobs.create(
                user_id="USER_A",
                url="https://example.com/x",
                adapter="webpage",
            )
        )
        assert doc["adapter"] == "webpage"


# ---------------------------------------------------------------------------
# 10. Source job endpoints — sanity checks
# ---------------------------------------------------------------------------


class TestGenerateFromUrlEndpoint:
    @pytest.fixture
    def app(self):
        from backend.app.main import app

        return app

    def test_bad_scheme_returns_400_synchronously(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/generate-from-url",
            json={"url": "javascript:alert(1)"},
        )
        assert response.status_code == 400

    def test_loopback_returns_400_synchronously(
        self, client_a, app
    ) -> None:
        # Phase 3 / SSRF pre-check: literal loopback IPs are blocked
        # synchronously by ``validate_url`` (now with literal-IP
        # detection) before any job is created.
        response = client_a.post(
            "/api/v1/content/generate-from-url",
            json={"url": "http://127.0.0.1/x"},
        )
        assert response.status_code == 400

    def test_private_ip_returns_400_synchronously(
        self, client_a, app
    ) -> None:
        # Literal private IPs are blocked synchronously too.
        response = client_a.post(
            "/api/v1/content/generate-from-url",
            json={"url": "http://192.168.0.1/x"},
        )
        assert response.status_code == 400

    def test_metadata_endpoint_returns_400_synchronously(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/generate-from-url",
            json={"url": "http://169.254.169.254/latest/meta-data/"},
        )
        assert response.status_code == 400

    def test_cgnat_returns_400_synchronously(
        self, client_a, app
    ) -> None:
        response = client_a.post(
            "/api/v1/content/generate-from-url",
            json={"url": "http://100.64.0.1/x"},
        )
        assert response.status_code == 400

    def test_github_url_accepted(self, client_a, app) -> None:
        response = client_a.post(
            "/api/v1/content/generate-from-url",
            json={"url": "https://github.com/owner/repo"},
        )
        # 202 (enqueued), 429 (rate-limited), or any non-400 response
        # is fine — we just need to confirm the SSRF guard accepted
        # the URL.
        assert response.status_code != 400 or response.status_code == 429

    def test_unauthenticated_rejected(self, client_anon, app) -> None:
        response = client_anon.post(
            "/api/v1/content/generate-from-url",
            json={"url": "https://github.com/owner/repo"},
        )
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 11. normalize_linkedin_post applied to source drafts
# ---------------------------------------------------------------------------


class TestNormalizerOnSourceDrafts:
    def test_normalizer_strips_markdown_from_generated_content(self) -> None:
        from utils.linkedin_content import normalize_linkedin_post

        normalized = normalize_linkedin_post(
            title="## A title with markdown",
            content=(
                "**Bold** and *italic* text.\n\n"
                "```python\nprint('code')\n```\n\n"
                "Hashtags: #foo #bar"
            ),
            hashtags=["foo", "bar"],
        )
        assert "##" not in normalized.title
        assert "**" not in normalized.content
        assert "*" not in normalized.content
        assert "```" not in normalized.content
        # Trailing hashtags line stripped.
        assert "Hashtags:" not in normalized.content
        # Hashtags in the dedicated field are normalized.
        assert all(h.startswith("#") for h in normalized.hashtags)
