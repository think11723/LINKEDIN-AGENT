"""Dashboard endpoints — user-scoped summary metrics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.api.deps import (
    get_approval_repository,
    get_audit_repository,
    get_draft_repository,
    get_scheduler_repository,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import (
    ApprovalRepository,
    AuditRepository,
    DraftRepository,
    SchedulerRepository,
)
from shared.schemas import DashboardActivityItem, DashboardSummaryResponse

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    scheduler: SchedulerRepository = Depends(get_scheduler_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> DashboardSummaryResponse:
    drafts_count = await drafts.count(user.uid)
    published_count = await drafts.count(user.uid, status="published")
    approved_count = await drafts.count(user.uid, status="approved")
    pending_approvals = await approvals.count_for_user(user.uid, status="pending")
    scheduled_count = await scheduler.count_for_user(user.uid, status="pending")
    failed_count = await scheduler.count_for_user(user.uid, status="failed")

    activity = await audit.list_recent(user.uid, limit=8)
    return DashboardSummaryResponse(
        drafts_count=drafts_count,
        published_count=published_count,
        approved_count=approved_count,
        scheduled_count=scheduled_count,
        failed_count=failed_count,
        approval_queue_count=pending_approvals,
        recent_activity=[
            DashboardActivityItem(
                event_type=item.get("event_type", "event"),
                description=item.get("description", item.get("event_type", "event")),
                timestamp=(
                    item["timestamp"].isoformat()
                    if hasattr(item.get("timestamp"), "isoformat")
                    else str(item.get("timestamp"))
                ),
            )
            for item in activity
        ],
    )