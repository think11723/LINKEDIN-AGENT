"""Content API endpoints for the web application."""

from fastapi import APIRouter, Depends, HTTPException

from backend.app.services.workflow_service import WorkflowService
from shared.schemas import GenerateContentRequest, GenerateContentResponse

router = APIRouter(prefix="/api/v1/content", tags=["content"])


def get_workflow_service() -> WorkflowService:
    return WorkflowService()


@router.post("/generate", response_model=GenerateContentResponse)
async def generate_content(
    payload: GenerateContentRequest,
    service: WorkflowService = Depends(get_workflow_service),
) -> GenerateContentResponse:
    """Generate a LinkedIn draft using the existing LangGraph workflow."""
    try:
        return service.generate_content(payload)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise HTTPException(status_code=500, detail=str(exc)) from exc
