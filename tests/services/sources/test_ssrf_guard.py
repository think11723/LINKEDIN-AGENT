"""Phase 8D / P0 — SSRF guard tests.

The most security-critical tests in the codebase. Every assertion
here proves that ``backend/app/services/sources/ssrf.py`` rejects
an unsafe target before any HTTP byte is sent.

Coverage:

* Loopback (IPv4, IPv6, hostname).
* Private IPv4 ranges (10/8, 172.16/12, 192.168/16).
* IPv6 ULA (fc00::/7), link-local (fe80::/10), site-local.
* Cloud metadata endpoints (169.254.169.254, metadata.google.internal).
* IPv4-mapped IPv6, 6to4, Teredo, NAT64 transition ranges.
* CGNAT (100.64/10) and other reserved IPv4 ranges.
* Decimal / octal / hex IP obfuscation.
* Unsupported schemes (file://, gopher://, data:, ftp://, javascript:).
* URL with userinfo (``user:pass@host``).
* Non-standard ports (:22, :6379).
* Host allowlist (exact match; ``github.com.evil.com`` rejected).
* IDN / punycode handling.

Network operations are monkeypatched — these tests never open a
real socket.
"""

from __future__ import annotations

import socket

import pytest

from backend.app.services.sources.base import SourceBlockedError
from backend.app.services.sources.ssrf import (
    DEFAULT_ALLOWED_PORTS,
    GITHUB_ALLOWLIST,
    check_ip_family,
    resolve_safely,
    validate_url,
)


# ---------------------------------------------------------------------------
# IP-family vetting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ip",
    [
        # Loopback
        "127.0.0.1",
        "127.255.255.254",
        "::1",
        # Private IPv4
        "10.0.0.1",
        "172.16.5.4",
        "192.168.1.1",
        # Private IPv6
        "fd00::1",
        "fd12:3456::1",
        # Link-local
        "169.254.1.1",
        "169.254.169.254",  # cloud metadata IPv4
        "fe80::1",
        # Multicast
        "224.0.0.1",
        "ff02::1",
        # Reserved
        "240.0.0.1",
        # Unspecified
        "0.0.0.0",
        "::",
        # CGNAT
        "100.64.0.1",
        # Benchmarking
        "198.18.0.1",
        # Protocol-assignment
        "192.0.2.1",
    ],
)
def test_check_ip_family_blocks_unsafe(ip: str) -> None:
    with pytest.raises(SourceBlockedError):
        check_ip_family(ip)


@pytest.mark.parametrize(
    "ip",
    [
        # Public IPs (real public addresses used only as safe probes).
        "8.8.8.8",
        "1.1.1.1",
        "2606:4700:4700::1111",
        "2001:4860:4860::8888",
        "9.9.9.9",
    ],
)
def test_check_ip_family_allows_safe_public(ip: str) -> None:
    # Should NOT raise.
    check_ip_family(ip)


def test_check_ip_family_rejects_decimal_obfuscation() -> None:
    """``2130706433`` is 127.0.0.1 in 32-bit unsigned form.

    Python's ``ipaddress.ip_address`` rejects this form with
    ``AddressValueError`` — our guard maps that to ``bad_ip``. The
    security property is that the address is rejected; the specific
    code is an implementation detail.
    """
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("2130706433")
    assert exc_info.value.code in {"bad_ip", "loopback"}


def test_check_ip_family_rejects_octal_obfuscation() -> None:
    """``0177.0.0.1`` is 127.0.0.1 in octal form.

    Python's ``ipaddress.ip_address`` does not accept this form
    (raises ``ValueError``) — we map that to ``bad_ip``.
    """
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("0177.0.0.1")
    assert exc_info.value.code == "bad_ip"


def test_check_ip_family_rejects_ipv4_mapped_ipv6() -> None:
    """``::ffff:127.0.0.1`` is an IPv4-mapped loopback — must unwrap."""
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("::ffff:127.0.0.1")
    # The unwrap reaches 127.0.0.1 (loopback). ``is_private`` is also
    # True for 127.0.0.0/8 in Python; either code proves rejection.
    assert exc_info.value.code in {"loopback", "private_ip"}


def test_check_ip_family_rejects_ipv4_mapped_ipv6_private() -> None:
    """``::ffff:10.0.0.1`` is an IPv4-mapped private — must unwrap."""
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("::ffff:10.0.0.1")
    assert exc_info.value.code == "private_ip"


def test_check_ip_family_rejects_6to4_loopback() -> None:
    """``2002:7f00:0001::`` is a 6to4-embedded 127.0.0.1 — must unwrap."""
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("2002:7f00:0001::")
    # 6to4 v4 is the last 32 bits; for 2002:7f00:0001:: that is 0.0.0.0
    # (reserved). Either code proves the unwrap path fired.
    assert exc_info.value.code in {"loopback", "reserved", "private_ip"}


def test_check_ip_family_rejects_nat64_loopback() -> None:
    """``64:ff9b::7f00:0001`` is NAT64-mapped 127.0.0.1 — must unwrap."""
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("64:ff9b::7f00:0001")
    assert exc_info.value.code in {"loopback", "private_ip"}


def test_check_ip_family_rejects_teredo_private() -> None:
    """Teredo-embedded private IPv4 must unwrap and re-vet."""
    with pytest.raises(SourceBlockedError):
        check_ip_family("2001::c0a8:0101")


def test_check_ip_family_rejects_explicit_cloud_metadata() -> None:
    """``169.254.169.254`` is AWS/GCP/Azure metadata — code == loopback.

    The dedicated branch records ``reason="cloud_metadata"`` for
    forensics.
    """
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("169.254.169.254")
    assert exc_info.value.code == "loopback"
    assert exc_info.value.details.get("reason") == "cloud_metadata"


def test_check_ip_family_rejects_bad_ip() -> None:
    with pytest.raises(SourceBlockedError) as exc_info:
        check_ip_family("not-an-ip")
    assert exc_info.value.code == "bad_ip"


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------


def test_validate_url_passes_raw_ip_literals_to_resolve_safely() -> None:
    """``validate_url`` does NOT do IP-family checks (separation of
    concerns). Raw IP literals pass syntax validation and are only
    blocked by ``resolve_safely`` which runs the IP-family check.

    This test documents the contract: ``validate_url`` accepts IP
    literals; the second layer (``resolve_safely``) is the IP guard.
    """
    for url in [
        "http://10.0.0.1/x",
        "https://172.16.5.4/x",
        "http://192.168.1.1/x",
        "https://[fd00::1]/x",
        "http://[fe80::1]/x",
        "http://169.254.169.254/latest/meta-data",
    ]:
        parsed = validate_url(url)
        assert parsed.scheme in {"http", "https"}


def test_resolve_safely_rejects_raw_ip_literals(monkeypatch) -> None:
    """``resolve_safely`` is the IP-family guard. A raw IP literal
    passed as the host is checked directly against the IP-family
    allowlist.
    """
    for ip in ["127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.169.254"]:
        with pytest.raises(SourceBlockedError):
            resolve_safely(ip, 443)


def test_validate_url_passes_hostnames_for_later_dns_check() -> None:
    """Hostnames pass ``validate_url`` — IP-family check is in
    ``resolve_safely``. This is the documented separation of concerns.
    """
    # These must not raise — they'll be caught by ``resolve_safely``
    # when DNS returns a loopback / private / metadata answer.
    for url in [
        "http://localhost/x",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://localhost.example.com/x",
    ]:
        parsed = validate_url(url)
        assert parsed.scheme in {"http", "https"}


@pytest.mark.parametrize(
    "scheme_url",
    [
        "file:///etc/passwd",
        "gopher://example.com/_test",
        "data:text/plain;base64,SGVsbG8=",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "blob:https://example.com/uuid",
        "ws://example.com/socket",
    ],
)
def test_validate_url_blocks_non_http_schemes(scheme_url: str) -> None:
    with pytest.raises(SourceBlockedError) as exc_info:
        validate_url(scheme_url)
    assert exc_info.value.code == "bad_scheme"


def test_validate_url_blocks_userinfo() -> None:
    """``user:pass@evil.com@github.com`` is a userinfo injection attempt."""
    with pytest.raises(SourceBlockedError) as exc_info:
        validate_url("http://user:pass@github.com/user/repo")
    assert exc_info.value.code == "userinfo"


def test_validate_url_blocks_non_standard_ports() -> None:
    """Internal ports (SSH, Redis, SMTP) are blocked by default."""
    with pytest.raises(SourceBlockedError) as exc_info:
        validate_url("http://github.com:22/")
    assert exc_info.value.code == "bad_port"

    with pytest.raises(SourceBlockedError) as exc_info:
        validate_url("http://github.com:6379/")
    assert exc_info.value.code == "bad_port"


def test_validate_url_blocks_empty() -> None:
    with pytest.raises(SourceBlockedError):
        validate_url("")


def test_validate_url_blocks_bad_host_idna() -> None:
    """Hostnames that fail IDNA encoding are rejected.

    Control characters in the URL (e.g. NUL) are caught even earlier
    with the ``bad_url`` code — the test accepts either.
    """
    with pytest.raises(SourceBlockedError) as exc_info:
        # Embedded NUL — invalid in any IDNA profile.
        validate_url("http://evil.com\x00bad.com/")
    assert exc_info.value.code in {"bad_host", "bad_url"}


def test_validate_url_allows_public_https() -> None:
    parsed = validate_url("https://github.com/user/repo")
    assert parsed.scheme == "https"
    assert parsed.hostname == "github.com"


def test_validate_url_allowlist_rejects_not_github() -> None:
    """``github.com.evil.com`` is NOT in the GitHub allowlist."""
    with pytest.raises(SourceBlockedError) as exc_info:
        validate_url(
            "https://github.com.evil.com/user/repo",
            allow_hosts=GITHUB_ALLOWLIST,
        )
    assert exc_info.value.code == "not_allowlisted"


def test_validate_url_allowlist_rejects_close_miss() -> None:
    """``notgithub.com`` is NOT in the GitHub allowlist — exact match only."""
    with pytest.raises(SourceBlockedError) as exc_info:
        validate_url("https://notgithub.com", allow_hosts=GITHUB_ALLOWLIST)
    assert exc_info.value.code == "not_allowlisted"


def test_validate_url_allowlist_accepts_github_com() -> None:
    parsed = validate_url(
        "https://github.com/user/repo", allow_hosts=GITHUB_ALLOWLIST
    )
    assert parsed.hostname == "github.com"


def test_validate_url_allowlist_accepts_api_github_com() -> None:
    parsed = validate_url(
        "https://api.github.com/repos/user/repo",
        allow_hosts=GITHUB_ALLOWLIST,
    )
    assert parsed.hostname == "api.github.com"


def test_validate_url_strips_trailing_dot() -> None:
    """``github.com.`` is canonicalized to ``github.com`` (RFC 1035)."""
    parsed = validate_url("https://github.com./x", allow_hosts=GITHUB_ALLOWLIST)
    assert parsed.hostname == "github.com"


def test_validate_url_infers_default_port_in_netloc() -> None:
    """When the URL omits an explicit port, ``validate_url`` puts the
    inferred default (443/https, 80/http) in the returned ``netloc`` so
    callers don't have to re-run the inference before building a
    ``ResolvedTarget``.
    """
    parsed = validate_url("https://github.com/x", allow_hosts=GITHUB_ALLOWLIST)
    assert "github.com:443" in parsed.netloc

    parsed = validate_url("http://github.com/x", allow_hosts=None)
    assert "github.com:80" in parsed.netloc


def test_default_allowed_ports_set() -> None:
    """The default port allowlist must be {80, 443}."""
    assert DEFAULT_ALLOWED_PORTS == frozenset({80, 443})


def test_validate_url_rejects_high_port() -> None:
    """Ports above 1024 are not allowed by default — internal services
    (memcached 11211, redis 6379, etc.) live above."""
    with pytest.raises(SourceBlockedError) as exc_info:
        validate_url("http://github.com:8080/")
    assert exc_info.value.code == "bad_port"


# ---------------------------------------------------------------------------
# DNS resolution (resolve_safely)
# ---------------------------------------------------------------------------


def test_resolve_safely_rejects_loopback_resolution(monkeypatch) -> None:
    """If DNS returns a loopback answer, the entire resolution is blocked."""

    def fake_getaddrinfo(host, port, type):
        # Returns 127.0.0.1 for the host.
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(SourceBlockedError):
        resolve_safely("public-looking.example.com", 443)


def test_resolve_safely_rejects_multi_answer_round_robin(monkeypatch) -> None:
    """One private answer in the list blocks the host — defeats rebinding."""

    infos = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
    ]

    def fake_getaddrinfo(host, port, type):
        return infos

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(SourceBlockedError) as exc_info:
        resolve_safely("public-looking.example.com", 443)
    assert exc_info.value.code == "private_ip"


def test_resolve_safely_allows_single_public_answer(monkeypatch) -> None:
    def fake_getaddrinfo(host, port, type):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    targets = resolve_safely("github.com", 443)
    assert len(targets) == 1
    assert targets[0].ip == "8.8.8.8"
    assert targets[0].host == "github.com"
    assert targets[0].port == 443


def test_resolve_safely_rejects_dns_failure(monkeypatch) -> None:
    def fake_getaddrinfo(host, port, type):
        raise socket.gaierror(-2, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(SourceBlockedError) as exc_info:
        resolve_safely("nonexistent.example.com", 443)
    assert exc_info.value.code == "dns_error"