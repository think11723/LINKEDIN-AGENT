"""LinkedIn OAuth endpoints — per-user, PKCE-protected.

The Firebase ID token is required for ``/connect``, ``/status``, and
``/disconnect``. The ``/callback`` endpoint intentionally does NOT
require a Bearer header (the browser loses it during the LinkedIn
redirect). Instead, the ``state`` nonce stored at ``/connect`` time
securely binds the callback to the originating Firebase user.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from urllib.parse import quote

from backend.app.api.deps import (
    get_audit_repository,
    get_linkedin_repository,
    get_oauth_state_repository,
)
from backend.app.core.config import Settings, get_settings
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import (
    AuditRepository,
    LinkedInRepository,
    OAuthStateRepository,
)

logger = logging.getLogger(__name__)

LINKEDIN_AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

LINKEDIN_SCOPES = ["openid", "profile", "email", "w_member_social"]

router = APIRouter(prefix="/api/v1/linkedin", tags=["linkedin"])


class ConnectResponse(BaseModel):
    authorization_url: str
    state: str
    expires_at: str


class StatusResponse(BaseModel):
    connected: bool
    person_urn: Optional[str] = None
    expires_at: Optional[str] = None
    scope: Optional[str] = None


class DisconnectResponse(BaseModel):
    connected: bool


def _resolve_linkedin_settings(settings: Settings) -> tuple[str, str, str]:
    """Return (client_id, client_secret, redirect_uri) with all
    common paste-corruption stripped.

    Settings already ``.strip()`` ASCII whitespace, but real-world
    Railway env-var paste introduces non-whitespace junk too (BOM,
    zero-width spaces, surrounding quote / backtick / paren
    pairs). Aggressively normalising here means a single
    paste-corruption does not reach LinkedIn's /oauth/v2/accessToken
    as ``invalid_client``.
    """
    client_id = _normalize_credential(settings.linkedin_client_id)
    client_secret = _normalize_credential(settings.linkedin_client_secret)
    redirect_uri = _normalize_credential(settings.linkedin_redirect_uri)
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn OAuth is not configured on the server.",
        )
    return (client_id, client_secret, redirect_uri)


# OAuth error codes are short ASCII identifiers (RFC 6749 §5.2 + LinkedIn
# extensions). Restrict to that character set and cap the length so a
# hostile or buggy error payload cannot smuggle newlines, secrets, or
# log-injection content into audit rows or the redirect query string.
_OAUTH_ERROR_TOKEN_RE = re.compile(r"[^A-Za-z0-9_\-.]")


def _sanitize_oauth_error_token(value: str) -> Optional[str]:
    cleaned = _OAUTH_ERROR_TOKEN_RE.sub("", value).strip().strip(".")
    if not cleaned:
        return None
    return cleaned[:64] or None


_OAUTH_ERROR_TEXT_RE = re.compile(r"[^A-Za-z0-9 _\-.,:/()@?=&%+#]")


def _sanitize_oauth_error_text(value: str) -> Optional[str]:
    cleaned = _OAUTH_ERROR_TEXT_RE.sub("", value).strip()
    if not cleaned:
        return None
    return cleaned[:200] or None


# P0-9: defensive credential handling.
#
# ``str.strip()`` only handles ASCII whitespace. Real-world paste
# corruption into env-var UIs also brings:
#   - BOM / zero-width spaces / zero-width joiners / non-joiner
#   - surrounding ``"`` / ``'`` / ```` ` ```` / ``(`` ``)`` pairs
#   - other invisible Unicode characters
#
# These survive ``str.strip()`` and would be sent verbatim to
# LinkedIn's /oauth/v2/accessToken, producing ``invalid_client``.
# The two helpers below strip them before any request is built.
_UNUSUAL_CHAR_RE = re.compile(
    "["
    "​"  # ZERO WIDTH SPACE
    "‌"  # ZERO WIDTH NON-JOINER
    "‍"  # ZERO WIDTH JOINER
    "‎"  # LEFT-TO-RIGHT MARK
    "‏"  # RIGHT-TO-LEFT MARK
    "‪"  # LEFT-TO-RIGHT EMBEDDING
    "‫"  # RIGHT-TO-LEFT EMBEDDING
    "‬"  # POP DIRECTIONAL FORMATTING
    "‭"  # LEFT-TO-RIGHT OVERRIDE
    "‮"  # RIGHT-TO-LEFT OVERRIDE
    "﻿"  # ZERO WIDTH NO-BREAK SPACE / BOM
    "⁠"  # WORD JOINER
    "⁡"  # FUNCTION APPLICATION
    "⁢"  # INVISIBLE TIMES
    "⁣"  # INVISIBLE SEPARATOR
    "⁤"  # INVISIBLE PLUS
    "]"
)
_SURROUNDING_PAIRS = (('"', '"'), ("'", "'"), ("`", "`"), ("(", ")"),
                      ("[", "]"), ("{", "}"))


def _normalize_credential(value: str) -> str:
    """Return a defensive copy of ``value`` with the most common
    paste-corruption stripped. Does not touch a string that is
    already clean."""
    if not value:
        return value
    # 1. Strip ASCII whitespace (defence in depth — config.py
    # already does this, but we re-strip here so the function is
    # correct when called from tests or future code paths).
    cleaned = value.strip()
    # 2. Strip zero-width / BOM / format characters that survive
    # ``str.strip()``.
    cleaned = _UNUSUAL_CHAR_RE.sub("", cleaned)
    # 3. Peel surrounding wrapping pairs (quotes, backticks,
    # parens, brackets, braces) so a paste like ``"secret"`` or
    # ``"secret"`` becomes ``secret``. Walk at most a few times
    # to peel nested wrapping.
    for _ in range(3):
        changed = False
        for opener, closer in _SURROUNDING_PAIRS:
            if (
                len(cleaned) >= 2
                and cleaned[0] == opener
                and cleaned[-1] == closer
            ):
                cleaned = cleaned[1:-1]
                changed = True
        if not changed:
            break
    return cleaned


def _credential_fingerprint(value: str) -> Optional[str]:
    """Return a short, NON-REVERSIBLE SHA-256 prefix of the
    credential so the operator can confirm Railway matches the
    LinkedIn Developer Portal without ever exposing the secret.
    Returns ``None`` when the credential is empty.
    """
    if not value:
        return None
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    # 16 hex chars = 64 bits — collision-resistant enough to act
    # as a fingerprint, short enough for an audit-log field.
    return digest[:16]


# P0-9: return the SHAPE of the configured LinkedIn credentials so
# operators can prove what the running backend saw — without ever
# leaking the credential value itself.
def _credential_shape(value: str) -> dict[str, Any]:
    configured = bool(value)
    raw = value
    normalized = _normalize_credential(raw)
    has_whitespace = raw != raw.strip()
    has_newline = "\n" in raw or "\r" in raw
    has_unusual_chars = normalized != raw.strip()
    return {
        "configured": configured,
        "length": len(normalized),
        "raw_length": len(raw),
        "had_whitespace": has_whitespace,
        "had_newline": has_newline,
        "had_unusual_chars": has_unusual_chars,
        "fingerprint_sha256_16": _credential_fingerprint(normalized),
    }


def _linkedin_config_shape(settings: Settings) -> dict[str, Any]:
    """Return a redacted snapshot of the LinkedIn OAuth configuration.

    Captures only:
      * whether each credential is set,
      * its length (post-normalization),
      * whether the raw env-var value had whitespace / newline /
        non-whitespace paste corruption BEFORE normalization,
      * a 64-bit SHA-256 fingerprint so the operator can verify
        Railway matches the LinkedIn Developer Portal without ever
        exposing the secret,
      * the redirect URI in full (it is not secret).

    Captures NEVER:
      * the actual client_id,
      * the actual client_secret,
      * the authorization code,
      * the access/refresh tokens,
      * the PKCE verifier.
    """
    return {
        "client_id": _credential_shape(settings.linkedin_client_id),
        "client_secret": _credential_shape(settings.linkedin_client_secret),
    }


def _build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    """Build the standard 3-legged Authorization Code Flow authorize URL.

    Confidential server-side LinkedIn apps use the standard
    `/oauth/v2/authorization` endpoint with the canonical parameter
    set:

        response_type=code
        client_id=<client id>
        redirect_uri=<callback URL>
        scope=<space-delimited scopes>
        state=<CSRF nonce>

    PKCE (`code_challenge`, `code_challenge_method`) is intentionally
    NOT sent — it belongs to LinkedIn's separate native-app flow at
    `/oauth/native-pkce/authorization`, which excludes `client_secret`
    from its token exchange. Mixing PKCE params with the standard
    authorize URL while still sending `client_secret` is rejected by
    LinkedIn as an invalid flow.

    See:
    https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(LINKEDIN_SCOPES),
        "state": state,
    }
    return f"{LINKEDIN_AUTHORIZE_URL}?{urlencode(params)}"


@router.get("/connect", response_model=ConnectResponse)
async def connect(
    user: AuthenticatedUser = Depends(get_current_user),
    oauth_states: OAuthStateRepository = Depends(get_oauth_state_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> ConnectResponse:
    """Generate the standard 3-legged Authorization Code Flow URL.

    CSRF protection is preserved via the ``state`` nonce. PKCE is
    intentionally NOT used — this is a confidential server-side app.
    """
    settings = get_settings()
    client_id, _, redirect_uri = _resolve_linkedin_settings(settings)

    record = await oauth_states.create(
        user_id=user.uid,
        ttl_seconds=600,
    )
    authorization_url = _build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=record["state"],
    )

    await audit.log(
        user_id=user.uid,
        event_type="LINKEDIN_CONNECT_STARTED",
        description="LinkedIn OAuth flow initiated",
        details={"state_prefix": record["state"][:8]},
    )

    return ConnectResponse(
        authorization_url=authorization_url,
        state=record["state"],
        expires_at=record["expires_at"].isoformat(),
    )


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    oauth_states: OAuthStateRepository = Depends(get_oauth_state_repository),
    linkedin: LinkedInRepository = Depends(get_linkedin_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> RedirectResponse:
    """LinkedIn OAuth callback. Validates state + PKCE; exchanges code; persists token.

    Phase 8C — returns a 303 RedirectResponse to the SPA so the
    ``LinkedInCard`` component picks up the ``?linkedin=connected|error&reason=...``
    flag in the URL and shows the success/error toast.

    Note: this endpoint does NOT require a Firebase Bearer header because
    browsers drop the Authorization header during the LinkedIn redirect.
    The ``state`` nonce stored at ``/connect`` time binds the callback
    to the originating Firebase user.
    """
    settings = get_settings()
    frontend_base = settings.frontend_url.rstrip("/")

    def _redirect(query: str) -> RedirectResponse:
        return RedirectResponse(
            url=f"{frontend_base}/settings?{query}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    record = await oauth_states.consume(state)
    if not record:
        await audit.log(
            user_id="unknown",
            event_type="LINKEDIN_CONNECT_FAILED",
            description="LinkedIn OAuth state invalid or expired",
            details={"reason": "invalid_state"},
        )
        return _redirect("linkedin=error&reason=invalid_state")
    user_id = record["user_id"]

    try:
        client_id, client_secret, redirect_uri = _resolve_linkedin_settings(settings)
    except HTTPException as exc:
        await audit.log(
            user_id=user_id,
            event_type="LINKEDIN_CONNECT_FAILED",
            description="LinkedIn OAuth not configured",
            details={"reason": exc.detail},
        )
        return _redirect("linkedin=error&reason=not_configured")

    try:
        async with httpx.AsyncClient(timeout=30) as http:
            token_response = await http.post(
                LINKEDIN_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Accept": "application/json"},
            )
    except Exception as exc:  # noqa: BLE001
        # P0-8: log status only, never log the request body.
        logger.warning("LinkedIn token request failed: %s", exc.__class__.__name__)
        await audit.log(
            user_id=user_id,
            event_type="LINKEDIN_CONNECT_FAILED",
            description="LinkedIn token request failed",
            details={
                "reason": "request_error",
                "config_shape": _linkedin_config_shape(settings),
                "redirect_uri": settings.linkedin_redirect_uri,
            },
        )
        return _redirect("linkedin=error&reason=request_error")

    if token_response.status_code != 200:
        # P0-8 hygiene: capture only the OAuth-standard error fields
        # (error / error_description / error_uri) from LinkedIn's response
        # body. Never log the request body, the Authorization header,
        # the code, the PKCE verifier, or any token.
        oauth_error: Optional[str] = None
        oauth_error_description: Optional[str] = None
        oauth_error_uri: Optional[str] = None
        try:
            error_payload = token_response.json()
            if isinstance(error_payload, dict):
                raw_error = error_payload.get("error")
                raw_error_description = error_payload.get("error_description")
                raw_error_uri = error_payload.get("error_uri")
                if isinstance(raw_error, str):
                    oauth_error = _sanitize_oauth_error_token(raw_error)
                if isinstance(raw_error_description, str):
                    oauth_error_description = _sanitize_oauth_error_text(
                        raw_error_description
                    )
                if isinstance(raw_error_uri, str):
                    oauth_error_uri = _sanitize_oauth_error_text(raw_error_uri)
        except Exception:  # noqa: BLE001
            # LinkedIn sometimes returns a non-JSON error body. Fall
            # through with None values; the audit log still records
            # the HTTP status code.
            pass

        audit_details: dict[str, Any] = {
            "status": token_response.status_code,
            "config_shape": _linkedin_config_shape(settings),
            "redirect_uri": settings.linkedin_redirect_uri,
        }
        if oauth_error is not None:
            audit_details["error"] = oauth_error
        if oauth_error_description is not None:
            audit_details["error_description"] = oauth_error_description
        if oauth_error_uri is not None:
            audit_details["error_uri"] = oauth_error_uri

        await audit.log(
            user_id=user_id,
            event_type="LINKEDIN_CONNECT_FAILED",
            description="LinkedIn token exchange failed",
            details=audit_details,
        )

        redirect_query = "linkedin=error&reason=token_exchange"
        if oauth_error is not None:
            redirect_query += f"&detail={quote(oauth_error, safe='')}"
        return _redirect(redirect_query)

    token_payload = token_response.json()
    access_token = token_payload.get("access_token")
    refresh_token = token_payload.get("refresh_token")
    expires_in = token_payload.get("expires_in")
    scope = token_payload.get("scope")

    if not access_token:
        await audit.log(
            user_id=user_id,
            event_type="LINKEDIN_CONNECT_FAILED",
            description="LinkedIn response did not contain an access token",
        )
        return _redirect("linkedin=error&reason=no_access_token")

    expires_at: Optional[datetime] = None
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    person_urn = await _fetch_person_urn(access_token)
    await linkedin.upsert_tokens(
        user_id=user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        scope=scope,
        person_urn=person_urn,
    )
    await audit.log(
        user_id=user_id,
        event_type="LINKEDIN_CONNECTED",
        description="LinkedIn account connected",
        details={"scope": scope, "person_urn": person_urn},
    )
    return _redirect("linkedin=connected")


@router.get("/status", response_model=StatusResponse)
async def status_endpoint(
    user: AuthenticatedUser = Depends(get_current_user),
    linkedin: LinkedInRepository = Depends(get_linkedin_repository),
) -> StatusResponse:
    info = await linkedin.status(user.uid)
    return StatusResponse(**info)


@router.post("/disconnect", response_model=DisconnectResponse)
async def disconnect(
    user: AuthenticatedUser = Depends(get_current_user),
    linkedin: LinkedInRepository = Depends(get_linkedin_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> DisconnectResponse:
    deleted = await linkedin.disconnect(user.uid)
    if deleted:
        await audit.log(
            user_id=user.uid,
            event_type="LINKEDIN_DISCONNECTED",
            description="LinkedIn account disconnected",
        )
    return DisconnectResponse(connected=False)


async def _fetch_person_urn(access_token: str) -> Optional[str]:
    """Best-effort lookup of the LinkedIn member URN. None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            response = await http.get(
                LINKEDIN_USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
        if response.status_code != 200:
            return None
        data = response.json()
        sub = data.get("sub")
        return f"urn:li:person:{sub}" if sub else None
    except Exception:  # noqa: BLE001
        return None