"""Job Tracker API endpoints — Phase 11.

Routes
------

Jobs:
* ``POST   /api/v1/jobs``                          — create a blank job
* ``GET    /api/v1/jobs``                          — list caller's jobs
* ``GET    /api/v1/jobs/{id}``                     — read
* ``PUT    /api/v1/jobs/{id}``                     — update
* ``DELETE /api/v1/jobs/{id}``                     — delete
* ``POST   /api/v1/jobs/import``                   — import a job from a URL
* ``POST   /api/v1/jobs/{id}/analyze``             — run a deterministic
                                                       JD analysis
* ``POST   /api/v1/jobs/{id}/match-resume``        — match all the user's
                                                       resumes against the JD
* ``GET    /api/v1/jobs/{id}/matches``             — list cached matches
* ``POST   /api/v1/jobs/{id}/optimize``            — create an optimized
                                                       resume copy
* ``POST   /api/v1/jobs/{id}/linkedin``             — create a LinkedIn post

Applications:
* ``POST   /api/v1/applications``                  — create
* ``GET    /api/v1/applications``                  — list
* ``GET    /api/v1/applications/{id}``             — read
* ``PUT    /api/v1/applications/{id}``             — update (status, notes, ...)
* ``DELETE /api/v1/applications/{id}``             — delete
* ``POST   /api/v1/applications/{id}/events``      — append event
* ``GET    /api/v1/applications/{id}/events``      — list events
* ``GET    /api/v1/applications/dashboard``        — dashboard summary

All routes are user-scoped. Cross-user access returns 404.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import (
    get_application_event_repository,
    get_application_repository,
    get_job_match_repository,
    get_job_repository,
    get_resume_service,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.db.mongo import get_database
from backend.app.models.jobs import (
    ApplicationCreateRequest,
    ApplicationDashboard,
    ApplicationEventCreateRequest,
    ApplicationEventResponse,
    ApplicationResponse,
    ApplicationUpdateRequest,
    JobCreateRequest,
    JobImportRequest,
    JobImportResponse,
    JobLinkedInRequest,
    JobLinkedInResponse,
    JobOptimizeRequest,
    JobResponse,
    JobUpdateRequest,
    ResumeMatchResponse,
)
from backend.app.repositories.job_repository import (
    ApplicationEventRepository,
    ApplicationRepository,
    JobMatchRepository,
    JobRepository,
    application_to_response,
    event_to_response,
    job_to_response,
    match_to_response,
)
from backend.app.services.job_service import JobService, JobServiceError

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------


def _map_service_error(e: JobServiceError) -> HTTPException:
    code = e.code or "job_error"
    if code in ("not_found",):
        status_code = status.HTTP_404_NOT_FOUND
    elif code in (
        "invalid_input",
        "unsupported_format",
        "duplicate",
        "extraction_failed",
        "parser_unavailable",
        "bad_resume",
        "not_configured",
        "bad_scheme",
    ):
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=e.message)


def _build_service(user: AuthenticatedUser) -> JobService:
    db = get_database()
    return JobService(
        jobs=JobRepository(db),
        applications=ApplicationRepository(db),
        events=ApplicationEventRepository(db),
        matches=JobMatchRepository(db),
        resumes_service=get_resume_service(),
    )


# ----------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------


jobs_router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@jobs_router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    payload: JobCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await _build_service(user).create(
            user_id=user.uid, payload=payload
        )
    except JobServiceError as e:
        raise _map_service_error(e)


@jobs_router.get("", response_model=List[JobResponse])
async def list_jobs(
    user: AuthenticatedUser = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
):
    return await _build_service(user).list(user_id=user.uid, limit=limit)


@jobs_router.post("/import", response_model=JobImportResponse)
async def import_job(
    payload: JobImportRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await _build_service(user).import_from_url(
            user_id=user.uid, payload=payload
        )
    except JobServiceError as e:
        raise _map_service_error(e)


@jobs_router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    found = await _build_service(user).get(user_id=user.uid, job_id=job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found.")
    return found


@jobs_router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    payload: JobUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        found = await _build_service(user).update(
            user_id=user.uid, job_id=job_id, payload=payload
        )
    except JobServiceError as e:
        raise _map_service_error(e)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found.")
    return found


@jobs_router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ok = await _build_service(user).delete(user_id=user.uid, job_id=job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Job not found.")
    return None


@jobs_router.post("/{job_id}/analyze", response_model=JobResponse)
async def analyze_job(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        found = await _build_service(user).analyze_jd(
            user_id=user.uid, job_id=job_id
        )
    except JobServiceError as e:
        raise _map_service_error(e)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found.")
    return found


@jobs_router.post("/{job_id}/match-resume", response_model=List[ResumeMatchResponse])
async def match_resume(
    job_id: str,
    payload: dict,
    user: AuthenticatedUser = Depends(get_current_user),
):
    resume_id = payload.get("resume_id") if payload else None
    try:
        out = await _build_service(user).match_resume(
            user_id=user.uid, job_id=job_id, resume_id=resume_id
        )
    except JobServiceError as e:
        raise _map_service_error(e)
    if not out:
        # No matches because job not found OR no resumes.
        # Distinguish by checking job existence.
        found = await _build_service(user).get(
            user_id=user.uid, job_id=job_id
        )
        if not found:
            raise HTTPException(status_code=404, detail="Job not found.")
        return []
    return out


@jobs_router.get("/{job_id}/matches", response_model=List[ResumeMatchResponse])
async def list_matches(
    job_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return await _build_service(user).list_matches(
        user_id=user.uid, job_id=job_id
    )


@jobs_router.post("/{job_id}/optimize", response_model=JobResponse)
async def optimize_resume(
    job_id: str,
    payload: JobOptimizeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        copy = await _build_service(user).optimize(
            user_id=user.uid,
            job_id=job_id,
            resume_id=payload.resume_id,
            optimized_title=payload.optimized_title,
        )
    except JobServiceError as e:
        raise _map_service_error(e)
    if not copy:
        raise HTTPException(
            status_code=404, detail="Resume or job not found."
        )
    return copy


@jobs_router.post("/{job_id}/linkedin", response_model=JobLinkedInResponse)
async def linkedin_from_job(
    job_id: str,
    payload: JobLinkedInRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await _build_service(user).create_linkedin_from_job(
            user_id=user.uid, payload=payload
        )
    except JobServiceError as e:
        raise _map_service_error(e)


# ----------------------------------------------------------------
# Applications
# ----------------------------------------------------------------


applications_router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@applications_router.post("", response_model=ApplicationResponse, status_code=201)
async def create_application(
    payload: ApplicationCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await _build_service(user).create_application(
            user_id=user.uid, payload=payload
        )
    except JobServiceError as e:
        raise _map_service_error(e)


@applications_router.get("", response_model=List[ApplicationResponse])
async def list_applications(
    user: AuthenticatedUser = Depends(get_current_user),
    status: Optional[str] = None,
):
    return await _build_service(user).list_applications(
        user_id=user.uid, status=status
    )


@applications_router.get("/dashboard", response_model=ApplicationDashboard)
async def applications_dashboard(
    user: AuthenticatedUser = Depends(get_current_user),
):
    return await _build_service(user).dashboard(user_id=user.uid)


@applications_router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    found = await _build_service(user).get_application(
        user_id=user.uid, app_id=app_id
    )
    if not found:
        raise HTTPException(status_code=404, detail="Application not found.")
    return found


@applications_router.put("/{app_id}", response_model=ApplicationResponse)
async def update_application(
    app_id: str,
    payload: ApplicationUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        found = await _build_service(user).update_application(
            user_id=user.uid, app_id=app_id, payload=payload
        )
    except JobServiceError as e:
        raise _map_service_error(e)
    if not found:
        raise HTTPException(status_code=404, detail="Application not found.")
    return found


@applications_router.delete("/{app_id}", status_code=204)
async def delete_application(
    app_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    ok = await _build_service(user).delete_application(
        user_id=user.uid, app_id=app_id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Application not found.")
    return None


@applications_router.post(
    "/{app_id}/events", response_model=ApplicationEventResponse
)
async def add_application_event(
    app_id: str,
    payload: ApplicationEventCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    try:
        return await _build_service(user).add_event(
            user_id=user.uid, app_id=app_id, payload=payload
        )
    except JobServiceError as e:
        raise _map_service_error(e)


@applications_router.get(
    "/{app_id}/events", response_model=List[ApplicationEventResponse]
)
async def list_application_events(
    app_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    return await _build_service(user).list_events(
        user_id=user.uid, app_id=app_id
    )


__all__ = ["jobs_router", "applications_router"]
