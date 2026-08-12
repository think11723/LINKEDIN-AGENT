"""FastAPI approval server for handling approval requests."""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from approval.service import ApprovalService
from approval.models import DraftRecord
from utils.logger import logger

app = FastAPI(title="LinkedIn Approval Server")
approval_service = ApprovalService()
templates = Jinja2Templates(directory="approval/templates")


def _background_publish(draft_id: str) -> None:
    """Background task to publish draft to LinkedIn.
    
    Args:
        draft_id: Draft identifier.
    """
    try:
        success, message = approval_service.publish_draft(draft_id)
        if success:
            logger.info(f"Background publish succeeded for draft {draft_id}: {message}")
        else:
            logger.error(f"Background publish failed for draft {draft_id}: {message}")
    except Exception as e:
        logger.error(f"Background publish error for draft {draft_id}: {e}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "LinkedIn Approval Server", "status": "running"}


@app.get("/approve/{token}", response_class=HTMLResponse)
async def approve(token: str, request: Request, background_tasks: BackgroundTasks, schedule: Optional[str] = None):
    """Approve a draft via token and queue background publishing.
    
    Args:
        token: Approval token.
        request: FastAPI request.
        background_tasks: FastAPI background tasks.
        schedule: Optional schedule time (ISO format).
        
    Returns:
        HTML response with approval result.
    """
    from datetime import datetime
    
    schedule_time = None
    if schedule:
        try:
            schedule_time = datetime.fromisoformat(schedule)
        except ValueError:
            pass
    
    success, message = approval_service.approve(token, schedule_time)
    
    if success and not schedule_time:
        # Get draft ID for background publishing (only if immediate)
        draft = approval_service.get_draft(token)
        if draft:
            # Queue background publishing
            background_tasks.add_task(_background_publish, draft.draft_id)
            message = "Draft approved successfully. Publishing in background."
    
    return templates.TemplateResponse("approval_result.html", {
        "request": request,
        "success": success,
        "message": message,
        "action": "approved"
    })


@app.get("/reject/{token}", response_class=HTMLResponse)
async def reject(token: str, request: Request):
    """Reject a draft via token.
    
    Args:
        token: Approval token.
        request: FastAPI request.
        
    Returns:
        HTML response with rejection result.
    """
    success, message = approval_service.reject(token)
    
    return templates.TemplateResponse("approval_result.html", {
        "request": request,
        "success": success,
        "message": message,
        "action": "rejected"
    })


@app.get("/draft/{token}", response_class=HTMLResponse)
async def view_draft(token: str, request: Request):
    """View a draft via token (uses professional dashboard).
    
    Args:
        token: Approval token.
        request: FastAPI request.
        
    Returns:
        HTML response with draft details.
    """
    draft = approval_service.get_draft(token)
    
    if not draft:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "Draft not found or token invalid"
        })
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "draft": draft,
        "token": token
    })


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
