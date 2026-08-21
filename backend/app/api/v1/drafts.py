"""Drafts CRUD router — Mongo-backed, user-scoped.

Cross-user access returns 404 (not 403) to avoid leaking existence.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

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

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])


class DraftResponse(BaseModel):
    id: str
    user_id: str
    topic: str
    title: str
    content: str
    hashtags: list[str] = []
    image_path: Optional[str] = None
    review_score: Optional[int] = None
    review_feedback: Optional[str] = None
    research_summary: Optional[str] = None
    status: str
    approval_token: Optional[str] = None
    approval_status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    published_at: Optional[str] = None
    linkedin_post_id: Optional[str] = None
    # Phase 8D / URL-to-LinkedIn. None for topic-mode drafts and all
    # pre-feature drafts; persisted only when the draft was generated
    # from a URL. The viewer surfaces these in the Status card.
    source_url: Optional[str] = None
    source_metadata: Optional[dict] = None


class DraftListResponse(BaseModel):
    items: list[DraftResponse]
    next_page: Optional[int] = None
    total: int


class DraftCreateRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    title: Optional[str] = None
    content: Optional[str] = None
    hashtags: list[str] = []
    image_path: Optional[str] = None
    review_score: Optional[int] = None
    review_feedback: Optional[str] = None
    research_summary: Optional[str] = None
    status: Optional[str] = "draft"


class DraftUpdateRequest(BaseModel):
    topic: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    hashtags: Optional[list[str]] = None
    image_path: Optional[str] = None
    review_score: Optional[int] = None
    review_feedback: Optional[str] = None
    research_summary: Optional[str] = None
    status: Optional[str] = None


def _to_response(doc: dict) -> DraftResponse:
    return DraftResponse.model_validate(
        {
            "id": doc["_id"],
            "user_id": doc["user_id"],
            "topic": doc.get("topic", ""),
            "title": doc.get("title", ""),
            "content": doc.get("content", ""),
            "hashtags": doc.get("hashtags", []),
            "image_path": doc.get("image_path"),
            "review_score": doc.get("review_score"),
            "review_feedback": doc.get("review_feedback"),
            "research_summary": doc.get("research_summary"),
            "status": doc.get("status", "draft"),
            "approval_token": doc.get("approval_token"),
            "approval_status": doc.get("approval_status"),
            "created_at": (
                doc["created_at"].isoformat()
                if hasattr(doc.get("created_at"), "isoformat")
                else doc.get("created_at")
            ),
            "updated_at": (
                doc["updated_at"].isoformat()
                if hasattr(doc.get("updated_at"), "isoformat")
                else doc.get("updated_at")
            ),
            "published_at": (
                doc["published_at"].isoformat()
                if hasattr(doc.get("published_at"), "isoformat")
                else doc.get("published_at")
            ),
            "linkedin_post_id": doc.get("linkedin_post_id"),
            "source_url": doc.get("source_url"),
            "source_metadata": doc.get("source_metadata"),
        }
    )


@router.get("", response_model=DraftListResponse)
async def list_drafts(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = None,
    sort_by: Optional[str] = Query(default="updated", pattern="^(updated|created|title)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
) -> DraftListResponse:
    skip = (page - 1) * page_size
    items = await drafts.list(
        user.uid,
        status=status_filter,
        search=search,
        sort_by=sort_by,
        skip=skip,
        limit=page_size,
    )
    total = await drafts.count(user.uid, status=status_filter)
    next_page = page + 1 if (skip + len(items)) < total else None
    return DraftListResponse(
        items=[_to_response(doc) for doc in items],
        next_page=next_page,
        total=total,
    )


@router.get("/{draft_id}", response_model=DraftResponse)
async def get_draft(
    draft_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
) -> DraftResponse:
    doc = await drafts.get(user.uid, draft_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return _to_response(doc)


@router.post("", response_model=DraftResponse, status_code=status.HTTP_201_CREATED)
async def create_draft(
    payload: DraftCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
    approvals: ApprovalRepository = Depends(get_approval_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> DraftResponse:
    draft_id = uuid.uuid4().hex
    # Phase 9: normalize before persisting so any code path
    # (manual create, URL-mode generation, future agents) produces the
    # same canonical LinkedIn-native content. Writer and Reviewer also
    # normalize — this is the final defense layer for ALL paths.
    from utils.linkedin_content import normalize_linkedin_post

    _normalized = normalize_linkedin_post(
        title=payload.title or payload.topic,
        content=payload.content or "",
        hashtags=payload.hashtags,
    )
    title = _normalized.title
    content = _normalized.content
    hashtags = list(_normalized.hashtags)

    approval = await approvals.create(user_id=user.uid, draft_id=draft_id)
    doc = await drafts.create(
        user_id=user.uid,
        draft_id=draft_id,
        topic=payload.topic,
        title=title,
        content=content,
        hashtags=hashtags,
        image_path=payload.image_path,
        review_score=payload.review_score,
        review_feedback=payload.review_feedback,
        research_summary=payload.research_summary,
        status=payload.status or "draft",
        approval_token=approval["_id"],
    )
    await audit.log(
        user_id=user.uid,
        event_type="DRAFT_CREATED",
        description=title or payload.topic,
        details={"draft_id": draft_id},
    )
    return _to_response(doc)


@router.put("/{draft_id}", response_model=DraftResponse)
async def update_draft(
    draft_id: str,
    payload: DraftUpdateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> DraftResponse:
    existing = await drafts.get(user.uid, draft_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    if existing.get("published_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published drafts cannot be edited",
        )

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _to_response(existing)

    # Phase 9: normalize manually-edited title / content / hashtags
    # through the same canonical LinkedIn normalizer so users can't
    # accidentally paste Markdown into a draft and have it persist
    # verbatim. The normalizer is idempotent + safe on plain text.
    from utils.linkedin_content import normalize_linkedin_post

    if any(field in updates for field in ("title", "content", "hashtags")):
        from utils.linkedin_content import (
            normalize_title as _normalize_title,
            normalize_content as _normalize_content,
            normalize_hashtags as _normalize_hashtags,
        )

        _merged_title = updates.get("title", existing.get("title"))
        _merged_content = updates.get("content", existing.get("content"))
        _merged_hashtags = updates.get("hashtags", existing.get("hashtags"))
        updates["title"] = _normalize_title(_merged_title or "")
        updates["content"] = _normalize_content(_merged_content or "")
        updates["hashtags"] = list(
            _normalize_hashtags(_merged_hashtags or [])
        )

    doc = await drafts.update(user.uid, draft_id, updates)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")

    await audit.log(
        user_id=user.uid,
        event_type="DRAFT_UPDATED",
        description=doc.get("title", ""),
        details={"draft_id": draft_id, "fields": list(updates.keys())},
    )
    return _to_response(doc)


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_draft(
    draft_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> None:
    existing = await drafts.get(user.uid, draft_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    deleted = await drafts.delete(user.uid, draft_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    await audit.log(
        user_id=user.uid,
        event_type="DRAFT_DELETED",
        description=existing.get("title", ""),
        details={"draft_id": draft_id},
    )