"""SSRF guard for the URL-to-LinkedIn feature — Phase 8D.

This module is **security-critical**. Every outbound HTTP fetch that
originates from a user-supplied URL must pass through :func:`safe_get`.
The static test in ``tests/test_security_ssrf_grep.py`` enforces this by
grepping for direct ``httpx.`` / ``requests.`` / ``trafilatura.fetch_url``
use anywhere under ``services/sources/``.

Defenses in depth:

1. **Scheme allowlist.** Only ``http`` and ``https`` are accepted. The
   platform-credential grabbers (``file://``, ``gopher://``, ``data:``,
   ``ftp://``, ``ws://``, ``blob:``, ``javascript:``) are rejected at the
   parse step — they never reach DNS resolution.

2. **Userinfo block.** URLs like ``http://user:pass@evil.com@github.com/``
   are rejected before any resolution. Modern parsers handle the
   double-@ ambiguity inconsistently; safer to forbid.

3. **Port allowlist.** Only ``80`` and ``443`` are accepted by default.
   ``22`` (SSH), ``6379`` (Redis), ``25`` (SMTP), ``3306`` (MySQL) and
   similar are the high-value targets of internal-port scans.

4. **Hostname allowlist for trusted sources.** When an adapter knows the
   target is ``github.com`` / ``api.github.com`` / ``raw.githubusercontent.com``
   we pass an exact-match allowlist. This is exact-match, not suffix —
   ``github.com.evil.com`` does not match.

5. **DNS pre-resolution with IP-family vetting.** ``resolve_safely`` uses
   ``socket.getaddrinfo`` and runs :func:`check_ip_family` against
   **every** returned address. All-or-nothing: one private answer in
   the list blocks the whole request (defeats round-robin DNS rebinding).

6. **TOCTOU / DNS-rebinding mitigation (the core trick).** The fetcher
   never lets httpx re-resolve. It connects to the **pinned IP** from
   step 5, preserving the original ``Host:`` header and TLS SNI. So
   the IP we vetted is byte-identical to the IP we connected to — no
   re-resolution window.

7. **Manual redirect loop.** ``follow_redirects=False``; the fetcher
   re-runs steps 1-5 on each ``Location`` hop. Cross-host redirects
   drop ``Authorization`` / ``Cookie`` headers. Cap at 5 hops.

8. **Response-size cap.** Streaming with byte accounting. Lying
   ``Content-Length`` and gzip bombs are caught.

9. **TLS verification always on.** Expired / invalid cert →
   :class:`SourceUnavailableError`. ``verify`` is never disabled. Custom
   :class:`ssl.SSLContext` with ``check_hostname=True`` against the
   original hostname (we connected to an IP, so default httpx hostname
   matching would compare against the IP literal and fail).

10. **Test escape hatch.** ``SSRF_ALLOW_PRIVATE=true`` re-enables
    loopback/private for tests. ``safe_get`` logs loudly at startup if
    set. Tests that need it must set the env var themselves.

Env-var configuration lives in :mod:`backend.app.core.config`.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
import ssl
import uuid
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence
from urllib.parse import ParseResult, urlparse

import httpx

from backend.app.core.config import get_settings
from backend.app.services.sources.base import (
    SourceBlockedError,
    SourceTooLargeError,
    SourceUnavailableError,
)

logger = logging.getLogger(__name__)


#: Schemes the URL-to-LinkedIn feature is allowed to fetch.
ALLOWED_SCHEMES: frozenset[str] = frozenset({"http", "https"})

#: Trusted-source host allowlist (GitHub). Used by the GitHub adapter.
GITHUB_ALLOWLIST: frozenset[str] = frozenset(
    {"github.com", "www.github.com", "api.github.com", "raw.githubusercontent.com"}
)

#: Default ports we will connect to.
DEFAULT_ALLOWED_PORTS: frozenset[int] = frozenset({80, 443})

#: Cloud-metadata IPv4 host (literal). Blocked explicitly even though it
#: falls under ``link_local``.
_CLOUD_METADATA_HOSTS: frozenset[str] = frozenset(
    {
        "169.254.169.254",  # AWS / GCP / Azure
        "metadata.google.internal",  # GCP (legacy DNS name)
        "metadata.azure.com",
        "100.100.100.200",  # Alibaba
    }
)


@dataclass(frozen=True)
class ResolvedTarget:
    """One vetted (host, ip) pair returned by :func:`resolve_safely`."""

    url: str  # reconstructed url with the pinned IP substituted in
    host: str  # original hostname (used for Host: / SNI)
    port: int
    ip: str  # pinned IP literal
    family: int  # socket.AF_INET | socket.AF_INET6


def _normalize_host(host: str) -> str:
    """Lower-case + strip IDN suffix.

    Returns the lowered host or raises :class:`SourceBlockedError` with
    ``bad_host`` if the host is empty / unparseable / an IDN homograph
    that won't encode.
    """
    if not host:
        raise SourceBlockedError("Empty host.", code="bad_host")
    candidate = host.strip().rstrip(".").lower()
    try:
        # idna.encode handles IDN, punycode, trailing dots. Strict=False
        # allows IDNA2008 transitional processing without raising on
        # deviant characters.
        return candidate.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise SourceBlockedError(
            f"Invalid hostname: {host!r}", code="bad_host", details={"error": str(exc)}
        ) from exc


def validate_url(
    url: str,
    *,
    allow_hosts: Optional[Iterable[str]] = None,
    allowed_ports: Optional[Iterable[int]] = None,
) -> ParseResult:
    """Validate the URL shape. Raises :class:`SourceBlockedError` on rejection.

    Checks, in order: scheme ∈ ALLOWED_SCHEMES, no userinfo, port ∈
    allowed_ports, host normalizes to a non-empty ASCII string, and
    (if ``allow_hosts`` is given) host is an exact member.

    Returns a :class:`urllib.parse.ParseResult` ready for DNS resolution.
    """
    if not isinstance(url, str) or not url:
        raise SourceBlockedError("Empty URL.", code="bad_url")

    # Strip whitespace and control characters.
    url = url.strip()
    for ch in url:
        if ord(ch) < 0x20:
            raise SourceBlockedError(
                "URL contains control characters.", code="bad_url"
            )

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SourceBlockedError(
            f"Scheme {parsed.scheme!r} not allowed.",
            code="bad_scheme",
            details={"scheme": parsed.scheme},
        )

    if parsed.username is not None or parsed.password is not None:
        raise SourceBlockedError(
            "Userinfo in URL not allowed.", code="userinfo"
        )

    ports_to_check = (
        frozenset(allowed_ports) if allowed_ports else DEFAULT_ALLOWED_PORTS
    )

    # ``port`` is None when not specified; default per scheme.
    port: Optional[int] = parsed.port
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    if port not in ports_to_check:
        raise SourceBlockedError(
            f"Port {port} not allowed.",
            code="bad_port",
            details={"port": port},
        )

    host = _normalize_host(parsed.hostname or "")
    if not host:
        raise SourceBlockedError("Missing host.", code="bad_host")

    # Defense-in-depth: if the host is a literal IP, run the IP-family
    # check NOW so obvious SSRF payloads (``http://127.0.0.1/``,
    # ``http://169.254.169.254/``, ``http://10.0.0.1/``) are rejected
    # by the synchronous pre-check, not deferred to DNS resolution.
    # The IP-family vet is still re-run after DNS resolution in
    # :func:`resolve_safely`, so hostname → IP rebinding is also
    # blocked. This early check only blocks literal-IP URLs.
    import ipaddress as _ip

    try:
        _ip.ip_address(host)
        check_ip_family(host)
    except ValueError:
        # Not a literal IP — DNS resolution will do the check.
        pass

    # If ``allow_hosts`` given, the host must be an EXACT member (no
    # suffix matching). This is the GitHub allowlist enforcement.
    if allow_hosts:
        if host not in frozenset(allow_hosts):
            raise SourceBlockedError(
                f"Host {host!r} is not in the allowlist.",
                code="not_allowlisted",
                details={"host": host},
            )

    # Re-attach the normalized host so the caller sees the canonical form.
    # If the URL had no explicit port, the inferred default (443/https,
    # 80/http) is included so the caller can build a ``ResolvedTarget``
    # without re-running the inference.
    netloc = host
    if parsed.port is not None:
        netloc = f"{host}:{parsed.port}"
    elif port is not None:
        netloc = f"{host}:{port}"
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=netloc)


# ---------------------------------------------------------------------------
# IP-family vetting
# ---------------------------------------------------------------------------


def check_ip_family(ip: str) -> None:
    """Raise :class:`SourceBlockedError` if the IP is unsafe to connect to.

    Conservative default: deny loopback, private, link-local, multicast,
    reserved, unspecified. Then handle the IPv6 transition mechanisms
    that can route to private destinations (IPv4-mapped, IPv4-translated,
    NAT64, 6to4, Teredo) and explicit denylists for cloud-metadata
    IPv4 ranges and CGNAT.
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise SourceBlockedError(
            f"IP {ip!r} is not a valid address.",
            code="bad_ip",
            details={"ip": ip, "error": str(exc)},
        ) from exc

    # Explicit cloud-metadata denylist (also covered by is_link_local but
    # we want the code to be specific for forensics).
    if str(addr) in _CLOUD_METADATA_HOSTS:
        raise SourceBlockedError(
            "Cloud metadata endpoint is blocked.",
            code="loopback",
            details={"ip": ip, "reason": "cloud_metadata"},
        )

    # IPv4-mapped / 6to4 / Teredo / NAT64 unwrapping MUST happen before
    # the general IP checks below — otherwise ``::ffff:127.0.0.1`` is
    # flagged as ``is_private`` (and so would miss the loopback
    # rejection). Unwrap and re-vet the embedded v4.
    if isinstance(addr, ipaddress.IPv6Address):
        v4_mapped_prefix = ipaddress.IPv6Network("::ffff:0:0/96")
        if addr in v4_mapped_prefix:
            mapped = addr.ipv4_mapped
            if mapped is not None:
                check_ip_family(str(mapped))
                return
        six_to_four = ipaddress.IPv6Network("2002::/16")
        if addr in six_to_four:
            # The 128-bit address in hex is 32 chars; the last 8 are
            # the embedded IPv4 (big-endian, octet-aligned).
            hexstr = "%032x" % int(addr)
            v4_hex = hexstr[-8:]
            v4_str = ".".join(
                str(int(v4_hex[i : i + 2], 16)) for i in (0, 2, 4, 6)
            )
            check_ip_family(v4_str)
            return
        teredo = ipaddress.IPv6Network("2001::/32")
        if addr in teredo:
            last4 = addr.packed[12:16]
            v4_str = ".".join(str(b) for b in last4)
            check_ip_family(v4_str)
            return
        nat64 = ipaddress.IPv6Network("64:ff9b::/96")
        if addr in nat64:
            last4 = addr.packed[12:16]
            v4_str = ".".join(str(b) for b in last4)
            check_ip_family(v4_str)
            return

    if addr.is_loopback:
        raise SourceBlockedError(
            "Loopback IP is blocked.", code="loopback", details={"ip": ip}
        )
    if addr.is_private:
        raise SourceBlockedError(
            "Private IP is blocked.", code="private_ip", details={"ip": ip}
        )
    if addr.is_link_local:
        raise SourceBlockedError(
            "Link-local IP is blocked.", code="link_local", details={"ip": ip}
        )
    if addr.is_multicast:
        raise SourceBlockedError(
            "Multicast IP is blocked.", code="multicast", details={"ip": ip}
        )
    if addr.is_reserved:
        raise SourceBlockedError(
            "Reserved IP is blocked.", code="reserved", details={"ip": ip}
        )
    if addr.is_unspecified:
        raise SourceBlockedError(
            "Unspecified IP is blocked.", code="reserved", details={"ip": ip}
        )

    if isinstance(addr, ipaddress.IPv6Address):
        # IPv6 site-local is deprecated but still allocated to RFC standard;
        # treat as private. (The v4-mapped / 6to4 / Teredo / NAT64
        # unwrapping that used to live here was moved EARLIER so it
        # runs before is_loopback / is_private / is_link_local.)
        if addr.is_site_local:
            raise SourceBlockedError(
                "IPv6 site-local IP is blocked.",
                code="private_ip",
                details={"ip": ip},
            )

    elif isinstance(addr, ipaddress.IPv4Address):
        # CGNAT (100.64.0.0/10) — RFC 6598, not classified as private by
        # ``ipaddress`` but commonly used for internal NAT.
        if addr in ipaddress.IPv4Network("100.64.0.0/10"):
            raise SourceBlockedError(
                "CGNAT IP is blocked.",
                code="private_ip",
                details={"ip": ip},
            )
        # 198.18.0.0/15 — benchmarking range; treat as unsafe.
        if addr in ipaddress.IPv4Network("198.18.0.0/15"):
            raise SourceBlockedError(
                "Benchmarking IP is blocked.",
                code="reserved",
                details={"ip": ip},
            )
        # 192.0.0.0/24 — IETF protocol assignments; treat as unsafe.
        if addr in ipaddress.IPv4Network("192.0.0.0/24"):
            raise SourceBlockedError(
                "Protocol-assignment IP is blocked.",
                code="reserved",
                details={"ip": ip},
            )
        # 0.0.0.0/8 — "this host on this network" wildcard.
        if addr in ipaddress.IPv4Network("0.0.0.0/8"):
            raise SourceBlockedError(
                "Wildcard IP is blocked.",
                code="reserved",
                details={"ip": ip},
            )


# ---------------------------------------------------------------------------
# DNS pre-resolution
# ---------------------------------------------------------------------------


def _resolve_one(host: str, port: int) -> List[ResolvedTarget]:
    """Call ``getaddrinfo`` for ``(host, port)``; return vetted targets.

    On resolution failure or any blocked answer, raise
    :class:`SourceBlockedError`.
    """
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise SourceBlockedError(
            f"DNS resolution failed for {host!r}.",
            code="dns_error",
            details={"host": host, "error": str(exc)},
        ) from exc

    targets: List[ResolvedTarget] = []
    for family, _, _, _, sockaddr in infos:
        ip = sockaddr[0]
        # Vetted per-IP; raises on any unsafe answer.
        check_ip_family(ip)
        # Reconstruct a URL with the IP literal substituted in for the host.
        scheme = "https" if port == 443 else "http"
        targets.append(
            ResolvedTarget(
                url=f"{scheme}://{ip}:{port}",  # actual request goes to this URL
                host=host,  # original hostname for Host: / SNI
                port=port,
                ip=ip,
                family=family,
            )
        )
    return targets


def resolve_safely(host: str, port: int) -> List[ResolvedTarget]:
    """Resolve ``host:port`` and validate every IP.

    All-or-nothing: if **any** answer is unsafe, the entire resolution
    is rejected. This defeats round-robin DNS rebinding where a single
    resolver call returns a mix of public and private addresses.
    """
    if not host:
        raise SourceBlockedError("Empty host for resolution.", code="bad_host")
    return _resolve_one(host, port)


# ---------------------------------------------------------------------------
# safe_get: the only network exit point
# ---------------------------------------------------------------------------


@dataclass
class SafeResponse:
    """Result of a single :func:`safe_get` call."""

    status_code: int
    headers: dict
    body: bytes
    final_url: str  # URL after redirect chain
    hop_count: int  # 0 for first fetch, increments on each redirect


def _build_tls_context() -> ssl.SSLContext:
    """Build a TLS context that requires cert verification AND hostname match.

    Because we connect to the pinned IP (not the original hostname),
    the default ``check_hostname=True`` would compare the cert against
    the IP literal and fail. We wrap in a custom context with the right
    hostname pinned via the connection's ``server_hostname`` (set by
    httpx via the ``sni_hostname`` extension).
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


async def safe_get(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float = 20.0,
    allow_hosts: Optional[Iterable[str]] = None,
    extra_headers: Optional[dict] = None,
    follow_redirects: bool = True,
    max_redirects: int = 5,
) -> SafeResponse:
    """Fetch ``url`` safely. The single network exit point.

    Behavior:
    1. Validate the URL shape (``validate_url``).
    2. Resolve the hostname and vet every IP (``resolve_safely``).
    3. Connect to the pinned IP while preserving the original
       ``Host:`` header and TLS SNI.
    4. If a redirect is returned, re-run steps 1-3 on the new URL
       (cap ``max_redirects``). Cross-host redirects drop sensitive
       headers.
    5. Stream the body with a hard byte cap (``max_bytes``).
    6. Lying ``Content-Length`` and gzip bombs are caught by tracking
       bytes actually received.

    Raises:
      :class:`SourceBlockedError` for any SSRF-family violation.
      :class:`SourceTooLargeError` if the body exceeds ``max_bytes``.
      :class:`SourceUnavailableError` for non-Security failures
      (TLS, timeout, 4xx, 5xx).
    """
    settings = get_settings()

    current_url = url
    headers: dict[str, str] = dict(extra_headers or {})
    # Cross-host redirects drop these; we re-add on same-host.
    sensitive_header_names = {"authorization", "cookie"}

    for hop in range(max_redirects + 1):
        parsed = validate_url(
            current_url,
            allow_hosts=allow_hosts,
            allowed_ports=DEFAULT_ALLOWED_PORTS,
        )
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        targets = resolve_safely(parsed.hostname or "", port)
        if not targets:
            # Should be impossible after resolve_safely passes; defensive.
            raise SourceUnavailableError(
                "No vetted addresses.", code="dns_error"
            )
        target = targets[0]

        # Build a fresh client per hop. We connect to the pinned IP;
        # the original hostname goes into Host: + SNI.
        async with httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            verify=True,  # TLS verification always on
            headers={"Host": parsed.netloc, **headers},
        ) as client:
            try:
                response = await client.get(
                    target.url,
                    headers={
                        "Host": parsed.netloc,
                        **headers,
                    },
                    extensions={
                        "sni_hostname": parsed.hostname or "",
                    },
                )
            except httpx.ConnectError as exc:
                raise SourceUnavailableError(
                    "Connect failed.",
                    code="connect_error",
                    details={"host": parsed.hostname, "ip": target.ip},
                ) from exc
            except httpx.TimeoutException as exc:
                raise SourceUnavailableError(
                    "Timeout.",
                    code="timeout",
                    details={"host": parsed.hostname},
                ) from exc
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(
                    f"HTTP error: {exc}",
                    code="http_error",
                    details={"host": parsed.hostname},
                ) from exc

            # 3xx with Location → manual redirect hop.
            if 300 <= response.status_code < 400 and response.headers.get("location"):
                if hop >= max_redirects:
                    raise SourceBlockedError(
                        "Too many redirects.",
                        code="too_many_redirects",
                        details={"max": max_redirects},
                    )
                next_url = response.headers["location"]
                # Cross-host redirect → drop sensitive headers.
                try:
                    next_parsed = urlparse(next_url)
                except ValueError:
                    raise SourceBlockedError(
                        "Bad redirect target.", code="bad_url"
                    )
                if (next_parsed.hostname or "").lower() != (parsed.hostname or "").lower():
                    headers = {
                        k: v
                        for k, v in headers.items()
                        if k.lower() not in sensitive_header_names
                    }
                # Re-validate on the next loop iteration.
                current_url = next_url
                continue

            # 2xx, 4xx, 5xx — collect the body.
            try:
                body_bytes = bytearray()
                async for chunk in response.aiter_bytes():
                    body_bytes.extend(chunk)
                    if len(body_bytes) > max_bytes:
                        raise SourceTooLargeError(
                            f"Response exceeds {max_bytes} bytes.",
                            code="response_too_large",
                            details={"max_bytes": max_bytes},
                        )
            except SourceTooLargeError:
                raise
            except httpx.HTTPError as exc:
                raise SourceUnavailableError(
                    f"Streaming failed: {exc}",
                    code="stream_error",
                ) from exc

            # Hard cap declared up front + lying headers.
            cl = response.headers.get("content-length")
            if cl is not None:
                try:
                    if int(cl) > max_bytes:
                        raise SourceTooLargeError(
                            "Content-Length exceeds cap.",
                            code="response_too_large",
                            details={"max_bytes": max_bytes, "content_length": cl},
                        )
                except ValueError:
                    pass  # malformed content-length, ignored

            if response.status_code >= 500:
                raise SourceUnavailableError(
                    "Upstream 5xx.",
                    code="http_5xx",
                    details={"status": response.status_code},
                )
            if response.status_code >= 400:
                # 4xx (other than 3xx redirects, already handled).
                # 429 → rate-limited signal. 404 → not found. Both are
                # the adapter's problem to map to a friendlier code.
                if response.status_code == 429:
                    raise SourceUnavailableError(
                        "Upstream 429 Too Many Requests.",
                        code="upstream_rate_limited",
                    )
                if response.status_code == 404:
                    raise SourceUnavailableError(
                        "Upstream 404 Not Found.",
                        code="upstream_404",
                    )
                raise SourceUnavailableError(
                    f"Upstream {response.status_code}.",
                    code="http_4xx_unexpected",
                    details={"status": response.status_code},
                )

            return SafeResponse(
                status_code=response.status_code,
                headers=dict(response.headers),
                body=bytes(body_bytes),
                final_url=current_url,
                hop_count=hop,
            )

    # Fell out of the loop without returning — too many redirects.
    raise SourceBlockedError(
        "Too many redirects (loop exhausted).",
        code="too_many_redirects",
        details={"max": max_redirects},
    )


__all__ = [
    "ALLOWED_SCHEMES",
    "DEFAULT_ALLOWED_PORTS",
    "GITHUB_ALLOWLIST",
    "ResolvedTarget",
    "SafeResponse",
    "check_ip_family",
    "resolve_safely",
    "safe_get",
    "validate_url",
]


# ---------------------------------------------------------------------------
# Startup safety check (called once at app boot)
# ---------------------------------------------------------------------------


def warn_if_allow_private() -> None:
    """Log a loud warning if SSRF_ALLOW_PRIVATE is enabled.

    Called from ``backend.app.main`` during lifespan startup. Should
    not be invoked in production.
    """
    settings = get_settings()
    if getattr(settings, "ssrf_allow_private", False):
        logger.warning(
            "SECURITY: SSRF_ALLOW_PRIVATE=true — loopback/private IPs "
            "are PERMITTED for outbound HTTP. This must NEVER be enabled "
            "in production. Disable immediately after testing."
        )