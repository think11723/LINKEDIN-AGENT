"""Content API endpoints for the web application.

Now requires Firebase authentication. Generated drafts are persisted in
MongoDB owned by the authenticated user, and ``draft_id`` +
``approval_token`` are surfaced at the top level of the response.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.app.api.deps import (
    get_approval_repository,
    get_audit_repository,
    get_draft_repository,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import (
    ApprovalRepository,
    AuditRepository,
    DraftRepository,
)
from backend.app.services.workflow_service import WorkflowService
from shared.schemas import GenerateContentRequest, GenerateContentResponse

router = APIRouter(prefix="/api/v1/content", tags=["content"])


def get_workflow_service() -> WorkflowService:
    return WorkflowService()


@router.post("/generate", response_model=GenerateContentResponse)
async def generate_content(
    payload: GenerateContentRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
    drafts: DraftRepository = Depends(get_draft_repository),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> GenerateContentResponse:
    """Generate a LinkedIn draft using the existing LangGraph workflow.

    The result is persisted in MongoDB owned by the authenticated user.

    Phase 8A / P0-1: the global exception handler in
    ``backend.app.core.error_handlers`` produces a safe envelope for any
    uncaught exception — never ``str(exc)``.
    """
    # WorkflowService raises HTTPException for empty topics; re-raise.
    workflow_result = service.generate_content(payload)

    response = workflow_result
    try:
        response = await _persist_result(
            user=user,
            workflow_result=workflow_result,
            drafts=drafts,
            approvals=approvals,
            audit=audit,
        )
    except Exception:  # pragma: no cover - defensive
        # Persistence failure must not mask the workflow output. The
        # global exception handler logs the traceback server-side; here
        # we just continue and return the workflow result unchanged.
        import logging
        logging.getLogger(__name__).exception(
            "Persistence failed for generated draft; returning workflow result."
        )

    return response


async def _persist_result(
    *,
    user: AuthenticatedUser,
    workflow_result: GenerateContentResponse,
    drafts: DraftRepository,
    approvals: ApprovalRepository,
    audit: AuditRepository,
) -> GenerateContentResponse:
    """Persist the generated draft + create an approval token owned by the user."""
    if not workflow_result.final_post:
        return workflow_result

    draft_id = uuid.uuid4().hex
    approval = await approvals.create(user_id=user.uid, draft_id=draft_id)

    title = workflow_result.final_post.title or workflow_result.topic
    content = workflow_result.final_post.content or ""
    hashtags = workflow_result.final_post.hashtags or []

    review_score = None
    review_feedback = None
    if workflow_result.review_scores:
        try:
            review_score = int(workflow_result.review_scores.get("overall", 0)) or None
        except (TypeError, ValueError):
            review_score = None
    if workflow_result.review_feedback:
        review_feedback = str(workflow_result.review_feedback)

    research_summary = None
    if workflow_result.metadata:
        package = workflow_result.metadata.get("research_package") or {}
        research_summary = package.get("summary")

    # Phase 8A / P0-5: persist the provider/model used by writer + reviewer.
    meta = dict(workflow_result.metadata or {})
    llm_meta: dict[str, str] = {}
    if "writer_provider" in meta:
        llm_meta["writer_provider"] = meta["writer_provider"]
    if "writer_model" in meta:
        llm_meta["writer_model"] = meta["writer_model"]
    if "reviewer_provider" in meta:
        llm_meta["reviewer_provider"] = meta["reviewer_provider"]
    if "reviewer_model" in meta:
        llm_meta["reviewer_model"] = meta["reviewer_model"]

    draft_doc = await drafts.create(
        user_id=user.uid,
        draft_id=draft_id,
        topic=workflow_result.topic,
        title=title,
        content=content,
        hashtags=hashtags,
        image_path=workflow_result.final_post.image_path,
        review_score=review_score,
        review_feedback=review_feedback,
        research_summary=research_summary,
        status="draft" if not workflow_result.approved else "approved",
        approval_token=approval["_id"],
        metadata={"llm": llm_meta} if llm_meta else None,
    )

    await audit.log(
        user_id=user.uid,
        event_type="DRAFT_GENERATED",
        description=title,
        details={
            "draft_id": draft_id,
            "approved": workflow_result.approved,
            "iterations": workflow_result.iterations,
        },
    )

    payload = workflow_result.model_dump(exclude_none=True)
    payload["draft_id"] = draft_id
    payload["approval_token"] = approval["_id"]
    payload["draft"] = {
        "draft_id": draft_doc["_id"],
        "title": title,
        "topic": draft_doc.get("topic"),
        "content": content,
        "hashtags": hashtags,
        "status": draft_doc.get("status"),
        "approval_token": approval["_id"],
        "created_at": (
            draft_doc["created_at"].isoformat()
            if hasattr(draft_doc.get("created_at"), "isoformat")
            else draft_doc.get("created_at")
        ),
    }
    return GenerateContentResponse.model_validate(payload)