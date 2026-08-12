"""Recent activity API for dashboard usage."""

from __future__ import annotations

from fastapi import APIRouter

from approval.audit import AuditLog
from shared.schemas import DashboardActivityItem, DashboardActivityResponse

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


@router.get("/recent", response_model=DashboardActivityResponse)
async def get_recent_activity() -> DashboardActivityResponse:
    audit_log = AuditLog()
    events = sorted(
        audit_log.events,
        key=lambda event: event.timestamp,
        reverse=True,
    )[:12]
    return DashboardActivityResponse(
        items=[
            DashboardActivityItem(
                event_type=event.event_type.value,
                description=(
                    event.details.get("title") or event.event_type.value
                ),
                timestamp=event.timestamp.isoformat(),
            )
            for event in events
        ]
    )
