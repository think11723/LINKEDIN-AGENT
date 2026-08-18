"""Source-adapter Pydantic models — Phase 8D / URL-to-LinkedIn feature.

These models are the **public** surface that the API layer returns to
the SPA. The internal ``SourcePackage`` (in ``services/sources/base.py``)
is the adapter output; ``SourceSummary`` is the trimmed version
embedded inside the job response so the SPA can render a "source
preview" before the user opens the draft.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceSummary(BaseModel):
    """Trimmed view of ``SourcePackage`` for the SPA's source-preview card."""

    title: str
    summary: str
    key_facts: List[str] = Field(default_factory=list)
    adapter: Optional[str] = None  # "github" | "webpage" | "stub"
    truncated: bool = False


class GenerateFromUrlRequest(BaseModel):
    """Request body for ``POST /api/v1/content/generate-from-url``.

    Topic / intent / audience mirrors today's free-form generation so
    the downstream writer has the same per-user personalization signals.
    """

    url: str = Field(..., min_length=1, description="Public URL to fetch and analyze")
    intent: Optional[str] = Field(
        default=None, description="Optional override for the planner intent"
    )
    audience: Optional[str] = Field(
        default=None, description="Optional target-audience hint"
    )
    tone: Optional[str] = Field(
        default=None, description="Optional tone override for the writer"
    )


class GenerateFromUrlJobResponse(BaseModel):
    """Body of the poll endpoint (``GET /api/v1/content/generate-from-url/{job_id}``).

    Excludes internal fields that the SPA must not consume
    (``attempts``, ``stage`` is exposed for UX, ``request_id`` is
    exposed for support tickets).
    """

    job_id: str
    status: str  # "queued" | "running" | "succeeded" | "failed" | "cancelled"
    stage: Optional[str] = None  # "fetching" | "analyzing" | "writing" | "reviewing" | "persisting" | None
    url: str
    adapter: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    draft_id: Optional[str] = None
    approval_token: Optional[str] = None
    source_summary: Optional[SourceSummary] = None
    source_metadata: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class GenerateFromUrlAcceptedResponse(BaseModel):
    """Body of the POST endpoint when the job is accepted (HTTP 202)."""

    job_id: str
    status: str = "queued"
    request_id: str
    poll_url: str


__all__ = [
    "GenerateFromUrlAcceptedResponse",
    "GenerateFromUrlJobResponse",
    "GenerateFromUrlRequest",
    "SourceSummary",
]