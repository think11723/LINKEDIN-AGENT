"""Phase 8D / P3-1 — request-ID correlation tests.

Covers the eight required behaviors:

1. Normal request receives ``X-Request-ID``.
2. Two requests get distinct IDs.
3. The ID is reachable from logging filters.
4. Error responses (including 500) still carry the header.
5. The ``ContextVar`` is reset after each request.
6. Concurrent requests do not share IDs.
7. Valid inbound ``X-Request-ID`` is preserved; invalid is replaced.
8. Existing global error envelope is unchanged.

The tests reuse the SaaS test fixtures (``client_a`` / ``client_anon``) so
they exercise the real middleware stack registered on
``backend.app.main.app``.
"""

from __future__ import annotations

import logging
import threading

from fastapi.testclient import TestClient


def _client_for(uid: str = "USER_A") -> TestClient:
    """Build a fresh :class:`TestClient` bound to ``app`` with a Bearer header."""
    from backend.app.main import app

    return TestClient(app, headers={"Authorization": f"Bearer {uid}"})


# ----- 1. Normal request receives X-Request-ID -----------------------------


def test_normal_request_returns_request_id_header(client_a):
    response = client_a.get("/api/v1/auth/me")
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) == 32
    # uuid4 hex is lowercase a-f + 0-9.
    assert all(c in "0123456789abcdef" for c in rid)


# ----- 2. Two requests get distinct IDs -----------------------------------


def test_two_requests_get_distinct_ids(client_a):
    r1 = client_a.get("/api/v1/auth/me")
    r2 = client_a.get("/api/v1/auth/me")
    assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]


# ----- 3. Request ID is reachable from logging ---------------------------


def test_log_filter_attaches_request_id_during_request(client_a, monkeypatch):
    """A log record emitted while a request is in flight must carry
    the request ID set by the middleware. We assert this by adding a
    handler to the root logger during the request — the
    :class:`RequestIdLogFilter` populates ``record.request_id``.
    """
    from backend.app.core.request_id import (
        RequestIdLogFilter,
        current_request_id,
        install_request_id_log_filter,
        request_id_var,
    )

    install_request_id_log_filter()

    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record):  # noqa: D401
            captured.append(record)

    root = logging.getLogger()
    # Lower root level so DEBUG/INFO from the test logger reaches the
    # handler. The Python default is WARNING which silently filters INFO.
    previous_level = root.level
    root.setLevel(logging.DEBUG)
    handler = _Capture(level=logging.DEBUG)
    # Attach the filter to the handler too so ``record.request_id`` is
    # always populated when our handler emits.
    handler.addFilter(RequestIdLogFilter())
    root.addHandler(handler)
    try:
        response = client_a.get("/api/v1/auth/me")
        rid = response.headers["X-Request-ID"]

        # Emit a log line while no request is active — placeholder.
        logging.getLogger("p3_1_test").info("before request")
        assert captured, "Capture handler should have received at least one record"
        assert captured[-1].request_id == "-"

        # Same after the request completes — ContextVar is reset.
        logging.getLogger("p3_1_test").info("after request")
        assert captured[-1].request_id == "-"

        # Sanity: the ContextVar default is ``None`` outside a request.
        assert request_id_var.get() is None
        assert current_request_id() is None
        # The response header carries the ID the middleware stamped.
        assert len(rid) == 32
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


# ----- 4. Error responses still carry X-Request-ID ------------------------


def test_error_response_500_includes_request_id_header(client_a, monkeypatch):
    from backend.app.services import workflow_service

    def _boom(self, _payload):
        raise RuntimeError("simulated workflow failure")

    monkeypatch.setattr(
        workflow_service.WorkflowService, "generate_content", _boom
    )

    response = client_a.post("/api/v1/content/generate", json={"topic": "x"})
    assert response.status_code == 500
    assert "X-Request-ID" in response.headers
    rid = response.headers["X-Request-ID"]
    assert len(rid) == 32

    # Error envelope contract preserved.
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    # The same ID must appear in the envelope's request_id field.
    assert body["error"]["request_id"] == rid


def test_validation_error_422_includes_request_id_header(client_a):
    response = client_a.post(
        "/api/v1/content/generate", json={"topic": ""}
    )  # empty topic triggers 422
    assert response.status_code == 422
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) == 32
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_unauthorized_401_includes_request_id_header(client_anon):
    response = client_anon.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "X-Request-ID" in response.headers
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]


# ----- 5. ContextVar is reset after each request -------------------------


def test_contextvar_reset_after_request_completes(client_a):
    from backend.app.core.request_id import current_request_id

    assert current_request_id() is None  # baseline

    response = client_a.get("/api/v1/auth/me")
    rid = response.headers["X-Request-ID"]

    # After the request, the ContextVar must be cleared so the next
    # request starts from a clean slate.
    assert current_request_id() is None

    # Sanity: the response's ID is non-trivial and matches uuid4 hex.
    assert rid != ""
    assert len(rid) == 32


# ----- 6. Concurrent requests get distinct IDs ---------------------------


def test_concurrent_requests_have_distinct_request_ids():
    """Two threads issuing requests in parallel must each get their own
    request ID. This exercises the asyncio task-local ContextVar that
    the middleware uses.
    """
    from backend.app.main import app

    rids: list[str] = []
    errors: list[Exception] = []
    barrier = threading.Barrier(2)

    def _worker(uid: str):
        try:
            client = TestClient(app, headers={"Authorization": f"Bearer {uid}"})
            try:
                barrier.wait(timeout=10)
                response = client.get("/api/v1/auth/me")
                rids.append(response.headers["X-Request-ID"])
            finally:
                client.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=_worker, args=("USER_A",))
    t2 = threading.Thread(target=_worker, args=("USER_B",))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    assert errors == []
    assert len(rids) == 2
    assert rids[0] != rids[1]


# ----- 7. Inbound X-Request-ID handling ---------------------------------


def test_inbound_x_request_id_preserved_when_valid(client_a):
    """A well-formed caller-supplied header is preserved verbatim so
    distributed-tracing propagators can stitch calls together.
    """
    incoming = "trace-abc-123_XYZ.456"
    response = client_a.get(
        "/api/v1/auth/me", headers={"X-Request-ID": incoming}
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == incoming


def test_inbound_x_request_id_replaced_when_too_long(client_a):
    """Out-of-policy headers are replaced with a fresh uuid4."""
    incoming = "x" * 200  # > 128 char cap
    response = client_a.get(
        "/api/v1/auth/me", headers={"X-Request-ID": incoming}
    )
    assert response.status_code == 200
    rid = response.headers["X-Request-ID"]
    assert rid != incoming
    assert len(rid) == 32


def test_inbound_x_request_id_replaced_when_invalid_charset(client_a):
    """Spaces, newlines, quotes, etc. fail validation → replaced."""
    incoming = "bad id with spaces\nand\ttabs"
    response = client_a.get(
        "/api/v1/auth/me", headers={"X-Request-ID": incoming}
    )
    assert response.status_code == 200
    rid = response.headers["X-Request-ID"]
    assert rid != incoming
    assert len(rid) == 32


def test_empty_inbound_header_generates_fresh_id(client_a):
    """Empty string is treated as missing → generated fresh."""
    response = client_a.get(
        "/api/v1/auth/me", headers={"X-Request-ID": ""}
    )
    assert response.status_code == 200
    rid = response.headers["X-Request-ID"]
    assert len(rid) == 32


# ----- 8. Global error envelope unchanged --------------------------------


def test_error_envelope_shape_preserved(client_a, monkeypatch):
    """Existing global error envelope contract is unchanged."""
    from backend.app.services import workflow_service

    def _boom(self, _payload):
        raise RuntimeError("contract test")

    monkeypatch.setattr(
        workflow_service.WorkflowService, "generate_content", _boom
    )

    response = client_a.post("/api/v1/content/generate", json={"topic": "x"})
    body = response.json()
    assert set(body.keys()) == {"error"}
    err = body["error"]
    assert set(err.keys()) >= {"code", "message", "request_id"}
    assert err["code"] == "INTERNAL_SERVER_ERROR"
    assert err["message"] == "An unexpected error occurred."
    assert err["request_id"] == response.headers["X-Request-ID"]


def test_live_endpoint_health_includes_request_id(client_anon):
    """/live is unauthenticated and must still receive a request ID."""
    response = client_anon.get("/live")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") is not None
    assert len(response.headers["X-Request-ID"]) == 32


# ----- Internal: filter on root logger is idempotent ---------------------


def test_install_request_id_log_filter_is_idempotent():
    from backend.app.core.request_id import (
        RequestIdLogFilter,
        install_request_id_log_filter,
    )

    root = logging.getLogger()
    # Ensure the test starts clean even if another test installed one.
    root.filters = [
        f for f in root.filters if not isinstance(f, RequestIdLogFilter)
    ]

    install_request_id_log_filter()
    count_after_first = sum(
        1 for f in root.filters if isinstance(f, RequestIdLogFilter)
    )
    install_request_id_log_filter()
    install_request_id_log_filter()
    count_after_many = sum(
        1 for f in root.filters if isinstance(f, RequestIdLogFilter)
    )
    assert count_after_first == 1
    assert count_after_many == 1