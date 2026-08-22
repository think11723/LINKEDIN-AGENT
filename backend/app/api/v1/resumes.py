"""Resume API endpoints — Phase 10.

REST surface for the AI Resume Studio. All routes are mounted
under ``/api/v1/resumes`` and require Firebase authentication
(``get_current_user``). User-isolation is enforced at the repository
layer: a cross-user access returns ``None`` and the API responds
with 404 (never 403, to avoid leaking existence).

Routes
------

* ``POST   /api/v1/resumes``                          — create a blank resume
* ``GET    /api/v1/resumes``                          — list the caller's resumes
* ``GET    /api/v1/resumes/dashboard``                — dashboard summary
* ``GET    /api/v1/resumes/{id}``                     — read a single resume
* ``PUT    /api/v1/resumes/{id}``                     — update a resume
* ``DELETE /api/v1/resumes/{id}``                     — delete a resume
* ``POST   /api/v1/resumes/{id}/versions``            — create an optimized copy
* ``POST   /api/v1/resumes/upload``                   — upload a PDF / DOCX
* ``POST   /api/v1/resumes/parse``                    — parse raw text
* ``POST   /api/v1/resumes/{id}/ats/analyze``         — run an ATS analysis
* ``GET    /api/v1/resumes/{id}/ats/analyses``        — list a resume's analyses
* ``GET    /api/v1/resumes/ats/analyses/{analysis_id}`` — read a single analysis
* ``POST   /api/v1/resumes/{id}/linkedin``            — create a LinkedIn post

The upload endpoint consumes ``multipart/form-data`` with a single
``file`` field. PDF and DOCX are accepted; everything else is
rejected. The file is parsed by the deterministic text extractor
and then the deterministic resume parser produces a best-effort
:class:`Resume` the user reviews and edits in the editor.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.app.api.deps import (
    get_approval_repository,
    get_audit_repository,
    get_draft_repository,
    get_resume_service,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.models.resume import (
    JobAnalysisRequest,
    LinkedInFromResumeRequest,
    LinkedInFromResumeResponse,
    ParseRequest,
    Resume,
    ResumeCreateRequest,
    ResumeResponse,
    ResumeUpdateRequest,
    ResumeUploadResponse,
    ResumeVersionCreateRequest,
)
from backend.app.services.file_extraction import (
    FileExtractionError,
    extract_text,
)
from backend.app.services.resume_service import ResumeService, ResumeServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------


async def _load_resume(service: ResumeService, *, user_id: str, resume_id: str):
    resume = await service.get(user_id=user_id, resume_id=resume_id)
    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )
    return resume


def _map_service_error(e: ResumeServiceError) -> HTTPException:
    code = e.code or "resume_error"
    if code in (
        "not_found",
        "approval_record_not_found",
    ):
        status_code = status.HTTP_404_NOT_FOUND
    elif code in (
        "invalid_input",
        "unsupported_format",
        "empty_file",
        "file_too_large",
        "bad_pdf",
        "bad_docx",
        "parser_unavailable",
    ):
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code, detail=e.message)


# ----------------------------------------------------------------
# Routes
# ----------------------------------------------------------------


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume(
    payload: ResumeCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    try:
        return await service.create(user_id=user.uid, payload=payload)
    except ResumeServiceError as e:
        raise _map_service_error(e)


@router.get("", response_model=List[ResumeResponse])
async def list_resumes(
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    return await service.list(user_id=user.uid)


@router.get("/dashboard")
async def resume_dashboard(
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    return await service.dashboard_stats(user_id=user.uid)


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    return await _load_resume(service, user_id=user.uid, resume_id=resume_id)


@router.put("/{resume_id}", response_model=ResumeResponse)
async def update_resume(
    resume_id: str,
    payload: ResumeUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    try:
        updated = await service.update(
            user_id=user.uid, resume_id=resume_id, payload=payload
        )
    except ResumeServiceError as e:
        raise _map_service_error(e)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )
    return updated


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    deleted = await service.delete(user_id=user.uid, resume_id=resume_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )
    return None


@router.post(
    "/{resume_id}/versions",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_resume_version(
    resume_id: str,
    payload: ResumeVersionCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    # Override the source_resume_id from the URL to prevent
    # arbitrary version copies from another user's resume.
    payload = ResumeVersionCreateRequest(
        title=payload.title, source_resume_id=resume_id
    )
    try:
        created = await service.create_version(
            user_id=user.uid, payload=payload
        )
    except ResumeServiceError as e:
        raise _map_service_error(e)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source resume not found.",
        )
    return created


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_resume(
    file: UploadFile = File(...),
    title: str = Form(...),
    target_role: str = Form(""),
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    raw = await file.read()
    try:
        text, safe_name = extract_text(
            file.content_type or "", file.filename or "", raw
        )
    except FileExtractionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=e.message
        )
    parsed = await service.parse_text(text=text)
    try:
        doc = await service.repo.create(
            user_id=user.uid,
            title=(title or safe_name or "Untitled resume").strip(),
            target_role=(target_role or "").strip(),
            source_type=("uploaded_pdf" if safe_name.lower().endswith(".pdf") else "uploaded_docx"),
            resume=parsed.resume,
        )
    finally:
        # Always close the upload to release the file handle.
        try:
            await file.close()
        except Exception:  # noqa: BLE001
            pass
    from backend.app.repositories.resume_repository import (
        resume_doc_to_response,
    )
    return ResumeUploadResponse(
        resume=doc.get("resume") or {},
        parser_warnings=parsed.parser_warnings,
        detected_sections=parsed.detected_sections,
        raw_text_preview=parsed.raw_text_preview,
    )


@router.post("/parse", response_model=ResumeUploadResponse)
async def parse_resume_text(
    payload: ParseRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    return await service.parse_text(text=payload.text)


@router.post(
    "/{resume_id}/ats/analyze",
)
async def ats_analyze(
    resume_id: str,
    payload: JobAnalysisRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    try:
        return await service.run_ats_analysis(
            user_id=user.uid, resume_id=resume_id, payload=payload
        )
    except ResumeServiceError as e:
        raise _map_service_error(e)


@router.get("/{resume_id}/ats/analyses")
async def list_ats_analyses(
    resume_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    # Ownership check: ensure the resume is owned by the user.
    owned = await service.get(user_id=user.uid, resume_id=resume_id)
    if not owned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resume not found.",
        )
    return await service.list_analyses_for_resume(
        user_id=user.uid, resume_id=resume_id
    )


@router.get("/ats/analyses/{analysis_id}")
async def get_ats_analysis(
    analysis_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
):
    analysis = await service.get_analysis(
        user_id=user.uid, analysis_id=analysis_id
    )
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found.",
        )
    return analysis


@router.post(
    "/{resume_id}/linkedin",
    response_model=LinkedInFromResumeResponse,
)
async def create_linkedin_from_resume(
    resume_id: str,
    payload: LinkedInFromResumeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
    drafts = Depends(get_draft_repository),
    approvals = Depends(get_approval_repository),
    audit = Depends(get_audit_repository),
):
    """Build a LinkedIn post draft from a resume section.

    Flow:
        1. Load the resume (user-scoped).
        2. Build the source context via the deterministic
           resume → source-context builder.
        3. Call the existing WorkflowService (Phase 5 source-aware
           Writer + Reviewer). NO duplicate writer.
        4. The workflow result becomes a normal Draft (same code
           path as topic / URL drafts).
        5. Return the draft id + approval token so the UI can
           navigate to the existing draft viewer.
    """
    from backend.app.services.workflow_service import WorkflowService
    from shared.schemas import GenerateContentRequest

    # Ownership / fetch
    resume_doc = await service.get(user_id=user.uid, resume_id=resume_id)
    if not resume_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found."
        )
    resume = Resume(**(resume_doc.get("resume") or {}))

    # Build the source context from the resume.
    try:
        source_context = service.build_linkedin_source_context(
            resume=resume, payload=payload
        )
    except ResumeServiceError as e:
        raise _map_service_error(e)

    # Run the existing writer + reviewer pipeline. Reuse the same
    # seam the synchronous /content/generate path uses (Phase 5).
    workflow = WorkflowService()
    request = GenerateContentRequest(
        topic=(
            f"{source_context['source_title']} — {payload.post_type}"
        ),
        image_path=None,
    )
    # Apply a no-op adapter so the workflow can construct the
    # research package. The writer reads ``source`` (our new
    # source context) which carries the resume data.
    workflow_result = await workflow.generate_content(
        request, research_package=None, source=source_context
    )

    # Persist as a normal draft — same path as topic / URL drafts.
    # We delegate to _persist_result via a tiny inline call here.
    from backend.app.api.v1.content import _persist_result

    response = await _persist_result(
        user=user,
        workflow_result=workflow_result,
        drafts=drafts,
        approvals=approvals,
        audit=audit,
        # Tag the source so the Draft Viewer attribution and the
        # email render the resume as the source.
        source_url=None,
        source_metadata={
            "source_type": "resume_section",
            "section": payload.section or "",
            "section_id": payload.section_id or "",
            "post_type": payload.post_type,
            "tone": payload.tone,
            "resume_id": resume_id,
        },
    )
    return LinkedInFromResumeResponse(
        draft_id=response.draft_id,
        approval_token=response.approval_token or "",
        source_url=None,
        source_type="resume_section",
        source_label=(
            f"Resume · {source_context.get('source_title', 'section')}"
        ),
    )


__all__ = ["router"]
