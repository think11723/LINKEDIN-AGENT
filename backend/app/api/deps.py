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
    SourceJobRepository,
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


# ----------------------------------------------------------------
# Phase 10 / Resume Studio
# ----------------------------------------------------------------

def get_resume_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from backend.app.repositories.resume_repository import ResumeRepository
    return ResumeRepository(db)


def get_resume_service(
    repo = Depends(get_resume_repository),
):
    from backend.app.services.resume_service import ResumeService
    return ResumeService(repo)


# ----------------------------------------------------------------
# Phase 11 / Job Tracker
# ----------------------------------------------------------------

def get_job_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from backend.app.repositories.job_repository import JobRepository
    return JobRepository(db)


def get_application_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from backend.app.repositories.job_repository import ApplicationRepository
    return ApplicationRepository(db)


def get_application_event_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from backend.app.repositories.job_repository import ApplicationEventRepository
    return ApplicationEventRepository(db)


def get_job_match_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from backend.app.repositories.job_repository import JobMatchRepository
    return JobMatchRepository(db)


def get_oauth_state_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> OAuthStateRepository:
    return OAuthStateRepository(db)


def get_source_job_repository(
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SourceJobRepository:
    """Phase 8D / URL-to-LinkedIn source-job repository."""
    return SourceJobRepository(db)


# Re-export so handlers can simply say `user: AuthenticatedUser = Depends(get_current_user)`.
CurrentUser = Depends(get_current_user)