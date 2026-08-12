"""Thin service layer that wraps the existing CLI workflow for REST access."""

from __future__ import annotations

from fastapi import HTTPException

from workflows.content_workflow import ContentWorkflow
from shared.schemas import GenerateContentRequest, GenerateContentResponse


class WorkflowService:
    """Adapt the current LangGraph workflow to HTTP-first usage."""

    def __init__(self) -> None:
        self._workflow = ContentWorkflow()

    def generate_content(self, payload: GenerateContentRequest) -> GenerateContentResponse:
        """Run the existing workflow against a user topic and return a REST-friendly payload."""
        topic = payload.topic.strip()
        if not topic:
            raise HTTPException(status_code=400, detail="Topic cannot be empty")

        result = self._workflow.run(topic)
        if result.error:
            raise HTTPException(status_code=500, detail=result.error)

        response_payload = result.model_dump(exclude_none=True)
        return GenerateContentResponse.model_validate(response_payload)
