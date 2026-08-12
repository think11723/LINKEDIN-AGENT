"""Dashboard endpoints that surface existing approval and scheduler state."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from approval.audit import AuditLog
from approval.service import ApprovalService
from scheduler.models import JobStatus
from scheduler.service import SchedulerService
from shared.schemas import DashboardActivityItem, DashboardSummaryResponse

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary() -> DashboardSummaryResponse:
    approval_service = ApprovalService()
    scheduler_service = SchedulerService()
    audit_log = AuditLog()

    drafts = approval_service.store.storage.get_all_drafts()
    tokens = approval_service.store.storage.get_all_tokens()
    jobs = scheduler_service.get_all_jobs()

    published_count = 0
    pending_approval_count = 0
    scheduled_count = 0
    drafts_list: list[dict[str, Any]] = []

    for draft_data in drafts.values():
        draft = (
            draft_data
            if isinstance(draft_data, dict)
            else draft_data.model_dump()
        )
        drafts_list.append(draft)
        if draft.get("published_at"):
            published_count += 1

        token = (
            tokens.get(draft.get("approval_token"))
            if draft.get("approval_token")
            else None
        )
        if token is not None and token.status.value == "pending":
            pending_approval_count += 1

    for job in jobs:
        if job.status == JobStatus.PENDING:
            scheduled_count += 1

    return DashboardSummaryResponse(
        drafts_count=len(drafts_list),
        published_count=published_count,
        scheduled_count=scheduled_count,
        approval_queue_count=pending_approval_count,
        recent_activity=[
            DashboardActivityItem(
                event_type=event.event_type.value,
                description=(
                    event.details.get("title") or event.event_type.value
                ),
                timestamp=event.timestamp.isoformat(),
            )
            for event in sorted(
                audit_log.events,
                key=lambda event: event.timestamp,
                reverse=True,
            )[:8]
        ],
    )
