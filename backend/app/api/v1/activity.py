"""Recent activity endpoint — user-scoped."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.deps import get_audit_repository
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import AuditRepository
from shared.schemas import DashboardActivityItem, DashboardActivityResponse

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


@router.get("/recent", response_model=DashboardActivityResponse)
async def get_recent_activity(
    limit: int = Query(default=12, ge=1, le=200),
    user: AuthenticatedUser = Depends(get_current_user),
    audit: AuditRepository = Depends(get_audit_repository),
) -> DashboardActivityResponse:
    events = await audit.list_recent(user.uid, limit=limit)
    return DashboardActivityResponse(
        items=[
            DashboardActivityItem(
                event_type=item.get("event_type", "event"),
                description=item.get("description", item.get("event_type", "event")),
                timestamp=(
                    item["timestamp"].isoformat()
                    if hasattr(item.get("timestamp"), "isoformat")
                    else str(item.get("timestamp"))
                ),
            )
            for item in events
        ]
    )