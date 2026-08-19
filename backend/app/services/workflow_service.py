"""Thin service layer that wraps the existing CLI workflow for REST access.

Phase 8D / URL-to-LinkedIn: this service exposes a single seam —
``research_package`` — that lets the URL job runner feed a pre-built
``ResearchPackage`` into the same ``ContentGraphWorkflow`` invocation
the topic endpoint uses. The topic path is unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from fastapi import HTTPException

from workflows.content_workflow import ContentWorkflow
from shared.schemas import GenerateContentRequest, GenerateContentResponse

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from services.research.models import ResearchPackage


class WorkflowService:
    """Adapt the current LangGraph workflow to HTTP-first usage."""

    def __init__(self) -> None:
        self._workflow = ContentWorkflow()

    async def generate_content(
        self,
        payload: GenerateContentRequest,
        *,
        research_package: Optional["ResearchPackage"] = None,
    ) -> GenerateContentResponse:
        """Run the existing workflow against a topic. Optional
        ``research_package`` lets the URL job runner feed a pre-built
        ``ResearchPackage`` into the same graph. When ``None`` (the
        default), topic mode is unchanged — the graph performs live
        research as before.
        """
        # URL mode may pass ``payload.topic`` empty and supply a
        # ``ResearchPackage`` whose ``topic`` becomes the workflow's
        # topic. Topic mode always has a non-empty ``payload.topic``.
        topic = (payload.topic or "").strip()
        if not topic and research_package is not None:
            topic = research_package.topic or ""
        if not topic:
            raise HTTPException(status_code=400, detail="Topic cannot be empty")

        # The workflow (and its LangGraph) is async because the
        # Writer and Reviewer nodes await the LLM. ``await`` it
        # here so we do not call an async method from a sync
        # context (which would create a coroutine that the caller
        # then has to deal with).
        result = await self._workflow.run(
            topic, research_package=research_package
        )
        if result.error:
            raise HTTPException(status_code=500, detail=result.error)

        response_payload = result.model_dump(exclude_none=True)
        return GenerateContentResponse.model_validate(response_payload)