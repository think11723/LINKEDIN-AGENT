"""Phase 8B P1-11 — server-side user settings resource.

Settings live in the same ``users`` document under a ``preferences`` sub-doc.
The LinkedIn connection status is sourced from
[backend.app.repositories.linkedin_repository] and is not editable here.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.app.api.deps import (
    get_audit_repository,
    get_linkedin_repository,
    get_user_repository,
    get_linkedin_repository,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import (
    AuditRepository,
    LinkedInRepository,
    UserRepository,
)
from shared.schemas import (
    APPROVAL_MODES,
    PUBLISHING_MODES,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


# Permissive but safe email regex (RFC 5322 subset). Server-side
# validation only — the frontend does not need to mirror this.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_enums(*, publishing_mode: Optional[str], approval_mode: Optional[str]) -> None:
    if publishing_mode is not None and publishing_mode not in PUBLISHING_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"publishing_mode must be one of {list(PUBLISHING_MODES)}",
        )
    if approval_mode is not None and approval_mode not in APPROVAL_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"approval_mode must be one of {list(APPROVAL_MODES)}",
        )


def _validate_timezone(tz: Optional[str]) -> None:
    if tz is None:
        return
    try:
        ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown IANA timezone: {tz}",
        ) from exc


def _validate_email(email: Optional[str]) -> None:
    if email is None:
        return
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid notification_email")


@router.get("", response_model=UserSettingsResponse)
async def get_settings(
    user: AuthenticatedUser = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
    linkedin: LinkedInRepository = Depends(get_linkedin_repository),
) -> UserSettingsResponse:
    # Auto-seed so a fresh user doesn't need to hit /auth/me first.
    doc = await users.get_or_seed(
        user.uid,
        email=user.email or "",
        name=user.name,
        email_verified=user.email_verified,
    )
    preferences = (doc or {}).get("preferences") or {}
    linkedin_status = await linkedin.status(user.uid)

    return UserSettingsResponse(
        linkedin_connected=bool(linkedin_status.get("connected", False)),
        person_urn=linkedin_status.get("person_urn"),
        linkedin_expires_at=linkedin_status.get("expires_at"),
        linkedin_scope=linkedin_status.get("scope"),
        publishing_mode=preferences.get("publishing_mode", "manual"),
        approval_mode=preferences.get("approval_mode", "email"),
        notification_email=preferences.get("notification_email"),
        default_image_provider=None,
        default_image_model=None,
        timezone=preferences.get("timezone"),
        updated_at=(
            (doc or {}).get("updated_at").isoformat()
            if (doc or {}).get("updated_at")
            else ""
        ),
    )


@router.put("", response_model=UserSettingsResponse)
async def update_settings(
    payload: UserSettingsUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
    linkedin: LinkedInRepository = Depends(get_linkedin_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> UserSettingsResponse:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await get_settings(
            user=user, users=users, linkedin=linkedin
        )

    _validate_enums(
        publishing_mode=updates.get("publishing_mode"),
        approval_mode=updates.get("approval_mode"),
    )
    _validate_timezone(updates.get("timezone"))
    _validate_email(updates.get("notification_email"))

    # Cross-field rule: approval_mode == "email" requires a
    # notification_email. Without this, the email pipeline silently
    # short-circuits with reason="notification_email_not_set".
    # Surface the error at the save boundary instead.
    if updates.get("approval_mode") == "email":
        notif = updates.get("notification_email")
        if not notif or not str(notif).strip():
            raise HTTPException(
                status_code=422,
                detail=(
                    "notification_email is required when "
                    "approval_mode == 'email'"
                ),
            )

    try:
        payload_validated = UserSettingsUpdateRequest.model_validate(updates)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    await users.get_or_seed(
        user.uid,
        email=user.email or "",
        name=user.name,
        email_verified=user.email_verified,
    )
    await users.update_preferences(user.uid, **payload_validated.model_dump(exclude_unset=True))
    await audit.log(
        user_id=user.uid,
        event_type="SETTINGS_UPDATED",
        description="Settings updated",
        details={"fields": sorted(updates.keys())},
    )
    return await get_settings(
        user=user,
        users=users,
        linkedin=linkedin,
    )