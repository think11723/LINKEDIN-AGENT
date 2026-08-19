"""Legacy ``search_web`` compatibility wrapper.

This module lives inside the ``services.search`` package so that
``services/search.py`` (the top-level compat file) and the package's
``__init__.py`` can both import from it without a circular import.

The wrapper preserves the legacy sync ``search_web()`` signature
and semantics (returns ``[]`` on any failure) so existing callers
do not have to change.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Dict, List, Optional

from services.search.hn_algolia import HNAlgoliaProvider
from services.search.searxng import SearXNGProvider
from services.search.service import SearchService
from services.search.wikipedia import WikipediaProvider

logger = logging.getLogger(__name__)


_default_service_lock = threading.Lock()
_default_service: Optional[SearchService] = None


def _build_default_service() -> SearchService:
    """Build the default service with the priority list:
    SearXNG → Wikipedia → Hacker News Algolia.

    All three are free, no API key, A-class providers.
    """
    return SearchService(providers=[
        SearXNGProvider(),
        WikipediaProvider(),
        HNAlgoliaProvider(),
    ])


def get_search_service() -> SearchService:
    """Return the lazily-built default search service.

    The service is built once per process. Tests that need a
    fresh service should construct their own.
    """
    global _default_service
    if _default_service is None:
        with _default_service_lock:
            if _default_service is None:
                _default_service = _build_default_service()
    return _default_service


def reset_search_service() -> None:
    """Drop the cached default service (used by tests)."""
    global _default_service
    with _default_service_lock:
        _default_service = None


def search_web(
    query: str,
    max_results: int = 5,
    max_retries: int = 3,  # noqa: ARG001  (kept for API compat; ignored)
) -> List[Dict[str, str]]:
    """Perform a web search using the multi-provider fallback chain.

    The original signature is preserved for backward compatibility.
    ``max_retries`` is accepted but no longer used: per-provider
    retry lives inside each provider (the SearXNG provider, for
    example, rotates through its instance pool).

    On any failure (every provider in the chain failed, or every
    provider returned 0 results), this function returns ``[]``
    — the same behaviour as the original implementation. The
    structured outcome is available via :func:`asearch_web` for
    callers that want it.
    """
    try:
        outcome = asyncio.run(
            get_search_service().search(
                query,
                request_id="search_web",
                max_results=max_results,
            )
        )
        return list(outcome.results)
    except Exception:  # noqa: BLE001
        # The new layer raises SearchUnavailableError on full
        # chain failure; the legacy contract is "return [] on
        # failure" so we preserve that.
        logger.info(
            "search_web: no provider returned results for %r",
            (query or "")[:80],
        )
        return []


async def asearch_web(
    query: str,
    *,
    request_id: str = "asearch_web",
    max_results: int = 5,
) -> Any:
    """Async entry point. Returns the structured :class:`SearchOutcome`.

    Raises :class:`SearchUnavailableError` if every provider failed
    (callers that want the legacy ``[]`` behaviour can wrap this
    in ``try/except``).
    """
    return await get_search_service().search(
        query,
        request_id=request_id,
        max_results=max_results,
    )


__all__ = [
    "search_web",
    "asearch_web",
    "get_search_service",
    "reset_search_service",
]
