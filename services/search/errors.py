"""Exception hierarchy for the multi-provider search layer.

Mirrors the convention used by ``services/llm/base.py`` for the LLM
layer so callers can use the same try/except pattern.

The root exception is :class:`SearchError`. Subclasses add a
machine-readable ``code`` that callers (the workflow layer, the
global error handlers) can use to surface a precise error message
without parsing the exception text.

The classes are deliberately narrow — they cover the three failure
modes the orchestrator actually distinguishes when falling back
between providers:

  * :class:`SearchRateLimitedError` — 429 from the upstream; another
    instance or provider may not be rate-limited.
  * :class:`SearchBlockedError` — 4xx other than 429 (e.g. 401, 403,
    451) or an SSRF-family rejection. The provider's host is
    unreachable to the upstream; the next provider may be reachable.
  * :class:`SearchUnavailableError` — 5xx, timeout, network failure,
    malformed response, or exhausted retries on a single provider.
    The next provider may still be available.

When every provider in the priority list has failed with any of
the above, :class:`SearchService` raises :class:`SearchUnavailableError`
with the full attempt list attached so the workflow layer can log
exactly which providers were tried and why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SearchError(Exception):
    """Root exception for all search-layer failures."""

    def __init__(self, message: str, *, code: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details: Dict[str, Any] = dict(details or {})


class SearchRateLimitedError(SearchError):
    """The upstream returned HTTP 429 (or equivalent throttling signal).

    Carries the upstream provider name and (if known) the retry-after
    header value so the orchestrator can pick a different provider
    without waiting.
    """

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="search_rate_limited", details=details)
        self.provider = provider


class SearchBlockedError(SearchError):
    """The upstream rejected the request as unauthorized, forbidden,
    or otherwise blocked (4xx other than 429)."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, code="search_blocked", details=details)
        self.provider = provider


@dataclass
class SearchAttempt:
    """One provider's attempt in a SearchService chain.

    Carries only non-secret information. The error message is a
    single-line, secret-scrubbed string.
    """

    provider: str
    query: str
    error_type: str          # e.g. "SearchRateLimitedError", "SearchUnavailableError"
    error_message: str       # safe, single-line
    fallback_eligible: bool  # whether the orchestrator advanced

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "query": self.query,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "fallback_eligible": self.fallback_eligible,
        }


class SearchUnavailableError(SearchError):
    """Raised by :class:`SearchService` when every provider in the
    configured priority list failed.

    Carries the structured ``attempts`` list so the workflow layer
    can log exactly which providers were tried and why each one
    failed. The exception is the canonical signal to the workflow
    that live research is unavailable; the writer will fall back
    to model knowledge and the persisted draft's
    ``research_summary`` will be ``None`` (not a fabricated string).
    """

    def __init__(self, attempts: List[SearchAttempt]) -> None:
        self.attempts: List[SearchAttempt] = list(attempts)
        self.error_code = "search_unavailable"
        self.agent = "search"
        summary = "; ".join(
            f"{a.provider}={a.error_type}" for a in self.attempts
        ) or "no providers configured"
        super().__init__(
            f"All search providers failed: {summary}",
            code="search_unavailable",
            details={
                "attempt_count": len(self.attempts),
                "providers_tried": [a.provider for a in self.attempts],
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "agent": self.agent,
            "attempted_providers": [a.to_dict() for a in self.attempts],
        }


__all__ = [
    "SearchError",
    "SearchRateLimitedError",
    "SearchBlockedError",
    "SearchAttempt",
    "SearchUnavailableError",
]
