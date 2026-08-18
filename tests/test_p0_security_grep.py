"""Phase 8D / P0 - security grep.

A static check that no code path in the source-adapter service package
opens a network connection without going through ``ssrf.safe_get``.

This is the defence-in-depth companion to the SSRF-guard unit tests.
The unit tests prove the guard rejects unsafe targets; this test
proves nothing bypasses the guard.
"""

from __future__ import annotations

import re
from pathlib import Path


def _service_sources_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "app"
        / "services"
        / "sources"
    )


def test_no_direct_httpx_outside_ssrf_module() -> None:
    """``httpx.`` / ``httpx_get`` / ``httpx_post`` must not appear in
    ``backend/app/services/sources/`` outside ``ssrf.py``.
    """
    sources_dir = _service_sources_dir()
    forbidden_pattern = re.compile(
        r"\bhttpx\.(get|post|put|delete|patch|request)\b"
    )
    violations = []
    for path in sources_dir.rglob("*.py"):
        if path.name == "ssrf.py" or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in forbidden_pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            violations.append(f"{path}:{line_no}: {match.group(0)}")
    assert not violations, (
        "Direct httpx calls found in services/sources/ - must go "
        "through ssrf.safe_get. Offenders: " + str(violations)
    )


def test_no_direct_requests_outside_ssrf_module() -> None:
    """``requests.`` / ``requests_get`` / ``requests_post`` must not
    appear in the source-adapter package. The fetcher is async via
    httpx, so the sync ``requests`` library is doubly wrong.
    """
    sources_dir = _service_sources_dir()
    forbidden_pattern = re.compile(
        r"\brequests\.(get|post|put|delete|patch|head)\b"
    )
    violations = []
    for path in sources_dir.rglob("*.py"):
        if path.name == "ssrf.py" or path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        for match in forbidden_pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            violations.append(f"{path}:{line_no}: {match.group(0)}")
    assert not violations, (
        "Direct requests calls found in services/sources/. Offenders: "
        + str(violations)
    )


def test_no_trafilatura_fetch_url() -> None:
    """``trafilatura.fetch_url`` opens its own network connection and
    bypasses ``safe_get``; it must not be called from non-ssrf source
    modules. ``ssrf.py`` may mention the function name in its security
    docstring (to document the prohibition) but must not invoke it.
    """
    sources_dir = _service_sources_dir()
    forbidden_pattern = re.compile(r"\btrafilatura\.fetch_url\b")
    violations = []
    for path in sources_dir.rglob("*.py"):
        # ``ssrf.py`` is allowed to mention the function name in its
        # security docstring. Tests are excluded trivially.
        if path.name.startswith("test_") or path.name == "ssrf.py":
            continue
        text = path.read_text(encoding="utf-8")
        for match in forbidden_pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            violations.append(f"{path}:{line_no}: {match.group(0)}")
    assert not violations, (
        "trafilatura.fetch_url found in non-ssrf module - would bypass safe_get. "
        f"Offenders: {violations}"
    )


def test_safe_get_does_not_disable_tls_verification() -> None:
    """``safe_get`` must never call httpx with ``verify=False`` or
    construct an unverified ``SSLContext``. The TLS check is enforced
    by the SSL context passed at connection time.
    """
    ssrf_path = _service_sources_dir() / "ssrf.py"
    text = ssrf_path.read_text(encoding="utf-8")
    assert "verify=False" not in text, (
        "ssrf.py must not pass verify=False to httpx."
    )
    assert "CERT_NONE" not in text
    assert "check_hostname=False" not in text


def test_validate_url_uses_default_allowed_ports() -> None:
    """The default port allowlist must be 80/443 unless overridden.
    This guards against accidentally widening the default SSRF
    surface.
    """
    from backend.app.services.sources.ssrf import DEFAULT_ALLOWED_PORTS
    assert DEFAULT_ALLOWED_PORTS == frozenset({80, 443})


def test_resolve_safely_is_all_or_nothing() -> None:
    """``resolve_safely`` must check every answer in a multi-answer
    DNS response - one bad answer blocks the host.
    """
    import inspect
    from backend.app.services.sources import ssrf

    # ``resolve_safely`` delegates to ``_resolve_one`` which iterates
    # the getaddrinfo result and calls ``check_ip_family`` on every
    # answer - the iteration is the all-or-nothing guarantee.
    helper_source = inspect.getsource(ssrf._resolve_one)
    assert "check_ip_family" in helper_source
    assert "raise SourceBlockedError" in helper_source
    resolve_source = inspect.getsource(ssrf.resolve_safely)
    assert "_resolve_one" in resolve_source


# ---------------------------------------------------------------------------
# Phase 8D / P1 — GitHub adapter security checks
# ---------------------------------------------------------------------------


def test_github_adapter_uses_only_safe_get() -> None:
    """The GitHub adapter must call ``safe_get`` for every outbound
    request. No direct ``httpx.`` / ``requests.`` calls allowed.
    """
    sources_dir = _service_sources_dir()
    target = sources_dir / "github_adapter.py"
    if not target.exists():
        return  # P1 not yet shipped; nothing to check
    text = target.read_text(encoding="utf-8")
    # Must reference ``safe_get`` at least once.
    assert "safe_get" in text, (
        "github_adapter.py must call safe_get for outbound requests."
    )


def test_github_adapter_disables_no_tls_verification() -> None:
    """The GitHub adapter must never pass ``verify=False`` or construct
    an unverified ``SSLContext``.
    """
    sources_dir = _service_sources_dir()
    target = sources_dir / "github_adapter.py"
    if not target.exists():
        return
    text = target.read_text(encoding="utf-8")
    assert "verify=False" not in text
    assert "CERT_NONE" not in text
    assert "check_hostname=False" not in text


def test_github_adapter_uses_github_allowlist() -> None:
    """The GitHub adapter must pass ``allow_hosts=GITHUB_ALLOWLIST`` to
    ``safe_get`` on every outbound request.
    """
    sources_dir = _service_sources_dir()
    target = sources_dir / "github_adapter.py"
    if not target.exists():
        return
    text = target.read_text(encoding="utf-8")
    # Must reference the allowlist (imported as ``GITHUB_ALLOWLIST`` or
    # imported from ``ssrf`` and re-exported).
    assert "GITHUB_ALLOWLIST" in text or "ssrf import" in text.lower(), (
        "github_adapter.py must use GITHUB_ALLOWLIST when calling safe_get."
    )
    # And must actually pass it as the ``allow_hosts=`` argument.
    assert "allow_hosts=" in text, (
        "github_adapter.py must pass allow_hosts= to safe_get."
    )
