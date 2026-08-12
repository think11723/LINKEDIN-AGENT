"""Workflow state and result models for LinkedIn Content Agent."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from models.models import LinkedInPost
from agents.planner import ExecutionPlan
from agents.reviewer import ReviewScores, ReviewResult


class WorkflowState(BaseModel):
    """State model for content workflow execution."""
    
    topic: str = Field(description="User's topic/request")
    research: Optional[List[Dict[str, str]]] = Field(default=None, description="Research results if search was performed")
    execution_plan: Optional[ExecutionPlan] = Field(default=None, description="Execution plan from Planner Agent")
    draft: Optional[LinkedInPost] = Field(default=None, description="Current draft from Writer Agent")
    review: Optional[ReviewResult] = Field(default=None, description="Review result from Reviewer Agent")
    approved: bool = Field(default=False, description="Whether content was approved")
    iteration: int = Field(default=0, description="Current iteration count")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class WorkflowResult(BaseModel):
    """Result model for content workflow execution."""
    
    topic: str = Field(description="Original topic")
    final_post: Optional[LinkedInPost] = Field(description="Final LinkedIn post (may be None if failed)")
    approved: bool = Field(description="Whether content was approved")
    iterations: int = Field(description="Number of iterations performed")
    review_feedback: Optional[str] = Field(description="Review feedback from last iteration")
    review_scores: Optional[ReviewScores] = Field(description="Review scores from last iteration")
    error: Optional[str] = Field(default=None, description="Error message if workflow failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
