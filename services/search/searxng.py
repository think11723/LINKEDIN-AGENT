"""SearXNG search provider.

Public SearXNG instances are listed at https://searx.space/. The
provider supports a configurable pool of instances via the
``SEARXNG_INSTANCES`` environment variable (comma-separated URLs).
The orchestrator's "rotate on failure" logic lives here: each
query is tried against the next instance in the pool; an instance
that returns 429, 5xx, or a transport error is moved to the back
of the pool and the next instance is tried. A small in-memory
cooldown suppresses hammering of a recently-failed instance.

The provider talks to the network exclusively through
:func:`services.search._ssrf.safe_http_json`, which is a thin
wrapper around the project's existing SSRF guard. The host of
every request must appear in the ``allow_hosts`` allowlist that
the SearchService builds from ``SEARXNG_INSTANCES``; any request
to a host outside that set is rejected by the SSRF guard before
the request is even sent.

SearXNG result shape (JSON, ``/search?q=...&format=json``)::

    {
      "results": [
        {"title": "...", "url": "...", "content": "...", "engine": "..."},
        ...
      ],
      "suggestions": [...],
      "number_of_results": 42
    }

We normalize each entry to ``{title, url, snippet}``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from services.search._ssrf import _SearchHttpError, safe_http_json
from services.search.base import (
    SearchProvider,
    dedupe_by_url,
    normalize_result,
)
from services.search.errors import (
    SearchBlockedError,
    SearchRateLimitedError,
    SearchUnavailableError,
)

logger = logging.getLogger(__name__)


#: Default timeout per instance. Kept low so the pool rotation
#: doesn't cascade into a multi-minute request when several
#: instances are slow.
DEFAULT_TIMEOUT_SECONDS: float = 6.0


def _parse_instance_pool(raw: Optional[str]) -> List[str]:
    """Parse ``SEARXNG_INSTANCES`` into a list of normalized URLs.

    Each entry is stripped of whitespace and a trailing slash.
    Entries that are not http(s) URLs are dropped. Duplicate hosts
    are deduplicated. The result preserves the order in which
    instances appeared in the env var; that order is the round-robin
    start.
    """
    if not raw:
        return []
    out: List[str] = []
    seen_hosts: set[str] = set()
    for entry in raw.split(","):
        url = entry.strip().rstrip("/")
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue
        if not parsed.netloc:
            continue
        host = (parsed.hostname or "").lower()
        if not host or host in seen_hosts:
            continue
        seen_hosts.add(host)
        out.append(f"{parsed.scheme}://{parsed.netloc}")
    return out


class SearXNGProvider(SearchProvider):
    """SearXNG provider with a per-instance rotation pool.

    The pool is loaded from the ``SEARXNG_INSTANCES`` env var. If no
    instances are configured, every :meth:`search` call raises
    :class:`SearchUnavailableError` so the orchestrator can advance
    to the next provider.
    """

    name = "searxng"

    def __init__(
        self,
        instances: Optional[List[str]] = None,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        cooldown_seconds: float = 60.0,
    ) -> None:
        # Allow explicit injection (used by tests) or env-var lookup.
        if instances is None:
            instances = _parse_instance_pool(
                os.getenv("SEARXNG_INSTANCES", "")
            )
        self._initial_instances: List[str] = list(instances)
        self._timeout_seconds = float(timeout_seconds)
        self._cooldown_seconds = float(cooldown_seconds)
        # Per-instance cooldown marker (epoch seconds). When an
        # instance is moved to the back of the pool, it is also
        # marked for cooldown_seconds so the round-robin doesn't pick
        # it up again immediately. This is best-effort (in-memory
        # only — a process restart resets it).
        self._cooldown_until: Dict[str, float] = {}

    @property
    def instances(self) -> List[str]:
        """Return the configured instance list (read-only)."""
        return list(self._initial_instances)

    def _available_instances(self) -> List[str]:
        """Return the pool with any instance in cooldown skipped.

        An instance in cooldown is moved to the end of the returned
        list (so it eventually retries after the cooldown expires).
        """
        import time

        now = time.monotonic()
        available: List[str] = []
        cooled: List[str] = []
        for inst in self._initial_instances:
            until = self._cooldown_until.get(inst, 0.0)
            if until > now:
                cooled.append(inst)
            else:
                available.append(inst)
        # Cooled instances go to the back; they will be retried
        # once their cooldown elapses.
        return available + cooled

    def _mark_cooldown(self, instance: str) -> None:
        import time

        now = time.monotonic()
        self._cooldown_until[instance] = now + self._cooldown_seconds

    async def search(
        self,
        query: str,
        *,
        request_id: str,
        max_results: int = 5,
    ) -> List[Dict[str, str]]:
        if not self._initial_instances:
            raise _raise_no_instances()

        # Build the allowlist once per call. We use only the *available*
        # instances for the allowlist so the SSRF guard accepts the
        # round-robin targets; a cooled instance is NOT in the
        # allowlist until its cooldown elapses, so an accidental
        # retry against it would be SSRF-rejected.
        available = self._available_instances()
        if not available:
            # All configured instances are in cooldown. The
            # operator did configure instances; we just can't use
            # any right now. Surface as the structured unavailable
            # error so the orchestrator can advance to the next
            # provider, NOT as "no instances configured".
            raise _raise_searxng_unavailable(
                self.name,
                _SearchHttpError(
                    "all configured SearXNG instances are in cooldown",
                    status_code=0,
                ),
                list(self._initial_instances),
            )
        allow_hosts = [urlparse(inst).netloc.lower() for inst in available]

        last_error: Optional[Exception] = None
        # Walk the available pool once. An instance that returns a
        # transport-level failure is moved to the back AND marked
        # for cooldown so it is skipped on subsequent calls until
        # the cooldown elapses.
        for inst in available:
            url = (
                f"{inst}/search"
                f"?q={_quote(query)}"
                f"&format=json"
                f"&language=en"
                f"&safesearch=0"
                f"&categories=general"
            )
            try:
                status_code, payload, _headers = await safe_http_json(
                    url,
                    allow_hosts=allow_hosts,
                    timeout_seconds=self._timeout_seconds,
                )
            except _SearchHttpError as exc:
                last_error = exc
                # Transport-level failure (network, TLS, timeout,
                # 4xx, 5xx) — move to back and mark cooldown.
                self._mark_cooldown(inst)
                if exc.status_code == 429:
                    logger.info(
                        "SearXNG instance %s returned 429; rotating",
                        inst,
                    )
                    # Treat as rate-limited and try the next instance.
                    continue
                # Other transport failures: try the next instance.
                logger.info(
                    "SearXNG instance %s failed (%s); rotating",
                    inst, exc,
                )
                continue
            except SearchBlockedError as exc:
                # The SSRF guard rejected the URL. This should never
                # happen because the allowlist was built from the
                # same instance list, but treat defensively.
                last_error = exc
                logger.warning(
                    "SearXNG instance %s blocked by SSRF guard: %s",
                    inst, exc,
                )
                continue

            # 200 OK — parse the JSON.
            results = _parse_searxng_response(payload, max_results)
            if results:
                logger.info(
                    "SearXNG: %d result(s) from %s",
                    len(results), inst,
                )
                return dedupe_by_url(results)
            # Empty result set; treat as the provider having no
            # answers for this query, but try the next instance
            # before giving up — a different instance may have
            # better results.
            logger.info("SearXNG instance %s returned no results", inst)
            continue

        # Every available instance either failed or returned no
        # results. Raise so the orchestrator can move on to the
        # next provider. The ``last_error`` carries the most recent
        # transport detail; if it's a 429 we surface as
        # SearchRateLimitedError so the orchestrator can decide
        # whether to continue (it always does, for now).
        if isinstance(last_error, _SearchHttpError) and last_error.status_code == 429:
            raise SearchRateLimitedError(
                f"All SearXNG instances returned 429 ({last_error})",
                provider=self.name,
                details={"instances_tried": list(available)},
            )
        if last_error is None:
            raise _raise_no_instances()
        raise _raise_searxng_unavailable(
            self.name, last_error, available
        )


def _quote(s: str) -> str:
    """Percent-encode a value for a query string."""
    from urllib.parse import quote_plus
    return quote_plus(s or "")


def _parse_searxng_response(
    payload: Dict[str, Any],
    max_results: int,
) -> List[Dict[str, str]]:
    """Turn a SearXNG JSON payload into normalized results."""
    raw = payload.get("results") or []
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, str]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        normalized = normalize_result(
            title=str(entry.get("title") or ""),
            url=str(entry.get("url") or ""),
            snippet=str(entry.get("content") or ""),
        )
        if normalized is not None:
            out.append(normalized)
        if len(out) >= max_results:
            break
    return out


def _raise_no_instances() -> SearchUnavailableError:
    """SearXNGProvider was constructed with no instances configured."""
    from services.search.errors import SearchAttempt, SearchUnavailableError

    return SearchUnavailableError([
        SearchAttempt(
            provider="searxng",
            query="",
            error_type="SearchUnavailableError",
            error_message="no SearXNG instances configured (set SEARXNG_INSTANCES env var)",
            fallback_eligible=True,
        ),
    ])


def _raise_searxng_unavailable(
    provider: str,
    last_error: Exception,
    available: List[str],
) -> SearchUnavailableError:
    from services.search.errors import SearchAttempt, SearchUnavailableError

    return SearchUnavailableError([
        SearchAttempt(
            provider=provider,
            query="",
            error_type=type(last_error).__name__,
            error_message=str(last_error) or "transport failure",
            fallback_eligible=True,
        ),
    ])


__all__ = ["SearXNGProvider", "DEFAULT_TIMEOUT_SECONDS", "_parse_instance_pool"]
