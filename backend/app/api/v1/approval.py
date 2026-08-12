"""Approval API endpoints for the frontend."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from approval.service import ApprovalService
from shared.schemas import (
    ApprovalActionResponse,
    ApprovalDraftResponse,
    ApprovalQueueItem,
)

router = APIRouter(prefix="/api/v1/approval", tags=["approval"])


@router.get("/queue", response_model=list[ApprovalQueueItem])
async def get_approval_queue() -> list[ApprovalQueueItem]:
    approval_service = ApprovalService()
    drafts = approval_service.store.storage.get_all_drafts()
    tokens = approval_service.store.storage.get_all_tokens()

    items: list[ApprovalQueueItem] = []
    for draft_data in drafts.values():
        draft = (
            draft_data
            if isinstance(draft_data, dict)
            else draft_data.model_dump()
        )
        token = (
            tokens.get(draft.get("approval_token"))
            if draft.get("approval_token")
            else None
        )
        if token is not None and token.status.value == "pending":
            items.append(
                ApprovalQueueItem(
                    draft_id=draft["draft_id"],
                    title=draft.get("title", ""),
                    topic=draft.get("topic", ""),
                    token=token.token,
                    status=token.status.value,
                    review_score=draft.get("review_score", 0),
                    created_at=draft.get("created_at"),
                )
            )
    return items


@router.get("/draft", response_model=ApprovalDraftResponse)
async def get_draft_by_token(token: str) -> ApprovalDraftResponse:
    approval_service = ApprovalService()
    draft = approval_service.store.get_draft_by_token(token)
    if not draft:
        raise HTTPException(status_code=404, detail="Approval token not found")

    return ApprovalDraftResponse(
        draft_id=draft.draft_id,
        title=draft.title,
        content=draft.content,
        hashtags=draft.hashtags,
        review_score=draft.review_score,
        review_feedback=draft.review_feedback,
        research_summary=draft.research_summary,
        approval_token=token,
        published_at=(
            draft.published_at.isoformat() if draft.published_at else None
        ),
        scheduled_publish_time=(
            draft.scheduled_publish_time.isoformat()
            if draft.scheduled_publish_time
            else None
        ),
        status="pending",
    )


@router.get("/published", response_model=list[dict])
async def get_published_drafts() -> list[dict]:
    approval_service = ApprovalService()
    drafts = approval_service.store.storage.get_all_drafts()

    published_items: list[dict] = []
    for draft_data in drafts.values():
        draft = (
            draft_data
            if isinstance(draft_data, dict)
            else draft_data.model_dump()
        )
        if draft.get("published_at"):
            published_items.append(
                {
                    "draft_id": draft.get("draft_id"),
                    "title": draft.get("title", ""),
                    "content": draft.get("content", ""),
                    "hashtags": draft.get("hashtags", []),
                    "published_at": draft.get("published_at"),
                    "linkedin_post_id": draft.get("linkedin_post_id"),
                }
            )

    return published_items


@router.post("/approve", response_model=ApprovalActionResponse)
async def approve_draft(payload: dict) -> ApprovalActionResponse:
    token = payload.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    schedule_time = None
    schedule_value = payload.get("schedule_time")
    if schedule_value:
        schedule_time = datetime.fromisoformat(schedule_value)

    approval_service = ApprovalService()
    success, message = approval_service.approve(token, schedule_time)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return ApprovalActionResponse(success=True, message=message)


@router.post("/reject", response_model=ApprovalActionResponse)
async def reject_draft(payload: dict) -> ApprovalActionResponse:
    token = payload.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="token is required")

    approval_service = ApprovalService()
    success, message = approval_service.reject(token)
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return ApprovalActionResponse(success=True, message=message)


@router.post("/edit", response_model=ApprovalActionResponse)
async def edit_draft(payload: dict) -> ApprovalActionResponse:
    draft_id = payload.get("draft_id")
    if not draft_id:
        raise HTTPException(status_code=400, detail="draft_id is required")

    title = payload.get("title")
    content = payload.get("content")
    hashtags = payload.get("hashtags") or []
    if not title or not content:
        raise HTTPException(
            status_code=400,
            detail="title and content are required",
        )

    approval_service = ApprovalService()
    success, message = approval_service.edit_draft(
        draft_id,
        title,
        content,
        hashtags,
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)

    return ApprovalActionResponse(success=True, message=message)
