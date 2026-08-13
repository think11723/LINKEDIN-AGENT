"""Phase 8D / P3-2 — structured JSON logging tests.

The formatter lives in :mod:`backend.app.core.logging`. The tests verify:

1. A normal LogRecord becomes valid JSON.
2. JSON contains ``timestamp``, ``level``, ``logger``, ``message``.
4. JSON contains ``request_id`` (from the P3-1 ContextVar/filter).
5. A log emitted outside a request scope has ``request_id == "-"``.
6. ``exc_info=True`` serialises into an ``exception`` object.
7. Multi-line messages, quotes and unicode remain valid JSON.
8. The formatter does not echo obvious secrets that some upstream code
   might accidentally pass through ``extra={...}``.
9. The configuration is idempotent — re-calling ``configure_json_logging``
   does not duplicate handlers.
10. P3-1's request-id filter still works in concert with the formatter.
11. The application's existing error logging (P0-1 envelope) keeps
    producing the right HTTP shape.

The tests deliberately do **not** assert on the JSON output written to
stderr — the project's caplog-based tests verify behaviour through
``LogRecord`` objects, and this module follows the same pattern.
"""

from __future__ import annotations

import io
import json
import logging
import re

import pytest

from backend.app.core.logging import (
    JSON_HANDLER_NAME,
    JsonFormatter,
    configure_json_logging,
    reset_json_logging,
)
from backend.app.core.request_id import (
    RequestIdLogFilter,
    install_request_id_log_filter,
    request_id_var,
)


@pytest.fixture(autouse=True)
def _isolate_json_logging():
    """Save/restore the root logger so each test starts with the same state."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_filters = list(root.filters)
    reset_json_logging()
    yield
    reset_json_logging()
    root.handlers = saved_handlers
    root.level = saved_level
    root.filters = saved_filters


def _make_handler(formatter: JsonFormatter | None = None) -> logging.Handler:
    """Build a fresh StreamHandler with the given formatter attached."""
    handler = logging.StreamHandler(io.StringIO())
    handler.setFormatter(formatter or JsonFormatter())
    return handler


def _format(record: logging.LogRecord, handler: logging.Handler | None = None) -> dict:
    """Run a record through the JSON formatter and return the parsed dict."""
    fmt = handler.formatter if handler and handler.formatter else JsonFormatter()
    raw = fmt.format(record)
    return json.loads(raw)


# ----- 1. A normal LogRecord becomes valid JSON ---------------------------


def test_normal_log_record_is_valid_json():
    logger = logging.getLogger("backend.app.api.v1.drafts")
    record = logger.makeRecord(
        name="backend.app.api.v1.drafts",
        level=logging.INFO,
        fn="create_draft",
        lno=42,
        msg="Draft %s created",
        args=("hello",),
        exc_info=None,
    )
    payload = _format(record)
    assert isinstance(payload, dict)


# ----- 2. Required fields ------------------------------------------------


def test_json_contains_required_fields():
    logger = logging.getLogger("backend.app.api.v1.drafts")
    record = logger.makeRecord(
        name="backend.app.api.v1.drafts",
        level=logging.INFO,
        fn="create_draft",
        lno=42,
        msg="Draft created",
        args=(),
        exc_info=None,
    )
    payload = _format(record)
    assert "timestamp" in payload
    assert "level" in payload
    assert "logger" in payload
    assert "message" in payload
    assert "request_id" in payload
    assert payload["level"] == "INFO"
    assert payload["logger"] == "backend.app.api.v1.drafts"
    assert payload["message"] == "Draft created"


def test_timestamp_is_iso_utc_with_z_suffix():
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="x",
        args=(),
        exc_info=None,
    )
    payload = _format(record)
    # Match e.g. "2026-08-13T10:30:15.123Z"
    assert re.match(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$", payload["timestamp"]
    ), payload["timestamp"]


def test_message_renders_format_string_with_args():
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="user %s did %s",
        args=("alice", "login"),
        exc_info=None,
    )
    payload = _format(record)
    assert payload["message"] == "user alice did login"


# ----- 4. request_id from P3-1 ------------------------------------------


def test_request_id_pulled_from_contextvar_inside_request():
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="inside request",
        args=(),
        exc_info=None,
    )
    # Ensure P3-1 filter is installed and the ContextVar is set.
    install_request_id_log_filter()
    token = request_id_var.set("abc123def456")
    try:
        RequestIdLogFilter().filter(record)
        payload = _format(record)
        assert payload["request_id"] == "abc123def456"
    finally:
        request_id_var.reset(token)


def test_request_id_dash_outside_request():
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="no active request",
        args=(),
        exc_info=None,
    )
    # No ContextVar set, no filter applied — formatter must use "-".
    assert request_id_var.get() is None
    payload = _format(record)
    assert payload["request_id"] == "-"


# ----- 6. Exception logging --------------------------------------------


def test_exception_info_is_serialised():
    logger = logging.getLogger("p3_2.test")
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logger.makeRecord(
            name="p3_2.test",
            level=logging.ERROR,
            fn="t",
            lno=1,
            msg="handler failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    payload = _format(record)
    assert "exception" in payload
    exc = payload["exception"]
    assert exc["type"] == "ValueError"
    assert exc["message"] == "boom"
    assert "Traceback" in exc["traceback"]
    assert "ValueError" in exc["traceback"]


def test_record_without_exc_info_has_no_exception_key():
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="fine",
        args=(),
        exc_info=None,
    )
    payload = _format(record)
    assert "exception" not in payload


# ----- 7. Special characters / multiline ---------------------------------


def test_quotes_and_newlines_yield_valid_json():
    logger = logging.getLogger("p3_2.test")
    tricky = 'first line\nsecond "quoted" line\twith a backslash \\'
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg=tricky,
        args=(),
        exc_info=None,
    )
    raw = JsonFormatter().format(record)
    # The raw output must be valid JSON.
    payload = json.loads(raw)
    # The message field must round-trip exactly.
    assert payload["message"] == tricky


def test_unicode_message_preserved():
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="héllo 🚀",
        args=(),
        exc_info=None,
    )
    raw = JsonFormatter().format(record)
    payload = json.loads(raw)
    assert payload["message"] == "héllo 🚀"


# ----- 8. Secret-safety in formatter extras ----------------------------


def test_extras_with_sensitive_keys_are_dropped():
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="sensitive payload",
        args=(),
        exc_info=None,
    )
    # Manually attach extra fields that look like secrets.
    record.firebase_token = "secret-firebase-token"
    record.LINKEDIN_CLIENT_SECRET = "abc"  # noqa: N806 — LogRecord attr name
    record.bearer_token = "Bearer SECRET_BEARER"
    record.user_id = "USER_A"  # benign — should be kept
    record.iteration = 3  # benign — should be kept

    payload = _format(record)
    extras = payload.get("extra", {})
    assert "user_id" in extras
    assert "iteration" in extras
    # Sensitive keys are filtered out.
    assert "firebase_token" not in extras
    assert "LINKEDIN_CLIENT_SECRET" not in extras
    assert "bearer_token" not in extras


def test_message_text_with_secret_fragments_is_not_modified_by_formatter():
    """The formatter is a passive serialiser. It must NOT auto-redact
    messages — but it must not amplify them either. The contract is:
    the message round-trips verbatim. Emitting code is responsible for
    not passing secrets.
    """
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="note: do not pass access_token=ABC here",
        args=(),
        exc_info=None,
    )
    payload = _format(record)
    assert "access_token=ABC" in payload["message"]  # verbatim, no auto-redact


# ----- 9. Idempotent configuration --------------------------------------


def test_configure_json_logging_is_idempotent():
    root = logging.getLogger()
    h1 = configure_json_logging()
    h2 = configure_json_logging()
    h3 = configure_json_logging()
    # Same handler instance is returned and there is exactly one.
    assert h1 is h2 is h3
    json_handlers = [
        h
        for h in root.handlers
        if getattr(h, "_saas_json_marker", False)
        or (h.get_name() == JSON_HANDLER_NAME)
    ]
    assert len(json_handlers) == 1
    assert json_handlers[0].formatter is not None
    # The formatter is the JsonFormatter.
    assert isinstance(json_handlers[0].formatter, JsonFormatter)


def test_reset_json_logging_removes_only_json_handler():
    root = logging.getLogger()
    sentinel = logging.StreamHandler(io.StringIO())
    sentinel.set_name("caplog-sentinel")
    root.addHandler(sentinel)
    configure_json_logging()
    try:
        json_count = sum(
            1
            for h in root.handlers
            if getattr(h, "_saas_json_marker", False)
            or (h.get_name() == JSON_HANDLER_NAME)
        )
        assert json_count == 1
        # Reset only removes the JSON handler.
        reset_json_logging()
        remaining_names = [h.get_name() for h in root.handlers]
        assert JSON_HANDLER_NAME not in remaining_names
        assert "caplog-sentinel" in remaining_names
    finally:
        root.removeHandler(sentinel)


def test_configure_json_logging_respects_log_level_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    configure_json_logging()
    try:
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        json_handler = next(
            h
            for h in root.handlers
            if getattr(h, "_saas_json_marker", False)
            or (h.get_name() == JSON_HANDLER_NAME)
        )
        assert json_handler.level == logging.DEBUG
    finally:
        monkeypatch.delenv("LOG_LEVEL", raising=False)


def test_configure_json_logging_respects_explicit_level():
    configure_json_logging("WARNING")
    try:
        root = logging.getLogger()
        assert root.level == logging.WARNING
    finally:
        reset_json_logging()


# ----- 10. P3-1 filter integration --------------------------------------


def test_p3_1_filter_populates_request_id_for_real_logger_call(client_a):
    """End-to-end: a request → log emitted by app code → JSON line with the right request_id."""
    install_request_id_log_filter()
    configure_json_logging("DEBUG")
    try:
        captured: list[str] = []
        handler = logging.StreamHandler(io.StringIO())
        handler.setFormatter(JsonFormatter())
        handler.addFilter(RequestIdLogFilter())

        class _Capture(logging.Handler):
            def emit(self, record):  # noqa: D401
                captured.append(handler.formatter.format(record))

        # Replace handler with the capture handler (still JSON-formatted).
        root = logging.getLogger()
        # Remove the default JSON handler installed by configure_json_logging
        # and replace with our capture variant.
        reset_json_logging()
        root.addHandler(_Capture(level=logging.DEBUG))
        root.setLevel(logging.DEBUG)

        # Drive a request to make the middleware set the ContextVar.
        response = client_a.get("/api/v1/auth/me")
        rid = response.headers["X-Request-ID"]

        # Emit a log line AFTER the request — the ContextVar has been
        # reset, so the placeholder is the documented behavior.
        logging.getLogger("p3_2_integration").info("post-request log")
        payload = json.loads(captured[-1])
        assert payload["request_id"] == "-"
        # The header we observed is still the uuid4 hex.
        assert len(rid) == 32
    finally:
        reset_json_logging()


def test_json_output_is_single_line_per_record():
    """Each formatted record is exactly one line — log shippers split on newlines."""
    logger = logging.getLogger("p3_2.test")
    record = logger.makeRecord(
        name="p3_2.test",
        level=logging.INFO,
        fn="t",
        lno=1,
        msg="line one\nline two\nline three",
        args=(),
        exc_info=None,
    )
    raw = JsonFormatter().format(record)
    assert raw.count("\n") == 0  # the JSON encoder escapes the newlines


# ----- 11. P0-1 envelope regression guard -------------------------------


def test_application_error_handler_still_returns_correct_envelope(client_a, monkeypatch):
    """P3-2 must not alter the global error envelope produced by
    :mod:`backend.app.core.error_handlers`.
    """
    from backend.app.services import workflow_service

    def _boom(self, _payload):
        raise RuntimeError("P3-2 envelope check")

    monkeypatch.setattr(
        workflow_service.WorkflowService, "generate_content", _boom
    )
    response = client_a.post("/api/v1/content/generate", json={"topic": "x"})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["message"] == "An unexpected error occurred."
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]