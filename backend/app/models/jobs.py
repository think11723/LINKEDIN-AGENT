"""Job Tracker data models — Phase 11.

Structured job, application, application event, and job-resume
match models. Every list defaults to empty so the deterministic
parser can populate fields incrementally. A field that the parser
could not extract stays empty (or "Not specified"); it is NEVER
fabricated.

CRITICAL data-integrity rules:

* No fabricated company, role, dates, salary, technologies, or
  candidate experience.
* If the JD text contains a prompt-injection attempt, the
  analyzer treats it as DATA, never as INSTRUCTIONS.
* The user always owns the resume. Optimization never overwrites
  the original (Phase 10 / version-copy mechanism).
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from backend.app.models.resume import (
    ATSScoreBreakdown,
    JDAnalysis,
)


# ----------------------------------------------------------------
# Job
# ----------------------------------------------------------------


WORK_MODES = {"remote", "hybrid", "onsite", "unknown"}
EMPLOYMENT_TYPES = {
    "full_time",
    "part_time",
    "internship",
    "contract",
    "freelance",
    "unknown",
}


class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    company: str = Field(default="", max_length=300)
    location: str = Field(default="", max_length=300)
    work_mode: str = Field(default="unknown", max_length=32)
    employment_type: str = Field(default="unknown", max_length=32)
    job_url: str = Field(default="", max_length=2000)
    source: str = Field(default="manual", max_length=64)
    source_name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=200_000)
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = Field(default="", max_length=8)
    posted_date: str = Field(default="", max_length=64)
    deadline: str = Field(default="", max_length=64)
    notes: str = Field(default="", max_length=4000)


class JobUpdateRequest(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None
    employment_type: Optional[str] = None
    job_url: Optional[str] = None
    description: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    posted_date: Optional[str] = None
    deadline: Optional[str] = None
    notes: Optional[str] = None


class JobImportRequest(BaseModel):
    """Import a job from a URL. The deterministic fetcher
    downloads the page safely (SSRF-guarded) and extracts the job
    description text."""

    url: str = Field(..., min_length=1, max_length=2000)
    title: str = Field(default="", max_length=300)
    company: str = Field(default="", max_length=300)


class JobImportResponse(BaseModel):
    """Returned by ``POST /api/v1/jobs/import``.

    The deterministic fetcher populates only fields it can
    confidently extract. Missing fields are empty. The user can
    review and edit the extracted job before saving.
    """

    job: "JobResponse"
    parser_warnings: List[str] = Field(default_factory=list)
    raw_text_preview: str = ""


class JobResponse(BaseModel):
    id: str
    title: str
    company: str = ""
    location: str = ""
    work_mode: str = "unknown"
    employment_type: str = "unknown"
    job_url: str = ""
    source: str = "manual"
    source_name: str = ""
    description: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = ""
    posted_date: str = ""
    deadline: str = ""
    notes: str = ""
    jd_analysis: Optional[JDAnalysis] = None
    saved_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_at: Optional[str] = None


# ----------------------------------------------------------------
# Application
# ----------------------------------------------------------------


APPLICATION_STATUSES = {
    "saved",
    "preparing",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
}


class ApplicationCreateRequest(BaseModel):
    job_id: str
    resume_id: str
    optimized_resume_id: Optional[str] = None
    status: str = Field(default="saved", max_length=32)
    application_url: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=4000)
    recruiter_name: str = Field(default="", max_length=200)
    recruiter_contact: str = Field(default="", max_length=400)
    salary: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    next_action: str = Field(default="", max_length=400)
    next_action_date: str = Field(default="", max_length=64)


class ApplicationUpdateRequest(BaseModel):
    resume_id: Optional[str] = None
    optimized_resume_id: Optional[str] = None
    status: Optional[str] = None
    application_url: Optional[str] = None
    notes: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_contact: Optional[str] = None
    salary: Optional[str] = None
    location: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    resume_id: str
    optimized_resume_id: Optional[str] = None
    status: str = "saved"
    application_url: str = ""
    notes: str = ""
    recruiter_name: str = ""
    recruiter_contact: str = ""
    salary: str = ""
    location: str = ""
    next_action: str = ""
    next_action_date: str = ""
    applied_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ----------------------------------------------------------------
# Application events
# ----------------------------------------------------------------


APPLICATION_EVENT_TYPES = {
    "saved",
    "preparing",
    "applied",
    "screening",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
    "note",
    "resume_optimized",
    "linkedin_created",
}


class ApplicationEventCreateRequest(BaseModel):
    event_type: str = Field(default="note", max_length=32)
    metadata: dict = Field(default_factory=dict)


class ApplicationEventResponse(BaseModel):
    id: str
    application_id: str
    event_type: str
    metadata: dict = Field(default_factory=dict)
    timestamp: Optional[str] = None


# ----------------------------------------------------------------
# Resume match
# ----------------------------------------------------------------


class MatchRequest(BaseModel):
    job_id: str
    resume_id: Optional[str] = None  # omitted → match all user resumes


class ResumeMatchResponse(BaseModel):
    id: str
    job_id: str
    resume_id: str
    overall_score: int = 0
    breakdown: ATSScoreBreakdown = Field(default_factory=ATSScoreBreakdown)
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    jd_analysis: Optional[JDAnalysis] = None
    resume_title: str = ""
    resume_target_role: str = ""
    created_at: Optional[str] = None


# ----------------------------------------------------------------
# Optimize / LinkedIn bridge requests
# ----------------------------------------------------------------


class JobOptimizeRequest(BaseModel):
    """Create an optimized resume copy for a specific job.

    Reuses the Phase 10 version-copy mechanism. The original
    resume is NEVER modified.
    """

    job_id: str
    resume_id: str
    optimized_title: Optional[str] = None


class JobLinkedInRequest(BaseModel):
    """Build a LinkedIn post draft from a job + resume combination.

    The post is grounded in the job context and the resume's
    relevant experience, and never implies employment / acceptance
    unless the user explicitly provides that fact. The existing
    WorkflowService is reused.
    """

    job_id: str
    resume_id: str
    post_type: str = Field(
        default="career_achievement",
        description=(
            "One of: project_launch, career_achievement, learning_journey, "
            "job_experience, certification, technical_deep_dive, career_milestone."
        ),
    )
    tone: str = Field(default="professional", max_length=32)
    angle: str = Field(
        default="researching",
        description=(
            "One of: researching, applying, employed. Determines how "
            "the post is framed. Default 'researching' is the safest "
            "non-deceptive choice."
        ),
    )


class JobLinkedInResponse(BaseModel):
    draft_id: str
    approval_token: str = ""
    source_url: str = ""
    source_type: str = "job"
    source_label: str = ""


# ----------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------


class ApplicationDashboard(BaseModel):
    counts: dict = Field(default_factory=dict)
    applications_this_week: int = 0
    applications_this_month: int = 0
    interview_rate: Optional[float] = None
    offer_rate: Optional[float] = None
    average_ats: int = 0
    upcoming: list = Field(default_factory=list)


__all__ = [
    "APPLICATION_EVENT_TYPES",
    "APPLICATION_STATUSES",
    "ApplicationCreateRequest",
    "ApplicationDashboard",
    "ApplicationEventCreateRequest",
    "ApplicationEventResponse",
    "ApplicationResponse",
    "ApplicationUpdateRequest",
    "EMPLOYMENT_TYPES",
    "JobCreateRequest",
    "JobImportRequest",
    "JobImportResponse",
    "JobLinkedInRequest",
    "JobLinkedInResponse",
    "JobOptimizeRequest",
    "JobResponse",
    "JobUpdateRequest",
    "MatchRequest",
    "ResumeMatchResponse",
    "WORK_MODES",
]
