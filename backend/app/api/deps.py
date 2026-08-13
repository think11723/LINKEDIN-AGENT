"""FastAPI dependency providers for repositories and the current user."""

from __future__ import annotations

from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.db.mongo import get_database
from backend.app.repositories import (
    ApprovalRepository,
    AuditRepository,
    DraftRepository,
    LinkedInRepository,
    OAuthStateRepository,
    SchedulerRepository,
    UserRepository,
)


def get_db() -> AsyncIOMotorDatabase:
    return get_database()


def get_user_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> UserRepository:
    return UserRepository(db)


def get_draft_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> DraftRepository:
    return DraftRepository(db)


def get_approval_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ApprovalRepository:
    return ApprovalRepository(db)


def get_scheduler_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SchedulerRepository:
    return SchedulerRepository(db)


def get_linkedin_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> LinkedInRepository:
    return LinkedInRepository(db)


def get_audit_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AuditRepository:
    return AuditRepository(db)


def get_oauth_state_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> OAuthStateRepository:
    return OAuthStateRepository(db)


# Re-export so handlers can simply say `user: AuthenticatedUser = Depends(get_current_user)`.
CurrentUser = Depends(get_current_user)