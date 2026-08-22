"""Resume service — Phase 10.

Orchestrates the resume CRUD, the deterministic parser, the
file-upload path, the ATS analyzer, the LinkedIn bridge, and
the version-copy workflow.

Every public method is user-scoped: a caller cannot read, modify,
or delete another user's resume or analysis. The repository
methods return ``None`` (or empty) for cross-user access and the
API layer responds with 404 — never 403, to avoid leaking
existence.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional

from backend.app.models.resume import (
    JobAnalysisRequest,
    LinkedInFromResumeRequest,
    LinkedInFromResumeResponse,
    Resume,
    ResumeCreateRequest,
    ResumeUpdateRequest,
    ResumeUploadResponse,
    ResumeVersionCreateRequest,
)
from backend.app.repositories.resume_repository import (
    ResumeRepository,
    analysis_doc_to_response,
    resume_doc_to_response,
)
from backend.app.services import ats_analyzer
from backend.app.services.resume_parser import parse_resume_text
from backend.app.services.resume_to_linkedin import build_resume_source_context

logger = logging.getLogger(__name__)


class ResumeServiceError(Exception):
    """User-facing service error. The HTTP layer maps ``code`` to
    a status. The ``message`` is safe to surface to the UI."""

    def __init__(self, message: str, *, code: str = "resume_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ResumeService:
    def __init__(self, repo: ResumeRepository) -> None:
        self.repo = repo

    # ----------------------------------------------------------------
    # CRUD
    # ----------------------------------------------------------------

    async def create(self, *, user_id: str, payload: ResumeCreateRequest) -> dict:
        if not user_id:
            raise ResumeServiceError("Unauthorized.", code="unauthorized")
        doc = await self.repo.create(
            user_id=user_id,
            title=payload.title.strip(),
            target_role=(payload.target_role or "").strip(),
            source_type="manual",
            resume=Resume(),
        )
        return resume_doc_to_response(doc)

    async def get(self, *, user_id: str, resume_id: str) -> Optional[dict]:
        doc = await self.repo.get(user_id=user_id, resume_id=resume_id)
        if not doc:
            return None
        return resume_doc_to_response(doc)

    async def list(self, *, user_id: str, limit: int = 50) -> List[dict]:
        docs = await self.repo.list(user_id=user_id, limit=limit)
        return [resume_doc_to_response(d) for d in docs]

    async def update(
        self, *, user_id: str, resume_id: str, payload: ResumeUpdateRequest
    ) -> Optional[dict]:
        updates: dict = {}
        if payload.title is not None:
            title = payload.title.strip()
            if not title:
                raise ResumeServiceError("Title cannot be empty.", code="invalid_input")
            updates["title"] = title
        if payload.target_role is not None:
            updates["target_role"] = payload.target_role.strip()
        if payload.resume is not None:
            updates["resume"] = payload.resume.model_dump()
        if not updates:
            return await self.get(user_id=user_id, resume_id=resume_id)
        doc = await self.repo.update(
            user_id=user_id, resume_id=resume_id, updates=updates
        )
        if not doc:
            return None
        return resume_doc_to_response(doc)

    async def delete(self, *, user_id: str, resume_id: str) -> bool:
        return await self.repo.delete(user_id=user_id, resume_id=resume_id)

    async def create_version(
        self, *, user_id: str, payload: ResumeVersionCreateRequest
    ) -> Optional[dict]:
        doc = await self.repo.create_version(
            user_id=user_id,
            source_resume_id=payload.source_resume_id,
            title=payload.title.strip(),
        )
        if not doc:
            return None
        return resume_doc_to_response(doc)

    # ----------------------------------------------------------------
    # Parse
    # ----------------------------------------------------------------

    async def parse_text(self, *, text: str) -> ResumeUploadResponse:
        resume, warnings = parse_resume_text(text or "")
        detected = [
            "personal", "summary", "experience", "education", "skills",
            "projects", "certifications", "achievements", "links",
        ]
        # Only list sections that produced a non-empty body. We
        # approximate this by checking the original keys we set in
        # the parser.
        detected_present: list = []
        if resume.personal.full_name or resume.personal.email:
            detected_present.append("personal")
        if resume.summary:
            detected_present.append("summary")
        if resume.experience:
            detected_present.append("experience")
        if resume.education:
            detected_present.append("education")
        if resume.skill_list_flat():
            detected_present.append("skills")
        if resume.projects:
            detected_present.append("projects")
        if resume.certifications:
            detected_present.append("certifications")
        if resume.achievements:
            detected_present.append("achievements")
        if resume.links:
            detected_present.append("links")
        return ResumeUploadResponse(
            resume=resume,
            parser_warnings=warnings,
            detected_sections=detected_present or detected,
            raw_text_preview=(text or "")[:1200],
        )

    # ----------------------------------------------------------------
    # ATS
    # ----------------------------------------------------------------

    async def run_ats_analysis(
        self, *, user_id: str, resume_id: str, payload: JobAnalysisRequest
    ) -> dict:
        from backend.app.models.resume import ATSAnalysis

        resume_doc = await self.repo.get(user_id=user_id, resume_id=resume_id)
        if not resume_doc:
            raise ResumeServiceError("Resume not found.", code="not_found")
        resume = Resume(**(resume_doc.get("resume") or {}))
        analysis = ats_analyzer.analyze_resume_against_jd(
            resume, payload.job_description
        )
        analysis.id = ""  # filled in by repo
        analysis.resume_id = resume_id
        analysis.job_title = (payload.job_title or "").strip()
        analysis.company = (payload.company or "").strip()
        doc = await self.repo.save_analysis(
            user_id=user_id,
            resume_id=resume_id,
            analysis=analysis,
        )
        return analysis_doc_to_response(doc)

    async def get_analysis(
        self, *, user_id: str, analysis_id: str
    ) -> Optional[dict]:
        doc = await self.repo.get_analysis(
            user_id=user_id, analysis_id=analysis_id
        )
        if not doc:
            return None
        return analysis_doc_to_response(doc)

    async def list_analyses_for_resume(
        self, *, user_id: str, resume_id: str
    ) -> List[dict]:
        docs = await self.repo.list_analyses_for_resume(
            user_id=user_id, resume_id=resume_id
        )
        return [analysis_doc_to_response(d) for d in docs]

    async def list_recent_analyses(
        self, *, user_id: str, limit: int = 10
    ) -> List[dict]:
        docs = await self.repo.list_recent_analyses(user_id=user_id, limit=limit)
        return [analysis_doc_to_response(d) for d in docs]

    # ----------------------------------------------------------------
    # LinkedIn bridge
    # ----------------------------------------------------------------

    def build_linkedin_source_context(
        self, *, resume: Resume, payload: LinkedInFromResumeRequest
    ) -> dict:
        try:
            return build_resume_source_context(
                resume=resume,
                post_type=payload.post_type,
                tone=payload.tone,
                section=payload.section,
                section_id=payload.section_id,
            )
        except ValueError as e:
            raise ResumeServiceError(str(e), code="invalid_input")

    # ----------------------------------------------------------------
    # Dashboard
    # ----------------------------------------------------------------

    async def dashboard_stats(self, *, user_id: str) -> dict:
        docs = await self.repo.list(user_id=user_id, limit=200)
        analyses = await self.repo.list_recent_analyses(user_id=user_id, limit=50)
        scores = [a.get("overall_score", 0) for a in analyses if a.get("overall_score")]
        avg = round(sum(scores) / len(scores)) if scores else 0
        return {
            "resume_count": len(docs),
            "average_ats_score": avg,
            "recent_resumes": [
                {
                    "id": d["_id"],
                    "title": d.get("title", ""),
                    "target_role": d.get("target_role", ""),
                    "updated_at": d.get("updated_at").isoformat()
                    if d.get("updated_at")
                    else None,
                }
                for d in docs[:5]
            ],
            "recent_analyses": [
                {
                    "id": a["_id"],
                    "resume_id": a.get("resume_id"),
                    "job_title": a.get("job_title", ""),
                    "company": a.get("company", ""),
                    "overall_score": a.get("overall_score", 0),
                    "created_at": a.get("created_at").isoformat()
                    if a.get("created_at")
                    else None,
                }
                for a in analyses[:5]
            ],
        }


__all__ = ["ResumeService", "ResumeServiceError"]
