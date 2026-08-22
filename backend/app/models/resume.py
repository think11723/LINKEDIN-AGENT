"""Resume data models — Phase 10.

Structured resume + ATS analysis models. A user may own multiple
resumes (e.g. one for "Software Engineer" and one for "AI Engineer"),
and each resume may have multiple ATS analyses against different
job descriptions.

The shape is intentionally conservative: the deterministic parser
populates only fields it can confidently extract. The LLM-assisted
normalization step may add structure but never invents data.

A resume has these top-level sections:

* ``personal``       — name / headline / contact / links
* ``summary``        — professional summary
* ``experience``     — list of positions
* ``education``      — list of schools
* ``skills``         — categorized skill list
* ``projects``       — list of projects
* ``certifications`` — list of certs
* ``achievements``   — list of awards / wins
* ``links``          — list of personal URLs

A "version" is a duplicate of a resume created via
:func:`ResumeService.create_version`. The original is never
silently overwritten; the user explicitly opts in to a copy.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------
# Building blocks
# ----------------------------------------------------------------


class PersonalInfo(BaseModel):
    """Basic contact information. The deterministic parser never
    invents values; the LLM normalizer may suggest corrections
    but the user must confirm them.
    """

    full_name: str = ""
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""


class ExperienceItem(BaseModel):
    """A single position held by the candidate."""

    company: str = ""
    role: str = ""
    location: str = ""
    start_date: str = ""  # free-form ("Jan 2020")
    end_date: str = ""
    currently_working: bool = False
    description: str = ""
    achievements: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str = ""
    coursework: List[str] = Field(default_factory=list)


class SkillsGroup(BaseModel):
    """A category of skills (e.g. "Programming languages")."""

    category: str = ""
    skills: List[str] = Field(default_factory=list)


class ProjectItem(BaseModel):
    name: str = ""
    description: str = ""
    technologies: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    github_url: str = ""
    live_url: str = ""


class CertificationItem(BaseModel):
    name: str = ""
    issuing_organization: str = ""
    date: str = ""
    credential_url: str = ""


class AchievementItem(BaseModel):
    title: str = ""
    description: str = ""
    date: str = ""


class LinkItem(BaseModel):
    label: str = ""
    url: str = ""


# ----------------------------------------------------------------
# Resume
# ----------------------------------------------------------------


class Resume(BaseModel):
    """The complete structured resume.

    Every list defaults to empty so the parser / editor can
    populate fields incrementally. A field that the parser could
    not extract stays empty — the user fills it in or the LLM
    helps suggest wording (but never invents facts).
    """

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    experience: List[ExperienceItem] = Field(default_factory=list)
    education: List[EducationItem] = Field(default_factory=list)
    skills: List[SkillsGroup] = Field(default_factory=list)
    projects: List[ProjectItem] = Field(default_factory=list)
    certifications: List[CertificationItem] = Field(default_factory=list)
    achievements: List[AchievementItem] = Field(default_factory=list)
    links: List[LinkItem] = Field(default_factory=list)

    def skill_list_flat(self) -> List[str]:
        """Return a flat list of every skill across categories."""
        out: list = []
        for group in self.skills:
            out.extend(s for s in group.skills if s)
        return out


# ----------------------------------------------------------------
# API request / response models
# ----------------------------------------------------------------


class ResumeSummary(BaseModel):
    """Lightweight summary used by the dashboard / library list."""

    id: str
    title: str
    target_role: str = ""
    updated_at: Optional[str] = None
    created_at: Optional[str] = None
    source_type: str = "manual"  # 'manual' | 'uploaded_pdf' | 'uploaded_docx'


class ResumeCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    target_role: str = Field(default="", max_length=200)


class ResumeUpdateRequest(BaseModel):
    title: Optional[str] = None
    target_role: Optional[str] = None
    resume: Optional[Resume] = None


class ResumeResponse(BaseModel):
    id: str
    title: str
    target_role: str = ""
    source_type: str = "manual"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    resume: Resume = Field(default_factory=Resume)


class ResumeUploadResponse(BaseModel):
    """Returned by ``POST /api/v1/resumes/upload``.

    The deterministic parser produces a best-effort :class:`Resume`
    that the user can review and edit before saving.
    """

    resume: Resume
    parser_warnings: List[str] = Field(default_factory=list)
    detected_sections: List[str] = Field(default_factory=list)
    raw_text_preview: str = ""


class ParseRequest(BaseModel):
    """Optional explicit text input for parsing (e.g. pasted resume)."""

    text: str = Field(..., min_length=1, max_length=200_000)


class JobAnalysisRequest(BaseModel):
    """ATS analyzer input — the resume id and the JD text."""

    job_title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    job_description: str = Field(..., min_length=1, max_length=200_000)


# ----------------------------------------------------------------
# ATS analysis output
# ----------------------------------------------------------------


class ATSScoreBreakdown(BaseModel):
    keyword_match: int = 0
    skills_match: int = 0
    experience_relevance: int = 0
    education_relevance: int = 0
    title_alignment: int = 0
    formatting_readability: int = 0
    section_completeness: int = 0

    @property
    def overall(self) -> int:
        # Simple average; the deterministic analyzer exposes the
        # breakdown to the user so they can see *why* a score is
        # what it is.
        vals = [
            self.keyword_match,
            self.skills_match,
            self.experience_relevance,
            self.education_relevance,
            self.title_alignment,
            self.formatting_readability,
            self.section_completeness,
        ]
        return round(sum(vals) / len(vals)) if vals else 0


class ATSImprovementItem(BaseModel):
    title: str
    detail: str
    priority: str = "medium"  # 'high' | 'medium' | 'low'


class JDAnalysis(BaseModel):
    """Structured extraction of the Job Description.

    Produced by a deterministic parser (no LLM). The LLM may be
    used to surface implicit skills ("Cloud" → "AWS") but every
    surfaced field must be present in the JD text.
    """

    role_title: str = ""
    company: str = ""
    domain: str = ""
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    experience_years: str = ""
    education: str = ""
    important_keywords: List[str] = Field(default_factory=list)


class ATSAnalysis(BaseModel):
    """The persisted result of an ATS analysis."""

    id: str
    resume_id: str
    job_title: str = ""
    company: str = ""
    overall_score: int = 0
    breakdown: ATSScoreBreakdown = Field(default_factory=ATSScoreBreakdown)
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    related_keywords: List[str] = Field(default_factory=list)
    jd_analysis: JDAnalysis = Field(default_factory=JDAnalysis)
    improvements: List[ATSImprovementItem] = Field(default_factory=list)
    created_at: Optional[str] = None


class ResumeVersionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    source_resume_id: str


# ----------------------------------------------------------------
# LinkedIn bridge
# ----------------------------------------------------------------


class LinkedInFromResumeRequest(BaseModel):
    """Build a LinkedIn post draft from a resume section.

    The actual writing is delegated to the existing
    :class:`WorkflowService` (Phase 5 source-aware Writer +
    Reviewer) — the resume data is converted into a source
    context the Writer consumes as grounding.
    """

    resume_id: str
    post_type: str = Field(
        default="project_launch",
        description=(
            "One of: project_launch, career_achievement, learning_journey, "
            "job_experience, certification, technical_deep_dive, career_milestone."
        ),
    )
    tone: str = Field(
        default="professional",
        description="One of: professional, storytelling, educational, founder, opinion.",
    )
    section: str = Field(
        default="",
        description=(
            "Optional section id to focus on (project, achievement, "
            "experience, certification). Empty = whole resume."
        ),
    )
    section_id: str = Field(
        default="",
        description=(
            "Optional id within the section (e.g. a specific project name). "
            "Empty = pick the first item in the section."
        ),
    )


class LinkedInFromResumeResponse(BaseModel):
    draft_id: str
    approval_token: str
    source_url: Optional[str] = None
    source_type: str = "resume_section"
    source_label: str = ""


__all__ = [
    "AchievementItem",
    "ATSAnalysis",
    "ATSImprovementItem",
    "ATSScoreBreakdown",
    "CertificationItem",
    "EducationItem",
    "ExperienceItem",
    "JDAnalysis",
    "JobAnalysisRequest",
    "LinkedInFromResumeRequest",
    "LinkedInFromResumeResponse",
    "LinkItem",
    "ParseRequest",
    "PersonalInfo",
    "ProjectItem",
    "Resume",
    "ResumeCreateRequest",
    "ResumeResponse",
    "ResumeSummary",
    "ResumeUpdateRequest",
    "ResumeUploadResponse",
    "ResumeVersionCreateRequest",
    "SkillsGroup",
]
