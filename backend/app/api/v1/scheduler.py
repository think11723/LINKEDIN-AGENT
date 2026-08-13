"""Scheduler HTTP endpoints — user-scoped, Mongo-backed."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.api.deps import (
    get_audit_repository,
    get_draft_repository,
    get_scheduler_repository,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import (
    AuditRepository,
    DraftRepository,
    SchedulerRepository,
)
from shared.schemas import (
    SchedulePostPayload,
    SchedulePostResponse,
    SchedulerJobResponse,
)

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


@router.get("/jobs", response_model=list[SchedulerJobResponse])
async def get_jobs(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    user: AuthenticatedUser = Depends(get_current_user),
    scheduler: SchedulerRepository = Depends(get_scheduler_repository),
) -> list[SchedulerJobResponse]:
    jobs = await scheduler.list_for_user(user.uid, status=status_filter, limit=200)
    return [
        SchedulerJobResponse(
            job_id=job["_id"],
            title=job.get("title", ""),
            content=job.get("content", ""),
            hashtags=job.get("hashtags", []),
            scheduled_time=(
                job["scheduled_time"].isoformat()
                if hasattr(job.get("scheduled_time"), "isoformat")
                else str(job.get("scheduled_time"))
            ),
            status=job.get("status", "pending"),
        )
        for job in jobs
    ]


@router.post("/schedule", response_model=SchedulePostResponse)
async def schedule_post(
    payload: SchedulePostPayload,
    user: AuthenticatedUser = Depends(get_current_user),
    scheduler: SchedulerRepository = Depends(get_scheduler_repository),
    drafts: DraftRepository = Depends(get_draft_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> SchedulePostResponse:
    if not payload.title or not payload.content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="title and content are required",
        )
    try:
        scheduled_time = datetime.fromisoformat(payload.scheduled_time.replace("Z", "+00:00"))
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_time must be ISO-8601",
        ) from exc

    job = await scheduler.create(
        user_id=user.uid,
        draft_id=None,
        title=payload.title,
        content=payload.content,
        hashtags=payload.hashtags or [],
        image_path=payload.image_path,
        scheduled_time=scheduled_time,
    )

    await audit.log(
        user_id=user.uid,
        event_type="JOB_SCHEDULED",
        description=payload.title,
        details={
            "job_id": job["_id"],
            "scheduled_time": payload.scheduled_time,
        },
    )

    return SchedulePostResponse(
        success=True,
        job_id=job["_id"],
        scheduled_time=scheduled_time.isoformat(),
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_job(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    scheduler: SchedulerRepository = Depends(get_scheduler_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> None:
    job = await scheduler.get(user.uid, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")
    deleted = await scheduler.cancel(user.uid, job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending jobs can be cancelled",
        )
    await audit.log(
        user_id=user.uid,
        event_type="JOB_CANCELLED",
        description=job.get("title", ""),
        details={"job_id": job_id},
    )