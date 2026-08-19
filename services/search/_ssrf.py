"""Internal helpers for the search layer.

This module wraps the existing project-wide SSRF guard
(``backend.app.services.sources.ssrf``) with a small async
HTTP-call helper that decodes JSON. The search providers do not
talk to the network directly — they go through ``safe_http_json``
so the same DNS pinning, IP-family vetting, TLS verification,
byte cap, redirect loop, and host allowlist rules that the
URL-mode feature uses apply to the topic-mode research path too.

The helper is intentionally minimal: it does no retries, no
provider-specific logic, and no response shape assumptions beyond
``status_code``, ``body`` (bytes), and ``headers``. The provider
modules own URL formation, JSON parsing, and retry semantics.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from backend.app.services.sources.ssrf import (
    SafeResponse,
    SourceBlockedError,
    SourceUnavailableError,
    safe_get,
)


#: Default per-request timeout for search queries. Kept low so a
#: single generation request never blocks for more than ~30s even
#: if every provider is slow.
DEFAULT_TIMEOUT_SECONDS: float = 8.0

#: Default per-response byte cap. Each search response is small
#: (a few KB of JSON); 1 MiB is generous.
DEFAULT_MAX_BYTES: int = 1 * 1024 * 1024


class _SearchHttpError(Exception):
    """Internal exception raised by ``safe_http_json`` on transport
    failure. The caller (a provider) translates this into one of
    the public ``services.search.errors`` types.

    Carries the HTTP status code and a short message; the response
    body is intentionally NOT carried (it can be hundreds of KB and
    is rarely useful for orchestrator decisions).
    """

    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


async def safe_http_json(
    url: str,
    *,
    allow_hosts: List[str],
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    """GET ``url`` through the SSRF guard and return ``(status, json, headers)``.

    The host must appear in ``allow_hosts``; if not, the SSRF guard
    raises ``SourceBlockedError`` which is translated to
    ``_SearchHttpError`` with a clear message so the caller can
    surface ``SearchBlockedError`` to the orchestrator.

    On 4xx / 5xx / non-2xx the helper raises ``_SearchHttpError``
    with the status code; the caller maps to ``SearchRateLimitedError``
    (for 429) or ``SearchUnavailableError`` (for everything else).

    On network / TLS / timeout failures the SSRF guard raises
    ``SourceUnavailableError``; the helper translates that to
    ``_SearchHttpError`` with ``status_code=0`` so the caller can
    map to ``SearchUnavailableError``.
    """
    try:
        response: SafeResponse = await safe_get(
            url,
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
            allow_hosts=allow_hosts,
        )
    except SourceBlockedError as exc:
        raise _SearchHttpError(
            f"blocked: {exc.message}",
            status_code=0,
        ) from exc
    except SourceUnavailableError as exc:
        # Network / TLS / timeout / 4xx / 5xx from the SSRF guard.
        # We can't tell from the exception alone whether this was a
        # rate-limit, a server error, or a timeout; the helper returns
        # 0 and the caller maps to SearchUnavailableError.
        raise _SearchHttpError(
            f"unavailable: {exc.message}",
            status_code=0,
        ) from exc

    if response.status_code != 200:
        raise _SearchHttpError(
            f"http {response.status_code}",
            status_code=response.status_code,
        )

    try:
        payload = json.loads(response.body.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _SearchHttpError(
            f"malformed json: {exc}",
            status_code=response.status_code,
        ) from exc

    if not isinstance(payload, dict):
        raise _SearchHttpError(
            f"unexpected json root type: {type(payload).__name__}",
            status_code=response.status_code,
        )

    # response.headers is a dict[str, str] per SafeResponse.
    return response.status_code, payload, dict(response.headers)


__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_MAX_BYTES",
    "safe_http_json",
    "_SearchHttpError",
]
