"""Phase 8B P1-10 — server-side user profile resource."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import (
    get_audit_repository,
    get_user_repository,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import AuditRepository, UserRepository
from shared.schemas import UserProfileResponse, UserProfileUpdateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


@router.get("", response_model=UserProfileResponse)
async def get_profile(
    user: AuthenticatedUser = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
) -> UserProfileResponse:
    # Auto-seed on first access so a fresh user can hit /profile without
    # having to call /auth/me first.
    doc = await users.get_or_seed(
        user.uid,
        email=user.email or "",
        name=user.name,
        email_verified=user.email_verified,
    )
    profile = (doc or {}).get("profile") or {}
    return UserProfileResponse(
        uid=user.uid,
        email=(doc or {}).get("email", user.email or ""),
        email_verified=bool((doc or {}).get("email_verified", False)),
        display_name=profile.get("display_name"),
        headline=profile.get("headline"),
        bio=profile.get("bio"),
        linkedin_url=profile.get("linkedin_url"),
        github_url=profile.get("github_url"),
        avatar_url=profile.get("avatar_url"),
        updated_at=(
            (doc or {}).get("updated_at").isoformat()
            if (doc or {}).get("updated_at")
            else ""
        ),
    )


@router.put("", response_model=UserProfileResponse)
async def update_profile(
    payload: UserProfileUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> UserProfileResponse:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return await get_profile(user=user, users=users)

    await users.update_profile(user.uid, **updates)
    await audit.log(
        user_id=user.uid,
        event_type="PROFILE_UPDATED",
        description="Profile updated",
        details={"fields": sorted(updates.keys())},
    )
    doc = await users.get_profile(user.uid)
    profile = (doc or {}).get("profile") or {}
    return UserProfileResponse(
        uid=user.uid,
        email=(doc or {}).get("email", user.email or ""),
        email_verified=bool((doc or {}).get("email_verified", False)),
        display_name=profile.get("display_name"),
        headline=profile.get("headline"),
        bio=profile.get("bio"),
        linkedin_url=profile.get("linkedin_url"),
        github_url=profile.get("github_url"),
        avatar_url=profile.get("avatar_url"),
        updated_at=(
            (doc or {}).get("updated_at").isoformat()
            if (doc or {}).get("updated_at")
            else ""
        ),
    )