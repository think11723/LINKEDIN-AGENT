"""LinkedIn OAuth endpoints — per-user, PKCE-protected.

The Firebase ID token is required for ``/connect``, ``/status``, and
``/disconnect``. The ``/callback`` endpoint intentionally does NOT
require a Bearer header (the browser loses it during the LinkedIn
redirect). Instead, the ``state`` nonce stored at ``/connect`` time
securely binds the callback to the originating Firebase user.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
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


def _pkce_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _resolve_linkedin_settings(settings: Settings) -> tuple[str, str, str]:
    if not settings.linkedin_client_id or not settings.linkedin_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LinkedIn OAuth is not configured on the server.",
        )
    return (
        settings.linkedin_client_id,
        settings.linkedin_client_secret,
        settings.linkedin_redirect_uri,
    )


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


def _build_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(LINKEDIN_SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{LINKEDIN_AUTHORIZE_URL}?{urlencode(params)}"


@router.get("/connect", response_model=ConnectResponse)
async def connect(
    user: AuthenticatedUser = Depends(get_current_user),
    oauth_states: OAuthStateRepository = Depends(get_oauth_state_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> ConnectResponse:
    """Generate a PKCE-protected authorization URL for the current user."""
    settings = get_settings()
    client_id, _, redirect_uri = _resolve_linkedin_settings(settings)

    code_verifier = secrets.token_urlsafe(48)
    code_challenge = _pkce_code_challenge(code_verifier)
    record = await oauth_states.create(
        user_id=user.uid,
        code_verifier=code_verifier,
        ttl_seconds=600,
    )
    authorization_url = _build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=record["state"],
        code_challenge=code_challenge,
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
    code_verifier = record["code_verifier"]

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
                    "code_verifier": code_verifier,
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
            details={"reason": "request_error"},
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

        audit_details: dict[str, Any] = {"status": token_response.status_code}
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