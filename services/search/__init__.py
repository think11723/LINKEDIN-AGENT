"""Search providers — multi-source, free, SSRF-safe.

Public surface of the new search layer. The legacy sync
``search_web`` function lives in :mod:`.legacy_compat` and is
re-exported here so that ``from services.search import search_web``
keeps working now that ``services.search`` is a package.
"""

from ._legacy_compat import (
    asearch_web,
    get_search_service,
    reset_search_service,
    search_web,
)
from .base import (
    SearchProvider,
    clean_snippet,
    clean_title,
    dedupe_by_url,
    normalize_result,
)
from .errors import (
    SearchAttempt,
    SearchBlockedError,
    SearchError,
    SearchRateLimitedError,
    SearchUnavailableError,
)
from .hn_algolia import HNAlgoliaProvider
from .searxng import SearXNGProvider, _parse_instance_pool
from .service import SearchOutcome, SearchService
from .wikipedia import WikipediaProvider

__all__ = [
    # Errors
    "SearchError",
    "SearchAttempt",
    "SearchBlockedError",
    "SearchRateLimitedError",
    "SearchUnavailableError",
    # Base
    "SearchProvider",
    "normalize_result",
    "dedupe_by_url",
    "clean_snippet",
    "clean_title",
    # Providers
    "SearXNGProvider",
    "WikipediaProvider",
    "HNAlgoliaProvider",
    # Service
    "SearchService",
    "SearchOutcome",
    # Legacy compat
    "search_web",
    "asearch_web",
    "get_search_service",
    "reset_search_service",
    # Helpers
    "_parse_instance_pool",
]
