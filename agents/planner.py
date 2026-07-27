"""Planner Agent for LinkedIn Content Agent.

This agent analyzes user requests and creates an execution plan,
determining whether web search is needed.
"""

from typing import Optional
from pydantic import BaseModel, Field
from config.config import config
from utils.style_manager import detect_style
from models.context_models import Context


class ExecutionPlan(BaseModel):
    """Execution plan for creating a LinkedIn post."""
    
    topic: str = Field(description="The main topic of the LinkedIn post")
    intent: str = Field(description="The user's intent (e.g., share experience, discuss trend, promote)")
    requires_search: bool = Field(description="Whether web search is needed for current information")
    search_reason: str = Field(description="Reason why search is needed (empty if not required)")
    tone: str = Field(description="Suggested tone for the post (e.g., professional, casual, inspirational)")
    writing_style: str = Field(default="professional", description="Writing style for the post")


class PlannerAgent:
    """Agent that plans the execution of LinkedIn post creation."""
    
    def __init__(self) -> None:
        """Initialize the Planner Agent."""
        self._setup_prompt()
    
    def _setup_prompt(self) -> None:
        """Set up the prompt template for planning."""
        # Note: Currently using heuristic-based parsing
        # In future, this could use LLM for more sophisticated planning
        pass
    
    def plan(self, user_request: str, context: Optional[Context] = None) -> ExecutionPlan:
        """Create an execution plan for the user's request.
        
        Args:
            user_request: Natural language request from the user.
            context: Unified context object with user preferences.
            
        Returns:
            ExecutionPlan: Structured plan for creating the LinkedIn post.
        """
        # Detect writing style
        writing_style = detect_style(user_request)
        
        # Use context writing style if provided
        if context and context.writing_style:
            writing_style = context.writing_style
        
        # Parse the request into structured format
        plan = self._parse_response(user_request, writing_style, context)
        
        return plan
    
    def _parse_response(self, user_request: str, writing_style: str = "professional", context: Optional[Context] = None) -> ExecutionPlan:
        """Parse the user request into an ExecutionPlan.
        
        Args:
            user_request: Original user request.
            writing_style: Detected writing style.
            
        Returns:
            ExecutionPlan: Structured execution plan.
        """
        # Use heuristic-based approach for planning
        # In future versions, this could use LLM for more sophisticated analysis
        
        # Determine if search is needed
        search_keywords = [
            "news", "trend", "latest", "recent", "2026", "statistics",
            "current", "today", "this year", "future", "upcoming"
        ]
        
        requires_search = any(
            keyword.lower() in user_request.lower() 
            for keyword in search_keywords
        )
        
        search_reason = ""
        if requires_search:
            search_reason = "Topic requires recent information or current trends"
        
        # Extract topic (simple approach)
        topic = user_request[:100] + "..." if len(user_request) > 100 else user_request
        
        # Determine intent
        if "journey" in user_request.lower() or "learning" in user_request.lower():
            intent = "share personal learning experience"
        elif "boom" in user_request.lower() or "trend" in user_request.lower():
            intent = "discuss industry trend"
        else:
            intent = "share professional insights"
        
        # Determine tone
        if "journey" in user_request.lower():
            tone = "personal and inspiring"
        else:
            tone = "professional and informative"
        
        return ExecutionPlan(
            topic=topic,
            intent=intent,
            requires_search=requires_search,
            search_reason=search_reason,
            tone=tone,
            writing_style=writing_style
        )
