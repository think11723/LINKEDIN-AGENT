"""Phase 8E — Multi-provider search fallback tests.

The tests cover all 12 scenarios in the user-facing requirements:

  A. SearXNG success
  B. SearXNG 429 → next instance
  C. SearXNG instance failure → next instance
  D. Wikipedia success
  E. HN Algolia success
  F. Primary SearXNG failure → Wikipedia fallback
  G. SearXNG + Wikipedia failure → HN fallback
  H. All providers fail → SearchUnavailableError / graceful result
  I. Result normalization
  J. URL deduplication
  K. SSRF / allowlist rejection
  L. Timeout handling

All network calls are mocked via ``monkeypatch`` of
``services.search._ssrf.safe_http_json`` so the tests do not depend
on real public SearXNG / Wikipedia / HN endpoints.
"""

from __future__ import annotations

import asyncio
import importlib
from typing import Any, Dict, List, Optional, Tuple

import pytest

# Lazy imports inside each test so the tests don't trigger the
# package-level conftest's mock_mongo fixture (which is irrelevant
# here and slows startup).


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class _FakeSafeHttp:
    """Replace ``services.search._ssrf.safe_http_json`` with a stub.

    Each call appends a record to ``self.calls`` (so tests can assert
    the URL and host allowlist that were used) and returns the
    pre-programmed response or raises the pre-programmed exception.
    """

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []
        # List of (url_match, response_or_exception) tuples. The
        # first entry whose url matches the requested URL is used.
        self._scripted: List[Tuple[str, Any]] = []

    def script(self, url_contains: str, response_or_exc: Any) -> None:
        """Queue a response / exception for the next call whose URL
        contains ``url_contains``."""
        self._scripted.append((url_contains, response_or_exc))

    def return_for(
        self,
        url: str,
        *,
        allow_hosts: List[str],
        timeout_seconds: float = 0.0,
        max_bytes: Any = None,
    ):
        """Return the queued response for this URL. Records the call."""
        self.calls.append({"url": url, "allow_hosts": list(allow_hosts)})
        for substr, value in self._scripted:
            if substr in url:
                # Pop the first match so a subsequent call sees
                # the next scripted response (or no response).
                idx = self._scripted.index((substr, value))
                self._scripted.pop(idx)
                if isinstance(value, BaseException):
                    raise value
                return value
        # No script. Default: empty 200.
        return 200, {}, {}


def _install_safe_http(monkeypatch, fake: _FakeSafeHttp) -> None:
    """Patch the safe_http_json symbol in every module that imported
    it. We patch the module-level symbol in each provider module
    AND in the ``_ssrf`` helper so any of them calling it sees
    the stub. A single patch at the ``_ssrf`` module is enough for
    most cases, but the providers import it directly so we patch
    both.

    ``fake.return_for`` is an instance method, so we wrap it in a
    closure that binds ``self=fake`` to avoid the "object tuple
    can't be used in 'await' expression" error.
    """
    import services.search._ssrf as ssrf_mod
    import services.search.searxng as searxng_mod
    import services.search.wikipedia as wiki_mod
    import services.search.hn_algolia as hn_mod

    async def stub(url, *, allow_hosts, timeout_seconds, max_bytes=...):
        return fake.return_for(
            url, allow_hosts=allow_hosts, timeout_seconds=timeout_seconds
        )

    for mod in (ssrf_mod, searxng_mod, wiki_mod, hn_mod):
        monkeypatch.setattr(mod, "safe_http_json", stub)


# A minimal SearXNG JSON payload.
SEARXNG_OK = {
    "results": [
        {
            "title": "First Result",
            "url": "https://example.com/first",
            "content": "Snippet one.",
        },
        {
            "title": "Second Result",
            "url": "https://example.com/second",
            "content": "Snippet two.",
        },
    ]
}

# A minimal Wikipedia OpenSearch payload.
WIKIPEDIA_OK = {
    "query": {
        "search": [
            {
                "title": "Foo",
                "snippet": "Foo is a <span>highlighted</span> topic.",
                "pageid": 12345,
            },
            {
                "title": "Bar",
                "snippet": "Bar is a related <span>concept</span>.",
                "pageid": 12346,
            },
        ]
    }
}

# A minimal HN Algolia payload.
HN_OK = {
    "hits": [
        {
            "objectID": "1",
            "title": "Show HN: First",
            "url": "https://example.com/hn-1",
            "_highlightResult": {
                "title": {"value": "Show HN: <em>First</em>"},
            },
        },
        {
            "objectID": "2",
            "story_title": "Second story",
            "story_url": "https://example.com/hn-2",
            "_highlightResult": {
                "story_text": {"value": "<em>Second</em> story text."},
            },
        },
    ]
}


# ---------------------------------------------------------------------------
# Scenario A: SearXNG success
# ---------------------------------------------------------------------------


def test_scenario_a_searxng_success(monkeypatch) -> None:
    """A single-instance SearXNG pool returns 200 with results;
    the orchestrator returns those results from the searxng
    provider.
    """
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search.errors import SearchUnavailableError

    fake = _FakeSafeHttp()
    fake.script("searx.example", (200, SEARXNG_OK, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("hello", request_id="r1", max_results=5)
    )
    assert outcome.provider == "searxng"
    assert len(outcome.results) == 2
    assert outcome.results[0]["title"] == "First Result"
    assert outcome.results[0]["url"] == "https://example.com/first"
    # The other providers were not consulted.
    assert all(a["provider"] == "searxng" for a in outcome.attempts)


# ---------------------------------------------------------------------------
# Scenario B: SearXNG 429 → next instance
# ---------------------------------------------------------------------------


def test_scenario_b_searxng_429_rotates_to_next_instance(monkeypatch) -> None:
    """The first instance returns 429 (rate-limited). The provider
    rotates to the second instance which returns 200. The
    orchestrator returns the results from the second instance.
    """
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError

    fake = _FakeSafeHttp()
    # First instance: 429.
    fake.script(
        "searx1.example",
        _SearchHttpError("http 429", status_code=429),
    )
    # Second instance: 200.
    fake.script("searx2.example", (200, SEARXNG_OK, {}))

    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(
            instances=["https://searx1.example", "https://searx2.example"],
        ),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("q", request_id="r2", max_results=5)
    )
    assert outcome.provider == "searxng"
    assert len(outcome.results) == 2
    # The two URLs in the call list should be the two instances.
    urls_called = [c["url"] for c in fake.calls]
    assert any("searx1.example" in u for u in urls_called)
    assert any("searx2.example" in u for u in urls_called)


# ---------------------------------------------------------------------------
# Scenario C: SearXNG instance failure → next instance
# ---------------------------------------------------------------------------


def test_scenario_c_searxng_instance_transport_failure(monkeypatch) -> None:
    """The first instance times out / 5xx / network error. The
    provider rotates to the second instance which returns 200.
    """
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError

    fake = _FakeSafeHttp()
    fake.script(
        "searx1.example",
        _SearchHttpError("unavailable: timeout", status_code=0),
    )
    fake.script("searx2.example", (200, SEARXNG_OK, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(
            instances=["https://searx1.example", "https://searx2.example"],
        ),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("q", request_id="r3", max_results=5)
    )
    assert outcome.provider == "searxng"
    assert len(outcome.results) == 2


# ---------------------------------------------------------------------------
# Scenario D: Wikipedia success
# ---------------------------------------------------------------------------


def test_scenario_d_wikipedia_success(monkeypatch) -> None:
    """SearXNG has no instances (or all instances fail). Wikipedia
    returns 200 with results. The orchestrator returns the
    Wikipedia results.
    """
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )

    fake = _FakeSafeHttp()
    fake.script("wikipedia.org", (200, WIKIPEDIA_OK, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=[]),  # no SearXNG configured
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("foo", request_id="r4", max_results=5)
    )
    assert outcome.provider == "wikipedia"
    assert len(outcome.results) == 2
    # Wikipedia page URLs are constructed from the title.
    assert outcome.results[0]["url"] == "https://en.wikipedia.org/wiki/Foo"
    assert outcome.results[0]["title"] == "Foo"
    # The HTML <span> tags have been stripped from the snippet.
    assert "<span>" not in outcome.results[0]["snippet"]
    assert "highlighted" in outcome.results[0]["snippet"]


# ---------------------------------------------------------------------------
# Scenario E: HN Algolia success
# ---------------------------------------------------------------------------


def test_scenario_e_hn_algolia_success(monkeypatch) -> None:
    """SearXNG and Wikipedia are unavailable. HN Algolia returns
    200 with results. The orchestrator returns the HN results.
    """
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError

    fake = _FakeSafeHttp()
    # SearXNG: no instances.
    # Wikipedia: transport error.
    fake.script(
        "wikipedia.org",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    # HN: success.
    fake.script("hn.algolia.com", (200, HN_OK, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=[]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("hn-q", request_id="r5", max_results=5)
    )
    assert outcome.provider == "hn_algolia"
    assert len(outcome.results) == 2
    # The first hit used ``title`` directly.
    assert outcome.results[0]["title"] == "Show HN: First"
    # The second hit fell back to ``story_title`` and ``story_url``.
    assert outcome.results[1]["title"] == "Second story"
    assert outcome.results[1]["url"] == "https://example.com/hn-2"


# ---------------------------------------------------------------------------
# Scenario F: Primary SearXNG failure → Wikipedia fallback
# ---------------------------------------------------------------------------


def test_scenario_f_searxng_failure_falls_back_to_wikipedia(monkeypatch) -> None:
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError

    fake = _FakeSafeHttp()
    fake.script(
        "searx.example",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script("wikipedia.org", (200, WIKIPEDIA_OK, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("q", request_id="r6", max_results=5)
    )
    assert outcome.provider == "wikipedia"
    assert len(outcome.results) == 2
    # The attempt log records both providers.
    providers_tried = [a["provider"] for a in outcome.attempts]
    assert providers_tried == ["searxng", "wikipedia"]
    # SearXNG's attempt was recorded as a failure.
    assert outcome.attempts[0]["success"] is False
    assert outcome.attempts[0]["error_type"] == "_SearchHttpError"
    # Wikipedia's attempt succeeded.
    assert outcome.attempts[1]["success"] is True
    assert outcome.attempts[1]["result_count"] == 2


# ---------------------------------------------------------------------------
# Scenario G: SearXNG + Wikipedia failure → HN fallback
# ---------------------------------------------------------------------------


def test_scenario_g_searxng_and_wikipedia_failure_falls_back_to_hn(
    monkeypatch,
) -> None:
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError

    fake = _FakeSafeHttp()
    fake.script(
        "searx.example",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script(
        "wikipedia.org",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script("hn.algolia.com", (200, HN_OK, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("q", request_id="r7", max_results=5)
    )
    assert outcome.provider == "hn_algolia"
    assert len(outcome.results) == 2
    providers_tried = [a["provider"] for a in outcome.attempts]
    assert providers_tried == ["searxng", "wikipedia", "hn_algolia"]


# ---------------------------------------------------------------------------
# Scenario H: All providers fail → SearchUnavailableError
# ---------------------------------------------------------------------------


def test_scenario_h_all_providers_fail_raises_unavailable(monkeypatch) -> None:
    """Every provider fails. The orchestrator raises
    SearchUnavailableError with the structured attempt list."""
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError
    from services.search.errors import SearchUnavailableError

    fake = _FakeSafeHttp()
    fake.script(
        "searx.example",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script(
        "wikipedia.org",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script(
        "hn.algolia.com",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    with pytest.raises(SearchUnavailableError) as excinfo:
        asyncio.run(service.search("q", request_id="r8", max_results=5))
    exc = excinfo.value
    assert exc.error_code == "search_unavailable"
    assert len(exc.attempts) == 3
    providers_tried = [a.provider for a in exc.attempts]
    assert providers_tried == ["searxng", "wikipedia", "hn_algolia"]
    for attempt in exc.attempts:
        assert attempt.fallback_eligible is True
    d = exc.to_dict()
    assert d["error_code"] == "search_unavailable"
    assert len(d["attempted_providers"]) == 3


# ---------------------------------------------------------------------------
# Scenario I: Result normalization
# ---------------------------------------------------------------------------


def test_scenario_i_result_normalization(monkeypatch) -> None:
    """Wikipedia response with HTML in the snippet is normalized:
    <span> tags stripped, whitespace collapsed, alphanumeric
    characters preserved. Empty fields cause the result to be
    dropped (not fabricated)."""
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )

    fake = _FakeSafeHttp()
    fake.script("wikipedia.org", (200, {
        "query": {
            "search": [
                {
                    "title": "Good Title",
                    "snippet": "Snippet with <span>tag</span> and  spaces.",
                    "pageid": 1,
                },
                {
                    "title": "",  # empty → dropped
                    "snippet": "snippet",
                    "pageid": 2,
                },
                {
                    "title": "Title with no snippet",
                    "snippet": "",  # empty → dropped
                    "pageid": 3,
                },
                {
                    "title": "Not a URL",
                    "snippet": "snippet",
                    "pageid": 4,
                },  # Wikipedia gives it a URL; not dropped here
            ]
        }
    }, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=[]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("q", request_id="r9", max_results=10)
    )
    # The "Good Title" result is normalized and included.
    assert len(outcome.results) >= 1
    good = next(r for r in outcome.results if r["title"] == "Good Title")
    assert "<span>" not in good["snippet"]
    assert "  " not in good["snippet"]
    assert good["snippet"] == "Snippet with tag and spaces."
    # The empty-title and empty-snippet entries were dropped.
    assert all(r["title"] for r in outcome.results)
    assert all(r["snippet"] for r in outcome.results)


# ---------------------------------------------------------------------------
# Scenario J: URL deduplication
# ---------------------------------------------------------------------------


def test_scenario_j_url_deduplication(monkeypatch) -> None:
    """If a SearXNG response contains the same URL twice, the
    orchestrator returns it only once.
    """
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )

    fake = _FakeSafeHttp()
    fake.script("searx.example", (200, {
        "results": [
            {
                "title": "First copy",
                "url": "https://example.com/dup",
                "content": "First snippet.",
            },
            {
                "title": "Second copy",
                "url": "https://example.com/dup",
                "content": "Second snippet.",
            },
            {
                "title": "Different",
                "url": "https://example.com/other",
                "content": "Other snippet.",
            },
        ]
    }, {}))
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("q", request_id="r10", max_results=10)
    )
    urls = [r["url"] for r in outcome.results]
    # The duplicate URL appears only once.
    assert urls.count("https://example.com/dup") == 1
    assert len(outcome.results) == 2


# ---------------------------------------------------------------------------
# Scenario K: SSRF / allowlist rejection
# ---------------------------------------------------------------------------


def test_scenario_k_allowlist_rejects_off_allowlist_host(monkeypatch) -> None:
    """If a provider's outbound request is rejected by the SSRF
    guard (host not in allowlist), the provider's failure
    surfaces as a structured error and the orchestrator advances
    to the next provider.

    This test uses a custom :class:`SearchProvider` whose ``search``
    method always raises ``_SearchHttpError`` (simulating an SSRF
    rejection by the production guard), so we can verify the
    orchestrator's "advance on SSRF rejection" behaviour without
    depending on the per-provider allowlist wiring.
    """
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearchProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError

    class _SSRFBlockedProvider(SearchProvider):
        """A provider that always raises an SSRF-style rejection."""

        name = "ssrf_blocked"

        async def search(self, query, *, request_id, max_results=5):
            raise _SearchHttpError(
                "blocked: host not in allowlist",
                status_code=0,
            )

    class _StubWikipediaProvider(SearchProvider):
        """A Wikipedia provider that returns one canned result."""

        name = "wikipedia"

        async def search(self, query, *, request_id, max_results=5):
            return [
                {
                    "title": "Wiki result",
                    "url": "https://en.wikipedia.org/wiki/Test",
                    "snippet": "Wiki snippet.",
                }
            ]

    service = SearchService(providers=[
        _SSRFBlockedProvider(),
        _StubWikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    outcome = asyncio.run(
        service.search("q", request_id="r11", max_results=5)
    )
    # The orchestrator advanced past the SSRF-blocked provider
    # and ended on Wikipedia.
    assert outcome.provider == "wikipedia"
    assert len(outcome.results) == 1
    assert outcome.results[0]["title"] == "Wiki result"
    # The SSRF-blocked provider's attempt is recorded as a
    # failure with the original error message preserved.
    ssrf_attempt = next(
        a for a in outcome.attempts if a["provider"] == "ssrf_blocked"
    )
    assert ssrf_attempt["success"] is False
    assert "blocked" in ssrf_attempt["error_message"]


# ---------------------------------------------------------------------------
# Scenario L: Timeout handling
# ---------------------------------------------------------------------------


def test_scenario_l_timeout_handling(monkeypatch) -> None:
    """If every provider times out, the orchestrator raises
    SearchUnavailableError. The total time is bounded by
    (num_providers × per_provider_timeout)."""
    import time
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search._ssrf import _SearchHttpError
    from services.search.errors import SearchUnavailableError

    # Each call sleeps just long enough to demonstrate that the
    # total time scales linearly with provider count, not
    # exponentially. We keep the sleeps tiny (10 ms) so the test
    # runs in well under a second.
    def slow_safe_http(url, *, allow_hosts, timeout_seconds, max_bytes=...):
        time.sleep(0.01)
        raise _SearchHttpError(
            f"unavailable: timeout after {timeout_seconds}s",
            status_code=0,
        )

    fake = _FakeSafeHttp()
    fake.return_for = slow_safe_http  # type: ignore[assignment]
    _install_safe_http(monkeypatch, fake)

    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    start = time.monotonic()
    with pytest.raises(SearchUnavailableError):
        asyncio.run(service.search("q", request_id="r12", max_results=5))
    elapsed = time.monotonic() - start
    # Each provider sleeps ~10 ms; 3 providers → ~30 ms. Allow
    # generous slack for process startup and pytest overhead.
    assert elapsed < 2.0, (
        f"orchestrator took {elapsed:.3f}s; expected < 2s for 3 providers"
    )


# ---------------------------------------------------------------------------
# Regression: search_web() compat wrapper still returns [] on failure
# ---------------------------------------------------------------------------


def test_search_web_compat_returns_empty_list_on_failure(
    monkeypatch,
) -> None:
    """The legacy ``search_web`` function preserves its "return []
    on any failure" contract so existing callers do not have to
    change."""
    import services.search as legacy_mod
    from services.search._ssrf import _SearchHttpError

    fake = _FakeSafeHttp()
    fake.script(
        "searx.example",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script(
        "wikipedia.org",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script(
        "hn.algolia.com",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    _install_safe_http(monkeypatch, fake)
    # Force a fresh service build (the previous test's build had
    # SearXNG instances from the test, but ``search_web`` reads
    # env at construction; we explicitly construct a service with
    # a single failing instance to make the test deterministic).
    from services.search import (
        HNAlgoliaProvider,
        SearchService,
        SearXNGProvider,
        WikipediaProvider,
    )
    legacy_mod.reset_search_service()
    # Override the lazy default with one that uses our fake-stubbed
    # providers. Easiest: patch get_search_service.
    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    monkeypatch.setattr(legacy_mod, "get_search_service", lambda: service)

    result = legacy_mod.search_web("q", max_results=5)
    assert result == []


# ---------------------------------------------------------------------------
# Regression: ResearchService marks summary=None when chain unavailable
# ---------------------------------------------------------------------------


def test_research_service_marks_summary_none_on_chain_failure(
    monkeypatch,
) -> None:
    """When every search provider fails, ResearchService.research
    must set ``summary=None`` and ``raw_results=[]`` so the
    workflow layer can distinguish a search failure from a
    successful zero-result search.
    """
    from services.research.service import ResearchService
    from services.search._ssrf import _SearchHttpError

    fake = _FakeSafeHttp()
    fake.script(
        "searx.example",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script(
        "wikipedia.org",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    fake.script(
        "hn.algolia.com",
        _SearchHttpError("unavailable: 5xx", status_code=0),
    )
    _install_safe_http(monkeypatch, fake)

    # Patch the lazy default service to one with the same three
    # providers (so the chain fails the same way).
    from services.search import (
        HNAlgoliaProvider,
        SearXNGProvider,
        WikipediaProvider,
    )
    from services.search.service import SearchService
    import services.search as legacy_mod
    legacy_mod.reset_search_service()
    service = SearchService(providers=[
        SearXNGProvider(instances=["https://searx.example"]),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])
    monkeypatch.setattr(legacy_mod, "get_search_service", lambda: service)

    rs = ResearchService()
    pkg = rs.research("some topic")
    assert pkg.raw_results == []
    assert pkg.summary is None
    assert pkg.sources == []


# ---------------------------------------------------------------------------
# SearXNG instance-pool parsing
# ---------------------------------------------------------------------------


def test_searxng_instance_pool_parsing() -> None:
    """``_parse_instance_pool`` must dedupe by host, drop malformed
    entries, and preserve the input order."""
    from services.search.searxng import _parse_instance_pool

    raw = (
        "https://a.example, https://b.example/ ,"
        "https://c.example,not-a-url,https://a.example,ftp://x.example"
    )
    parsed = _parse_instance_pool(raw)
    assert parsed == [
        "https://a.example",
        "https://b.example",
        "https://c.example",
    ]


def test_searxng_no_instances_raises_unavailable(monkeypatch) -> None:
    """A SearXNGProvider with no configured instances must raise
    SearchUnavailableError instead of fabricating results."""
    from services.search import SearXNGProvider
    from services.search.errors import SearchUnavailableError

    provider = SearXNGProvider(instances=[])
    with pytest.raises(SearchUnavailableError):
        asyncio.run(provider.search("q", request_id="r", max_results=5))
