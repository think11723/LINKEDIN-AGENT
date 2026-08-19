"""Wikipedia search provider.

Uses the public Wikipedia REST API
(``https://en.wikipedia.org/w/api.php?action=query&list=search&format=json``).
This is a free, no-key endpoint that powers Wikipedia's own search
box. Wikipedia is encyclopedic and stable; it is an excellent
fallback when general web search (SearXNG) is rate-limited.

Response shape::

    {
      "query": {
        "search": [
          {
            "title": "Foo",
            "snippet": "Foo is a <span>...</span> ...",
            "pageid": 12345
          },
          ...
        ]
      }
    }

We strip the HTML spans from the snippet and build the canonical
URL ``https://en.wikipedia.org/wiki/{title_underscored}``.

The provider is configured with a hard-coded base URL
(``https://en.wikipedia.org``) and the host allowlist passed to
:func:`safe_http_json` is exactly that single host. Any other
target would be SSRF-rejected.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import quote

from services.search._ssrf import _SearchHttpError, safe_http_json
from services.search.base import (
    SearchProvider,
    dedupe_by_url,
    normalize_result,
)
from services.search.errors import (
    SearchAttempt,
    SearchUnavailableError,
)

logger = logging.getLogger(__name__)


#: Wikipedia API base URL. Hard-coded because the Wikipedia API has
#: a stable canonical host. Override via the WIKIPEDIA_API_URL env
#: var if you operate a Wikipedia mirror.
WIKIPEDIA_API_URL: str = "https://en.wikipedia.org"

#: Wikipedia page URL prefix. Wikipedia page URLs are
#: ``https://en.wikipedia.org/wiki/{title}`` where ``title`` is the
#: page title with spaces replaced by underscores.
WIKIPEDIA_PAGE_PREFIX: str = WIKIPEDIA_API_URL + "/wiki/"

#: Default timeout. Wikipedia is fast; 6 s is comfortable.
DEFAULT_TIMEOUT_SECONDS: float = 6.0


class WikipediaProvider(SearchProvider):
    """Wikipedia OpenSearch provider. No API key required."""

    name = "wikipedia"

    def __init__(
        self,
        api_url: str = WIKIPEDIA_API_URL,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        # Normalize: scheme + host only, no trailing slash.
        from urllib.parse import urlparse
        parsed = urlparse(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                f"WikipediaProvider: invalid api_url {api_url!r}"
            )
        self._api_base = f"{parsed.scheme}://{parsed.netloc}"
        self._timeout_seconds = float(timeout_seconds)

    @property
    def api_base(self) -> str:
        return self._api_base

    async def search(
        self,
        query: str,
        *,
        request_id: str,
        max_results: int = 5,
    ) -> List[Dict[str, str]]:
        from urllib.parse import urlparse
        host = urlparse(self._api_base).netloc.lower()
        allow_hosts = [host]

        url = (
            f"{self._api_base}/w/api.php"
            f"?action=query"
            f"&list=search"
            f"&format=json"
            f"&srsearch={quote(query or '')}"
            f"&srlimit={int(max_results)}"
            f"&srprop=snippet"
            f"&utf8=1"
            f"&formatversion=2"
        )
        try:
            status_code, payload, _headers = await safe_http_json(
                url,
                allow_hosts=allow_hosts,
                timeout_seconds=self._timeout_seconds,
            )
        except _SearchHttpError as exc:
            logger.info(
                "Wikipedia: HTTP failure (%s); raising unavailable",
                exc,
            )
            raise _raise_wiki_unavailable(self.name, exc, query)

        results = _parse_wikipedia_response(payload, max_results)
        if not results:
            logger.info(
                "Wikipedia: no results for %r",
                (query or "")[:80],
            )
        else:
            logger.info("Wikipedia: %d result(s)", len(results))
        return dedupe_by_url(results)


def _parse_wikipedia_response(
    payload: Dict[str, Any],
    max_results: int,
) -> List[Dict[str, str]]:
    """Turn a Wikipedia OpenSearch response into normalized results."""
    query = payload.get("query") if isinstance(payload, dict) else None
    if not isinstance(query, dict):
        return []
    raw = query.get("search")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title") or "")
        if not title:
            continue
        # Wikipedia page URLs use the title with spaces replaced by
        # underscores. Title is already URL-safe aside from spaces.
        url = WIKIPEDIA_PAGE_PREFIX + title.replace(" ", "_")
        snippet = str(entry.get("snippet") or "")
        normalized = normalize_result(title=title, url=url, snippet=snippet)
        if normalized is not None:
            out.append(normalized)
        if len(out) >= max_results:
            break
    return out


def _raise_wiki_unavailable(
    provider: str,
    last_error: Exception,
    query: str,
) -> SearchUnavailableError:
    return SearchUnavailableError([
        SearchAttempt(
            provider=provider,
            query=query,
            error_type=type(last_error).__name__,
            error_message=str(last_error) or "transport failure",
            fallback_eligible=True,
        ),
    ])


__all__ = [
    "WikipediaProvider",
    "WIKIPEDIA_API_URL",
    "DEFAULT_TIMEOUT_SECONDS",
]
