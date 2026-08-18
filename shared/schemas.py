"""Shared request/response contracts for the web application."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GenerateContentRequest(BaseModel):
    """Request payload for content generation from the web UI."""

    topic: str = Field(
        ..., min_length=1, description="LinkedIn topic or prompt"
    )
    image_path: Optional[str] = Field(
        default=None, description="Optional local image path"
    )


class LinkedInPostPayload(BaseModel):
    """REST-friendly representation of the generated post."""

    title: str
    content: str
    hashtags: List[str] = Field(default_factory=list)
    image_path: Optional[str] = None


class GenerateContentResponse(BaseModel):
    """REST-friendly workflow result contract."""

    topic: str
    final_post: Optional[LinkedInPostPayload] = None
    approved: bool
    iterations: int
    review_feedback: Optional[str] = None
    review_scores: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Phase 7.6: surface the persisted draft + token so the SPA can navigate
    # to /drafts/{draft_id} immediately without polling /api/v1/approval/queue.
    draft_id: Optional[str] = None
    approval_token: Optional[str] = None
    draft: Optional[Dict[str, Any]] = None
    # Phase 8D / URL-to-LinkedIn. Only set when the draft was generated
    # from a URL; never set for topic-mode drafts.
    source_url: Optional[str] = None
    source_metadata: Optional[Dict[str, Any]] = None


class DashboardActivityItem(BaseModel):
    """A single recent activity entry for the dashboard."""

    event_type: str
    description: str
    timestamp: str


class DashboardSummaryResponse(BaseModel):
    """Dashboard summary metrics.

    Phase 8B P1-5 — extended with ``approved_count`` and ``failed_count``.
    """

    drafts_count: int
    published_count: int
    scheduled_count: int
    approval_queue_count: int
    approved_count: int = 0
    failed_count: int = 0
    recent_activity: List[DashboardActivityItem] = Field(default_factory=list)


class DashboardActivityResponse(BaseModel):
    """Recent activity endpoint response."""

    items: List[DashboardActivityItem] = Field(default_factory=list)


class ApprovalQueueItem(BaseModel):
    """Approval queue item used by the frontend."""

    draft_id: str
    title: str
    topic: str
    token: str
    status: str
    review_score: int
    created_at: Optional[str] = None


class ApprovalDraftResponse(BaseModel):
    """Approval draft detail contract."""

    draft_id: str
    title: str
    content: str
    hashtags: List[str] = Field(default_factory=list)
    review_score: int
    review_feedback: str = ""
    research_summary: Optional[str] = None
    approval_token: str
    published_at: Optional[str] = None
    scheduled_publish_time: Optional[str] = None
    status: str = "pending"


class ApprovalActionResponse(BaseModel):
    """Simple response for approval actions."""

    success: bool
    message: str


class SchedulerJobResponse(BaseModel):
    """Scheduled job representation."""

    job_id: str
    title: str
    content: str
    hashtags: List[str] = Field(default_factory=list)
    scheduled_time: str
    status: str


class SchedulePostPayload(BaseModel):
    """Payload to create a scheduled post."""

    title: str
    content: str
    hashtags: List[str] = Field(default_factory=list)
    image_path: Optional[str] = None
    scheduled_time: str


class SchedulePostResponse(BaseModel):
    """Response after scheduling a future post."""

    success: bool
    job_id: str
    scheduled_time: str


class PublishedDraftResponse(BaseModel):
    """Published drafts for the published posts page."""

    draft_id: str
    title: str
    content: str
    hashtags: List[str] = Field(default_factory=list)
    published_at: Optional[str] = None
    linkedin_post_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Phase 8B P1 — user profile, settings, publish-now
# ---------------------------------------------------------------------------


class UserProfileResponse(BaseModel):
    """Phase 8B P1-10 — server-side profile resource.

    Identity fields (uid, email, email_verified) are Firebase-owned and
    are not editable through this resource. Only application-side
    profile metadata is mutable.
    """

    uid: str
    email: str
    email_verified: bool
    display_name: Optional[str] = None
    headline: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    avatar_url: Optional[str] = None
    updated_at: str


class UserProfileUpdateRequest(BaseModel):
    """Mutable subset of the user profile. All fields optional (PATCH)."""

    display_name: Optional[str] = Field(default=None, max_length=120)
    headline: Optional[str] = Field(default=None, max_length=160)
    bio: Optional[str] = Field(default=None, max_length=2000)
    linkedin_url: Optional[str] = Field(default=None, max_length=500)
    github_url: Optional[str] = Field(default=None, max_length=500)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


# Enum-like string literals kept as plain strings for forward compatibility
# with the existing string-typed Pydantic conventions in this module.
PUBLISHING_MODES = ("manual", "scheduled")
APPROVAL_MODES = ("email", "auto", "manual")


class UserSettingsResponse(BaseModel):
    """Phase 8B P1-11 — server-side settings resource.

    `linkedin_connected` and `person_urn` are sourced from the LinkedIn
    repository, NOT from this document. Settings that affect publishing
    or notification behaviour live on the user document.
    """

    linkedin_connected: bool = False
    person_urn: Optional[str] = None
    linkedin_expires_at: Optional[str] = None
    linkedin_scope: Optional[str] = None
    publishing_mode: str = "manual"
    approval_mode: str = "email"
    notification_email: Optional[str] = None
    default_image_provider: Optional[str] = None
    default_image_model: Optional[str] = None
    timezone: Optional[str] = None
    updated_at: str


class UserSettingsUpdateRequest(BaseModel):
    """Mutable subset of user settings. All fields optional (PATCH).

    Enum fields (``publishing_mode``, ``approval_mode``) are validated
    server-side against ``PUBLISHING_MODES`` / ``APPROVAL_MODES``.
    """

    publishing_mode: Optional[str] = None
    approval_mode: Optional[str] = None
    notification_email: Optional[str] = Field(default=None, max_length=320)
    timezone: Optional[str] = Field(default=None, max_length=64)


class PublishNowResponse(BaseModel):
    """Phase 8B P1-9 — synchronous on-demand publish response.

    `linkedin_post_id` is the LinkedIn URN when the publish succeeded,
    otherwise ``None`` (the response itself may still indicate failure
    via the global error envelope; this shape is for the success path).
    """

    success: bool
    draft_id: str
    linkedin_post_id: Optional[str] = None
    published_at: str
    message: Optional[str] = None
    already_published: bool = False
