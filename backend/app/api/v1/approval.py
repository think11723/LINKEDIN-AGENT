"""Approval HTTP endpoints — user-scoped, Mongo-backed.

The legacy ``approval/store.py`` + JSON file store is preserved for the
CLI. The SaaS path here uses the Mongo-backed ``ApprovalRepository``.

Workflow:
  * POST /api/v1/approval/approve — when no ``schedule_time`` is
    provided, the approved draft is published immediately via the
    shared publishing service. When ``schedule_time`` is provided,
    the draft is enqueued for later publication by the scheduler.
  * The publishing service is the single source of truth for posting
    to LinkedIn — this route does not duplicate any LinkedIn code.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.api.deps import (
    get_approval_repository,
    get_audit_repository,
    get_draft_repository,
    get_scheduler_repository,
)
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import (
    ApprovalRepository,
    AuditRepository,
    DraftRepository,
    SchedulerRepository,
)
from backend.app.services.publishing import publish_now
from shared.schemas import (
    ApprovalActionResponse,
    ApprovalDraftResponse,
    ApprovalQueueItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/approval", tags=["approval"])


class ApprovalActionRequest(BaseModel):
    token: Optional[str] = None
    schedule_time: Optional[str] = None


class ApprovalEditRequest(BaseModel):
    draft_id: str
    title: Optional[str] = None
    content: Optional[str] = None
    hashtags: Optional[list[str]] = None


@router.get("/queue", response_model=list[ApprovalQueueItem])
async def get_approval_queue(
    user: AuthenticatedUser = Depends(get_current_user),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    drafts: DraftRepository = Depends(get_draft_repository),
) -> list[ApprovalQueueItem]:
    pending = await approvals.list_pending_for_user(user.uid, limit=200)
    items: list[ApprovalQueueItem] = []
    for record in pending:
        draft = await drafts.get(user.uid, record["draft_id"])
        if not draft:
            continue
        items.append(
            ApprovalQueueItem(
                draft_id=record["draft_id"],
                title=draft.get("title", ""),
                topic=draft.get("topic", ""),
                token=record["token"],
                status=record.get("status", "pending"),
                review_score=draft.get("review_score") or 0,
                created_at=(
                    record["created_at"].isoformat()
                    if hasattr(record.get("created_at"), "isoformat")
                    else None
                ),
            )
        )
    return items


@router.get("/draft", response_model=ApprovalDraftResponse)
async def get_draft_by_token(
    token: str,
    user: AuthenticatedUser = Depends(get_current_user),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    drafts: DraftRepository = Depends(get_draft_repository),
) -> ApprovalDraftResponse:
    approval = await approvals.get(user.uid, token)
    if not approval:
        # Cross-user or non-existent token — same 404 to avoid leaking existence.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval token not found")
    draft = await drafts.get(user.uid, approval["draft_id"])
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval token not found")
    return ApprovalDraftResponse(
        draft_id=draft["_id"],
        title=draft.get("title", ""),
        content=draft.get("content", ""),
        hashtags=draft.get("hashtags", []),
        review_score=draft.get("review_score") or 0,
        review_feedback=draft.get("review_feedback") or "",
        research_summary=draft.get("research_summary"),
        approval_token=token,
        published_at=(
            draft["published_at"].isoformat()
            if hasattr(draft.get("published_at"), "isoformat")
            else draft.get("published_at")
        ),
        scheduled_publish_time=(
            draft["scheduled_publish_time"].isoformat()
            if hasattr(draft.get("scheduled_publish_time"), "isoformat")
            else draft.get("scheduled_publish_time")
        ),
        status=approval.get("status", "pending"),
    )


@router.get("/published", response_model=list[dict])
async def get_published_drafts(
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
) -> list[dict]:
    items = await drafts.list_published(user.uid, limit=200)
    return [
        {
            "draft_id": item.get("_id"),
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "hashtags": item.get("hashtags", []),
            "published_at": (
                item["published_at"].isoformat()
                if hasattr(item.get("published_at"), "isoformat")
                else item.get("published_at")
            ),
            "linkedin_post_id": item.get("linkedin_post_id"),
        }
        for item in items
    ]


@router.post("/approve", response_model=ApprovalActionResponse)
async def approve_draft(
    payload: ApprovalActionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    drafts: DraftRepository = Depends(get_draft_repository),
    scheduler: SchedulerRepository = Depends(get_scheduler_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> ApprovalActionResponse:
    if not payload.token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="token is required")

    record = await approvals.approve(user.uid, payload.token)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval token not found")

    draft = await drafts.get(user.uid, record["draft_id"])

    if payload.schedule_time:
        try:
            schedule_dt = datetime.fromisoformat(payload.schedule_time.replace("Z", "+00:00"))
            if schedule_dt.tzinfo is None:
                schedule_dt = schedule_dt.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid schedule_time",
            ) from exc

        await scheduler.create(
            user_id=user.uid,
            draft_id=record["draft_id"],
            title=(draft or {}).get("title", ""),
            content=(draft or {}).get("content", ""),
            hashtags=(draft or {}).get("hashtags", []),
            image_path=(draft or {}).get("image_path"),
            scheduled_time=schedule_dt,
        )
        await audit.log(
            user_id=user.uid,
            event_type="APPROVAL_SCHEDULED",
            description=(draft or {}).get("title", ""),
            details={"draft_id": record["draft_id"], "schedule_time": payload.schedule_time},
        )
        return ApprovalActionResponse(
            success=True,
            message=f"Draft approved and scheduled for {schedule_dt.isoformat()}",
        )

    await audit.log(
        user_id=user.uid,
        event_type="APPROVAL_APPROVED",
        description=(draft or {}).get("title", ""),
        details={"draft_id": record["draft_id"]},
    )

    # Idempotency: if the draft is already published, do NOT re-publish.
    # This protects against double-clicks and against re-clicking
    # Approve on an approval record that has already been approved
    # once (the second approve returns the existing approval record
    # unchanged — see ApprovalRepository.approve).
    if (draft or {}).get("published_at"):
        return ApprovalActionResponse(
            success=True,
            message="Post was already approved and published.",
        )

    # No schedule_time → publish immediately via the shared publishing
    # service. This is the desired product workflow: human Approve on
    # the Approval page both records the human-review decision AND
    # triggers the publish.
    publish_result = await publish_now(user.uid, record["draft_id"])

    if publish_result.success:
        return ApprovalActionResponse(
            success=True,
            message="Post approved and published successfully.",
        )

    # Publishing failed AFTER approval succeeded. The approval is
    # recorded; the operator must retry the publish separately. Do NOT
    # report success.
    await audit.log(
        user_id=user.uid,
        event_type="PUBLISH_FAILED_AFTER_APPROVAL",
        description=(draft or {}).get("title", ""),
        details={
            "draft_id": record["draft_id"],
            "error": publish_result.error_message or "unknown",
            "already_published": publish_result.already_published,
        },
    )
    return ApprovalActionResponse(
        success=False,
        message=(
            "Post was approved but publishing to LinkedIn failed. "
            "Use the Draft viewer to retry."
        ),
    )


@router.post("/reject", response_model=ApprovalActionResponse)
async def reject_draft(
    payload: ApprovalActionRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    drafts: DraftRepository = Depends(get_draft_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> ApprovalActionResponse:
    if not payload.token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="token is required")

    record = await approvals.reject(user.uid, payload.token)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval token not found")

    draft = await drafts.get(user.uid, record["draft_id"])
    await audit.log(
        user_id=user.uid,
        event_type="APPROVAL_REJECTED",
        description=(draft or {}).get("title", ""),
        details={"draft_id": record["draft_id"]},
    )
    return ApprovalActionResponse(success=True, message="Draft rejected")


@router.post("/edit", response_model=ApprovalActionResponse)
async def edit_draft(
    payload: ApprovalEditRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> ApprovalActionResponse:
    existing = await drafts.get(user.uid, payload.draft_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if existing.get("published_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published drafts cannot be edited",
        )

    updates: dict = {}
    if payload.title is not None:
        updates["title"] = payload.title
    if payload.content is not None:
        updates["content"] = payload.content
    if payload.hashtags is not None:
        updates["hashtags"] = payload.hashtags

    if not updates:
        return ApprovalActionResponse(success=True, message="No changes")

    # Phase 9: normalize approval-edit input through the canonical
    # LinkedIn normalizer so a user who pastes Markdown into a draft
    # edit still ends up with a LinkedIn-native stored draft. Same
    # canonical function as Writer + Reviewer + persist.
    if any(field in updates for field in ("title", "content", "hashtags")):
        from utils.linkedin_content import (
            normalize_title as _normalize_title,
            normalize_content as _normalize_content,
            normalize_hashtags as _normalize_hashtags,
        )
        if "title" in updates:
            updates["title"] = _normalize_title(updates["title"] or "")
        if "content" in updates:
            updates["content"] = _normalize_content(updates["content"] or "")
        if "hashtags" in updates:
            updates["hashtags"] = list(
                _normalize_hashtags(updates["hashtags"] or [])
            )

    doc = await drafts.update(user.uid, payload.draft_id, updates)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    await audit.log(
        user_id=user.uid,
        event_type="DRAFT_EDITED",
        description=doc.get("title", ""),
        details={"draft_id": payload.draft_id, "fields": list(updates.keys())},
    )
    return ApprovalActionResponse(success=True, message="Draft updated")