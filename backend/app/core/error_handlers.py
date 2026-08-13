"""Global FastAPI exception handlers.

Phase 8A / P0-1.

Goals:

- Return a structured envelope for *all* errors so the SPA can render
  predictable toasts.
- Preserve useful application messages (HTTPException detail).
- NEVER expose internal exception text, tracebacks, LLM provider internals,
  MongoDB errors, Firebase errors, or LinkedIn response bodies to clients.
- Server-side logs always contain the full traceback + a correlation
  request id that is also returned to the client.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# Public-safe status → code mapping. Only used for the generic envelope.
_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    406: "NOT_ACCEPTABLE",
    409: "CONFLICT",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_SERVER_ERROR",
    501: "NOT_IMPLEMENTED",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def _code_for(status_code: int) -> str:
    return _STATUS_CODE_MAP.get(status_code, "ERROR")


def _safe_detail(detail: Any) -> str:
    """Coerce HTTPException detail into a string that is safe to send.

    `detail` may be a plain string, a dict (e.g. Mongo validation), or a
    list of error dicts (FastAPI/Pydantic). Strings and dicts are kept
    as-is. Lists of error dicts are summarised as ``"; "``. Anything else
    is replaced with a generic message.
    """
    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict):
        # Common case: {"detail": "..."} from FastAPI internals.
        if "detail" in detail and isinstance(detail["detail"], str):
            return detail["detail"]
        return str(detail)
    if isinstance(detail, list):
        parts: list[str] = []
        for entry in detail:
            if isinstance(entry, dict):
                msg = entry.get("msg") or entry.get("message") or ""
                loc = entry.get("loc") or []
                if loc:
                    parts.append(f"{'.'.join(str(x) for x in loc)}: {msg}")
                else:
                    parts.append(str(msg))
            else:
                parts.append(str(entry))
        return "; ".join(parts) if parts else "Validation error"
    if detail is None:
        return ""
    return str(detail)


def _envelope(*, code: str, message: str, request_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
        }
    }
    if extra:
        body["error"].update(extra)
    return body


def _request_id(request: Request) -> str:
    """Return the request id from the response state, generating one if missing."""
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = uuid.uuid4().hex
        request.state.request_id = rid
    return rid


async def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException) -> JSONResponse:
    """Handle FastAPI/Starlette HTTPException with the safe envelope."""
    rid = _request_id(request)
    message = _safe_detail(exc.detail)
    # Log expected errors at INFO (not WARNING) — they're part of normal flow.
    logger.info(
        "HTTP error %s on %s %s: %s (request_id=%s)",
        exc.status_code, request.method, request.url.path, message, rid,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(
            code=_code_for(exc.status_code),
            message=message,
            request_id=rid,
        ),
        headers=exc.headers or None,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """422 validation errors — keep a useful summary but never raw exceptions."""
    rid = _request_id(request)
    message = _safe_detail(exc.errors())
    logger.info("Validation error on %s %s: %s (request_id=%s)",
                request.method, request.url.path, message, rid)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_envelope(
            code="VALIDATION_ERROR",
            message=message,
            request_id=rid,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """500 fallback — log the traceback server-side, return a generic envelope."""
    rid = _request_id(request)
    # Log the full traceback server-side. NEVER include it in the response.
    logger.exception(
        "Unhandled exception on %s %s (request_id=%s)",
        request.method, request.url.path, rid,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_envelope(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred.",
            request_id=rid,
        ),
    )


def install_error_handlers(app: FastAPI) -> None:
    """Wire all handlers onto the FastAPI app.

    Phase 8A / P0-1.

    Notes on coverage:

    - ``Exception`` is registered so any uncaught error becomes a safe 500.
    - ``HTTPException`` (FastAPI) and ``StarletteHTTPException`` are
      both routed to the safe envelope so 401/403/404/409/422 keep
      their useful application messages.
    - ``RequestValidationError`` is registered for the 422 envelope.
    """
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    # Register concrete exception types AND a catch-all for `Exception`.
    # FastAPI/Starlette walks the MRO. The bare-`Exception` entry is the
    # last-resort fallback for anything we did not anticipate.
    for cls in (Exception, RuntimeError, ValueError, KeyError, TypeError):
        app.add_exception_handler(cls, unhandled_exception_handler)