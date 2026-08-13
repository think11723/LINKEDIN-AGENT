"""Repository layer for Mongo-backed data access.

All user-owned operations accept the authenticated Firebase UID and embed
``user_id`` in queries. Cross-user access must return ``None`` so callers
respond with HTTP 404 (never 403, to avoid leaking existence).
"""

from backend.app.repositories.user_repository import UserRepository
from backend.app.repositories.draft_repository import DraftRepository
from backend.app.repositories.approval_repository import ApprovalRepository
from backend.app.repositories.scheduler_repository import SchedulerRepository
from backend.app.repositories.linkedin_repository import LinkedInRepository
from backend.app.repositories.audit_repository import AuditRepository
from backend.app.repositories.oauth_state_repository import OAuthStateRepository

__all__ = [
    "UserRepository",
    "DraftRepository",
    "ApprovalRepository",
    "SchedulerRepository",
    "LinkedInRepository",
    "AuditRepository",
    "OAuthStateRepository",
]