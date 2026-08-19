"""Search Tool for LinkedIn Content Agent — compatibility wrapper.

This file is now a thin re-export shim. The actual implementation
lives in the :mod:`services.search` package (the directory of the
same name). Python gives the package precedence over this module
when both exist, so ``from services.search import search_web``
resolves to the package, which re-exports the symbol.

The original implementation used the ``duckduckgo_search`` library
directly and returned ``[]`` on any failure (a silent degradation
that masked rate-limit problems in production).

The new multi-provider layer is at :mod:`services.search`. The
priority chain is:

    SearXNG (configurable instance pool)
        ↓ failure
    Wikipedia REST
        ↓ failure
    Hacker News Algolia
        ↓ failure
    SearchUnavailableError

All three primary providers are A-class (truly free, no API key,
no credit card). The orchestrator reuses the project's existing
SSRF guard (``backend.app.services.sources.ssrf``) for every
outbound HTTP call.
"""

from __future__ import annotations

from services.search._legacy_compat import (  # noqa: F401  (re-export)
    asearch_web,
    get_search_service,
    reset_search_service,
    search_web,
)

__all__ = [
    "search_web",
    "asearch_web",
    "get_search_service",
    "reset_search_service",
]
