"""Request-ID correlation — Phase 8D / P3-1.

A small, focused module that owns:

* the canonical :class:`ContextVar` for the current request's ID
* the :class:`RequestIdMiddleware` that assigns a uuid4 (or accepts a
  caller-supplied header) and exposes it on ``request.state.request_id``
  and in the ``X-Request-ID`` response header
* a :class:`logging.Filter` that surfaces the active request ID on every
  LogRecord so future log formatters (P3-2) can include it without a
  separate refactor
* a public :func:`current_request_id` accessor used by error handlers

The middleware is the *only* component that mutates
``request_id_var`` — handlers and log filters read it. The
``ContextVar.reset(token)`` call is always paired with the matching
``set(...)`` so concurrent asyncio tasks cannot leak an ID across
requests.

Security:

* Generated IDs are ``uuid.uuid4().hex`` (non-predictable, 32 hex chars).
* Caller-supplied ``X-Request-ID`` headers are accepted for distributed
  -tracing compatibility, but validated strictly (length 1–128, charset
  ``[A-Za-z0-9_.-]``). Anything else is replaced with a fresh uuid4.
* The header value is never logged directly by the filter — only the
  validated value is propagated.
"""

from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


HEADER_NAME = "X-Request-ID"
_VALID_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")

#: ContextVar holding the current request's ID (or ``None`` outside a request).
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def current_request_id() -> Optional[str]:
    """Return the active request ID, or ``None`` outside a request scope."""
    return request_id_var.get()


def _generate_request_id() -> str:
    """Generate a fresh, non-predictable request ID."""
    return uuid.uuid4().hex


def _normalize_inbound(value: Optional[str]) -> Optional[str]:
    """Validate a caller-supplied ``X-Request-ID`` header.

    Returns the cleaned value if it is safe to use, else ``None`` so the
    caller falls back to a fresh uuid4.
    """
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if not _VALID_ID_RE.match(candidate):
        return None
    return candidate


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Bind a request ID to every HTTP request.

    Order of operations on a request:

    1. Resolve the ID (caller's ``X-Request-ID`` if valid, else fresh uuid4).
    2. Store on ``request.state.request_id``.
    3. Set the :data:`request_id_var` ContextVar; remember the reset token.
    4. Invoke the downstream stack inside a ``try/finally`` that always
       resets the ContextVar — no leak across requests, no leak on
       exceptions.
    5. Stamp ``X-Request-ID`` on the outgoing response (including error
       responses produced by the global exception handlers).
    """

    async def dispatch(self, request: Request, call_next):
        inbound = request.headers.get(HEADER_NAME)
        rid = _normalize_inbound(inbound) or _generate_request_id()
        request.state.request_id = rid

        token = request_id_var.set(rid)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)

        response.headers[HEADER_NAME] = rid
        return response


class RequestIdLogFilter(logging.Filter):
    """Attach the active request ID to every LogRecord.

    P3-2 (JSON logging) will read ``record.request_id``. The default is
    ``"-"`` so log records emitted outside a request scope (e.g. during
    application startup) carry a stable placeholder instead of raising
    ``AttributeError`` when a formatter references the attribute.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = request_id_var.get() or "-"
        return True


def install_request_id_log_filter() -> None:
    """Attach :class:`RequestIdLogFilter` to the root logger.

    Called once during application startup. Idempotent — repeated calls
    do not stack duplicate filters.
    """
    root = logging.getLogger()
    for existing in root.filters:
        if isinstance(existing, RequestIdLogFilter):
            return
    root.addFilter(RequestIdLogFilter())


def reset_request_id_log_filter() -> None:
    """Remove the :class:`RequestIdLogFilter` from the root logger.

    Intended for tests that need to assert a pristine log-filter state.
    """
    root = logging.getLogger()
    root.filters = [
        f for f in root.filters if not isinstance(f, RequestIdLogFilter)
    ]


__all__ = [
    "HEADER_NAME",
    "RequestIdLogFilter",
    "RequestIdMiddleware",
    "current_request_id",
    "install_request_id_log_filter",
    "request_id_var",
    "reset_request_id_log_filter",
]