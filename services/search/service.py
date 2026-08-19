"""Multi-provider search orchestrator.

Mirrors the design of :class:`LLMFactory.fallback` in
:smod:`services.llm.factory`. On every call, the orchestrator walks
the configured provider priority list, tries each provider in turn,
and on a transient failure (rate limit, transport error, blocked
host) advances to the next provider. A non-transient failure (e.g.
an empty result set) is *not* an error — the orchestrator tries the
next provider to give the caller the best chance of getting any
results. Only when every provider has been tried does the
orchestrator give up and raise :class:`SearchUnavailableError`
with the structured attempt list attached.

The orchestrator never invents results. A successful call returns
a :class:`SearchOutcome` whose ``results`` field is the list of
normalized results from the first provider that returned at least
one. ``provider`` is the name of that provider. ``attempts`` is the
list of providers that were tried, in order, including successful
ones (so the workflow layer can log the full audit trail).

The orchestrator deduplicates results by URL before returning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from services.search.base import (
    SearchProvider,
    dedupe_by_url,
)
from services.search.errors import (
    SearchAttempt,
    SearchError,
    SearchUnavailableError,
)

logger = logging.getLogger(__name__)


@dataclass
class SearchOutcome:
    """The structured result of a :class:`SearchService.search` call.

    Attributes:
        results: Normalized results, deduplicated by URL.
        provider: Name of the provider that supplied the results.
            ``None`` if every provider failed.
        attempts: Per-provider attempt records, in the order they
            were tried. Includes successful providers (whose
            ``error_type`` is empty / marked successful).
    """

    results: List[Dict[str, str]] = field(default_factory=list)
    provider: Optional[str] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "result_count": len(self.results),
            "attempts": list(self.attempts),
        }


def _attempt_record(
    *,
    provider: str,
    query: str,
    success: bool,
    result_count: int = 0,
    error_type: str = "",
    error_message: str = "",
    fallback_eligible: bool = True,
) -> Dict[str, Any]:
    """Build a single attempt record for ``SearchOutcome.attempts``."""
    rec: Dict[str, Any] = {
        "provider": provider,
        "query": query,
        "success": success,
        "result_count": result_count,
        "fallback_eligible": fallback_eligible,
    }
    if error_type:
        rec["error_type"] = error_type
    if error_message:
        rec["error_message"] = error_message
    return rec


class SearchService:
    """Multi-provider search orchestrator.

    Configuration: a list of provider instances in priority order.
    The list is typically::

        SearchService(providers=[
            SearXNGProvider(),
            WikipediaProvider(),
            HNAlgoliaProvider(),
        ])

    but callers may inject any provider. The orchestrator does
    not retry within a single provider (the provider itself owns
    its own retry strategy — see :class:`SearXNGProvider`'s
    instance rotation). Each provider is tried at most once per
    call.
    """

    def __init__(self, providers: Sequence[SearchProvider]) -> None:
        if not providers:
            raise ValueError(
                "SearchService requires at least one provider"
            )
        self._providers: List[SearchProvider] = list(providers)

    @property
    def providers(self) -> List[SearchProvider]:
        return list(self._providers)

    async def search(
        self,
        query: str,
        *,
        request_id: str,
        max_results: int = 5,
    ) -> SearchOutcome:
        """Run the configured providers in order.

        Returns a :class:`SearchOutcome` with the first non-empty
        result set. Raises :class:`SearchUnavailableError` if every
        provider failed; the exception carries the structured
        attempt list.
        """
        if not query or not query.strip():
            # No query to run. Surface as a structured empty result
            # so the orchestrator can decide what to do.
            return SearchOutcome(
                results=[],
                provider=None,
                attempts=[_attempt_record(
                    provider="<none>",
                    query=query or "",
                    success=False,
                    error_type="ValueError",
                    error_message="empty query",
                    fallback_eligible=False,
                )],
            )

        outcome = SearchOutcome()
        for provider in self._providers:
            try:
                results = await provider.search(
                    query,
                    request_id=request_id,
                    max_results=max_results,
                )
            except SearchError as exc:
                # Provider-specific structured failure. If the
                # exception is a single-provider SearchUnavailableError
                # (raised by a provider that exhausted its own
                # retry budget), extract the per-provider message
                # from the exception's attempts list so the
                # orchestrator's attempt record carries the
                # *provider's* error, not the chain summary.
                err_type = type(exc).__name__
                err_msg = str(exc) or exc.code
                if (
                    isinstance(exc, SearchUnavailableError)
                    and len(exc.attempts) == 1
                ):
                    err_type = exc.attempts[0].error_type
                    err_msg = exc.attempts[0].error_message
                outcome.attempts.append(_attempt_record(
                    provider=provider.name,
                    query=query,
                    success=False,
                    error_type=err_type,
                    error_message=err_msg,
                    fallback_eligible=True,
                ))
                logger.info(
                    "SearchService: provider %s failed (%s); advancing",
                    provider.name, exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                # Defensive catch for any unexpected error from a
                # provider. Treat as a transient failure.
                import traceback as _tb
                tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
                outcome.attempts.append(_attempt_record(
                    provider=provider.name,
                    query=query,
                    success=False,
                    error_type=type(exc).__name__,
                    error_message=(str(exc) or "unexpected error") + " | " + tb.splitlines()[-1] if tb else (str(exc) or "unexpected error"),
                    fallback_eligible=True,
                ))
                logger.warning(
                    "SearchService: provider %s raised unexpected %s; advancing: %s",
                    provider.name, type(exc).__name__, tb,
                )
                continue

            # The provider returned without raising. Even if the
            # list is empty we move on (an empty list is "no
            # results" — the next provider may have better results).
            deduped = dedupe_by_url(results or [])
            outcome.attempts.append(_attempt_record(
                provider=provider.name,
                query=query,
                success=True,
                result_count=len(deduped),
                fallback_eligible=True,
            ))
            if deduped:
                outcome.results = deduped
                outcome.provider = provider.name
                logger.info(
                    "SearchService: %s returned %d result(s) for %r",
                    provider.name, len(deduped),
                    (query or "")[:80],
                )
                return outcome
            logger.info(
                "SearchService: %s returned 0 results for %r; trying next",
                provider.name, (query or "")[:80],
            )
            continue

        # Every provider either failed or returned empty. If at
        # least one provider succeeded with 0 results, return
        # that empty outcome so the workflow can record
        # "search returned no results for this query" (which is
        # meaningfully different from "every provider failed").
        if outcome.attempts and any(a.get("success") for a in outcome.attempts):
            return outcome
        # Every provider failed. Raise the structured exception.
        attempts = [
            SearchAttempt(
                provider=a["provider"],
                query=a.get("query", ""),
                error_type=a.get("error_type", "SearchError"),
                error_message=a.get("error_message", ""),
                fallback_eligible=a.get("fallback_eligible", True),
            )
            for a in outcome.attempts
        ]
        raise SearchUnavailableError(attempts)


__all__ = ["SearchService", "SearchOutcome"]
