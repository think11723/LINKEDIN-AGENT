"""Phase 8B P1-9 — on-demand LinkedIn publish endpoint.

The scheduler path (``backend.app.services.scheduler_runner``) and this
endpoint both call into ``backend.app.services.publishing.publish_now``
to guarantee identical behaviour.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_draft_repository, get_audit_repository
from backend.app.core.security import AuthenticatedUser, get_current_user
from backend.app.repositories import AuditRepository, DraftRepository
from backend.app.services.publishing import publish_now
from shared.schemas import PublishNowResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/drafts", tags=["publishing"])


@router.post(
    "/{draft_id}/publish",
    response_model=PublishNowResponse,
    status_code=status.HTTP_200_OK,
)
async def publish_draft_now(
    draft_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
    drafts: DraftRepository = Depends(get_draft_repository),
    audit: AuditRepository = Depends(get_audit_repository),
) -> PublishNowResponse:
    """Publish a draft to LinkedIn immediately.

    - 404 if the draft does not exist for the caller (cross-user safety).
    - 200 with ``already_published: true`` if the draft is already published
      (idempotent — no second LinkedIn call is made).
    - 400 with a safe message if the user has not connected LinkedIn.
    - 502 on LinkedIn-side failure (4xx / 5xx), surfaced as the global
      ``INTERNAL_SERVER_ERROR`` envelope with the same P0-8 hygiene:
      never the response body, only the status code.
    """
    draft = await drafts.get(user.uid, draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    result = await publish_now(user.uid, draft_id)

    if not result.success:
        # Map to a structured HTTP error. Do NOT leak LinkedIn internals.
        raise HTTPException(
            status_code=400,
            detail=result.error_message or "Publish failed",
        )

    if result.already_published:
        await audit.log(
            user_id=user.uid,
            event_type="DRAFT_PUBLISHED_NOW",
            description=draft.get("title", ""),
            details={
                "draft_id": draft_id,
                "linkedin_post_id": result.linkedin_post_id,
                "idempotent": True,
            },
        )
    else:
        await audit.log(
            user_id=user.uid,
            event_type="DRAFT_PUBLISHED_NOW",
            description=draft.get("title", ""),
            details={
                "draft_id": draft_id,
                "linkedin_post_id": result.linkedin_post_id,
            },
        )

    return PublishNowResponse(
        success=True,
        draft_id=draft_id,
        linkedin_post_id=result.linkedin_post_id,
        published_at=(
            (draft.get("published_at") or datetime.now(timezone.utc)).isoformat()
        ),
        already_published=result.already_published,
        message="Already published." if result.already_published else "Published.",
    )