"""Hacker News Algolia search provider.

Uses the public HN Algolia search API
(``https://hn.algolia.com/api/v1/search``). This is a free, no-key
endpoint run by Algolia. It is best for technology, startup, and
industry-trend topics — the application's primary use case.

Response shape::

    {
      "hits": [
        {
          "objectID": "12345",
          "title": "Show HN: ...",
          "story_title": "Show HN: ...",   # used when title is null
          "url": "https://example.com/article",
          "story_url": "https://example.com/article",
          "author": "username",
          "points": 142,
          "created_at": "2025-08-12T10:00:00.000Z",
          "_highlightResult": {
            "comment_text": {"value": "..."},
            "story_text": {"value": "..."},
            "title": {"value": "..."}
          }
        },
        ...
      ]
    }

We use ``title`` (falling back to ``story_title``), the URL
(falling back to ``story_url`` or the canonical HN item URL
``https://news.ycombinator.com/item?id={objectID}``), and a snippet
from the highlighted title/comment/story text.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import quote, urlparse

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


#: HN Algolia API base. Hard-coded; stable canonical host.
HN_ALGOLIA_API_URL: str = "https://hn.algolia.com"

#: HN item URL prefix (canonical fallback when a hit has no URL).
HN_ITEM_PREFIX: str = "https://news.ycombinator.com/item?id="

#: Default timeout.
DEFAULT_TIMEOUT_SECONDS: float = 6.0


def _highlight_text(highlight: Dict[str, Any], *keys: str) -> str:
    """Extract the first available highlighted snippet.

    The HN API returns a dict per field like ``{"value": "<em>...</em>"}``.
    Returns an empty string if none of the keys are present.
    """
    if not isinstance(highlight, dict):
        return ""
    for key in keys:
        node = highlight.get(key)
        if isinstance(node, dict):
            value = node.get("value")
            if isinstance(value, str) and value:
                return value
    return ""


class HNAlgoliaProvider(SearchProvider):
    """Hacker News Algolia search provider. No API key required."""

    name = "hn_algolia"

    def __init__(
        self,
        api_url: str = HN_ALGOLIA_API_URL,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        parsed = urlparse(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                f"HNAlgoliaProvider: invalid api_url {api_url!r}"
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
        host = urlparse(self._api_base).netloc.lower()
        allow_hosts = [host]

        # ``tags=story`` narrows to stories; we still want the
        # broader corpus because LinkedIn research is often
        # about industry commentary, not only "Show HN" posts.
        url = (
            f"{self._api_base}/api/v1/search"
            f"?query={quote(query or '')}"
            f"&hitsPerPage={int(max_results)}"
        )
        try:
            status_code, payload, _headers = await safe_http_json(
                url,
                allow_hosts=allow_hosts,
                timeout_seconds=self._timeout_seconds,
            )
        except _SearchHttpError as exc:
            logger.info("HN Algolia: HTTP failure (%s); raising unavailable", exc)
            raise _raise_hn_unavailable(self.name, exc, query)

        results = _parse_hn_response(payload, max_results)
        if not results:
            logger.info("HN Algolia: no results for %r", (query or "")[:80])
        else:
            logger.info("HN Algolia: %d result(s)", len(results))
        return dedupe_by_url(results)


def _parse_hn_response(
    payload: Dict[str, Any],
    max_results: int,
) -> List[Dict[str, str]]:
    """Turn an HN Algolia JSON payload into normalized results."""
    raw = payload.get("hits")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        title = (
            str(entry.get("title") or "")
            or str(entry.get("story_title") or "")
        )
        if not title:
            continue
        url = (
            str(entry.get("url") or "")
            or str(entry.get("story_url") or "")
        )
        if not url:
            object_id = str(entry.get("objectID") or "")
            if object_id:
                url = HN_ITEM_PREFIX + object_id
        if not url:
            continue
        # Snippet priority: highlighted comment text, story text,
        # highlighted title, or the raw title as a last resort.
        highlight = entry.get("_highlightResult") or {}
        snippet = (
            _highlight_text(highlight, "comment_text", "story_text")
            or _highlight_text(highlight, "title", "story_title")
            or str(entry.get("story_text") or "")
            or title
        )
        normalized = normalize_result(title=title, url=url, snippet=snippet)
        if normalized is not None:
            out.append(normalized)
        if len(out) >= max_results:
            break
    return out


def _raise_hn_unavailable(
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
    "HNAlgoliaProvider",
    "HN_ALGOLIA_API_URL",
    "DEFAULT_TIMEOUT_SECONDS",
]
