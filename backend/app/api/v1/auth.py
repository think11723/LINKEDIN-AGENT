"""Auth router — exposes the verified Firebase identity.

``GET /api/v1/auth/me`` returns the verified user's profile. The
Firebase UID is the source of truth for ownership everywhere else in
the API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_user_repository
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import UserRepository

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/me")
async def me(
    user: AuthenticatedUser = Depends(get_current_user),
    users: UserRepository = Depends(get_user_repository),
) -> dict:
    profile = await users.upsert_from_auth(user)
    return {
        "uid": user.uid,
        "email": user.email,
        "email_verified": user.email_verified,
        "name": user.name,
        "picture": user.picture,
        "profile": {
            "created_at": profile.get("created_at") if profile else None,
            "updated_at": profile.get("updated_at") if profile else None,
        },
    }