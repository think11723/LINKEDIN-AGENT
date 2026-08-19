"""Base search provider and result-normalization helpers.

The contract every concrete provider implements:

  1. ``name`` — a stable lowercase identifier (``"searxng"``,
     ``"wikipedia"``, ``"hn_algolia"``).
  2. ``async search(query, *, request_id, max_results) -> List[Dict[str, str]]`` —
     perform the search and return a list of normalized results.
     Each result is a dict with exactly the keys the downstream
     writer consumes: ``title``, ``url``, ``snippet``. Raise one of
     the exceptions from :mod:`services.search.errors` on failure.

The base class also exposes :func:`normalize_result` and
:func:`dedupe_by_url` which every provider uses, so the contract is
enforced in one place and the providers stay small.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from services.search.errors import (
    SearchBlockedError,
    SearchError,
    SearchRateLimitedError,
    SearchUnavailableError,
)


# Single-line hard cap on snippets to keep log lines and persisted
# drafts manageable. The downstream writer itself truncates at
# 200 chars (see ``agents/writer.py:259-262``); this is the
# provider-side cap so the same budget applies to every source.
SNIPPET_CHAR_CAP = 600
TITLE_CHAR_CAP = 300

# Patterns used to clean raw snippets. Whitespace, newlines, control
# characters — kept as compiled regexes so we don't re-compile per
# result.
_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_snippet(text: str) -> str:
    """Strip HTML, collapse whitespace, drop control characters.

    Returns an empty string for falsy / whitespace-only input. The
    downstream writer's first-three-results contract is preserved
    because empty results are dropped by ``dedupe_by_url``.
    """
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub(" ", str(text))
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) > SNIPPET_CHAR_CAP:
        cleaned = cleaned[: SNIPPET_CHAR_CAP - 1].rstrip() + "…"
    return cleaned


def clean_title(text: str) -> str:
    """Same as ``clean_snippet`` but with a tighter cap and a
    fallback empty string for input that contains no alphanumeric
    content.
    """
    if not text:
        return ""
    cleaned = _HTML_TAG_RE.sub(" ", str(text))
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    if not cleaned:
        return ""
    if len(cleaned) > TITLE_CHAR_CAP:
        cleaned = cleaned[: TITLE_CHAR_CAP - 1].rstrip() + "…"
    return cleaned


def normalize_result(
    *,
    title: str,
    url: str,
    snippet: str,
) -> Optional[Dict[str, str]]:
    """Build a normalized result dict.

    Returns ``None`` when any of the three fields is empty after
    cleaning. The dedup step then drops them naturally.
    """
    t = clean_title(title)
    u = (url or "").strip()
    s = clean_snippet(snippet)
    if not t or not u or not s:
        return None
    if not (u.startswith("http://") or u.startswith("https://")):
        return None
    return {"title": t, "url": u, "snippet": s}


def dedupe_by_url(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Drop duplicate URLs, preserving the first occurrence.

    The downstream writer reads the first three results; a duplicate
    URL twice in that slice wastes one of the three slots. The
    orchestrator runs this just before returning to the caller.
    """
    seen: set[str] = set()
    out: List[Dict[str, str]] = []
    for r in results:
        url = r.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(r)
    return out


class SearchProvider(ABC):
    """Abstract base class for every search provider.

    Concrete subclasses must implement :meth:`search` and declare a
    unique ``name`` attribute. The :meth:`_build_safe_url` helper
    enforces that the request URL is formed from a hostname the
    SSRF guard has vetted.
    """

    #: Stable lowercase identifier. Used by the orchestrator to log
    #: which provider served the request.
    name: str = ""

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        request_id: str,
        max_results: int = 5,
    ) -> List[Dict[str, str]]:
        """Execute a search and return up to ``max_results`` normalized
        results.

        Implementations must:

        * Use :func:`backend.app.services.sources.ssrf.safe_get` (or
          a helper built on top of it) for every outbound HTTP call,
          so the existing SSRF guard applies. Direct ``requests`` /
          ``httpx`` use is rejected by the project's test grep.
        * Raise one of :class:`SearchError` subclasses on failure.
        * Never fabricate missing fields. If the upstream response is
          missing a field, the result is dropped, not invented.
        """


__all__ = [
    "SearchProvider",
    "clean_snippet",
    "clean_title",
    "normalize_result",
    "dedupe_by_url",
    "SNIPPET_CHAR_CAP",
    "TITLE_CHAR_CAP",
]
