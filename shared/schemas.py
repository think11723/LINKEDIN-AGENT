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


class DashboardActivityItem(BaseModel):
    """A single recent activity entry for the dashboard."""

    event_type: str
    description: str
    timestamp: str


class DashboardSummaryResponse(BaseModel):
    """Dashboard summary metrics."""

    drafts_count: int
    published_count: int
    scheduled_count: int
    approval_queue_count: int
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
