"""Scheduler API endpoints for the frontend."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from scheduler.service import SchedulerService
from shared.schemas import (
    SchedulePostPayload,
    SchedulePostResponse,
    SchedulerJobResponse,
)

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


@router.get("/jobs", response_model=list[SchedulerJobResponse])
async def get_jobs() -> list[SchedulerJobResponse]:
    service = SchedulerService()
    jobs = service.get_all_jobs()
    return [
        SchedulerJobResponse(
            job_id=job.job_id,
            title=job.title,
            content=job.content,
            hashtags=job.hashtags,
            scheduled_time=job.scheduled_time.isoformat(),
            status=job.status.value,
        )
        for job in jobs
    ]


@router.post("/schedule", response_model=SchedulePostResponse)
async def schedule_post(payload: SchedulePostPayload) -> SchedulePostResponse:
    service = SchedulerService()
    if not payload.title or not payload.content:
        raise HTTPException(
            status_code=400,
            detail="title and content are required",
        )

    scheduled_time = datetime.fromisoformat(payload.scheduled_time)
    job_id = service.schedule_post(
        title=payload.title,
        content=payload.content,
        hashtags=payload.hashtags,
        scheduled_time=scheduled_time,
        image_path=payload.image_path,
    )
    return SchedulePostResponse(
        success=True,
        job_id=job_id,
        scheduled_time=scheduled_time.isoformat(),
    )
