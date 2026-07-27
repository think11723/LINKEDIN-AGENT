"""Content workflow orchestration for LinkedIn Content Agent.

This module provides a clean orchestration layer for executing agents in sequence.
Now uses LangGraph for workflow orchestration.
"""

from typing import Optional, List, Dict
from models.workflow_models import WorkflowState, WorkflowResult
from models.context_models import Context
from agents.planner import PlannerAgent
from agents.writer import WriterAgent
from agents.reviewer import ReviewerAgent
from services.context_builder import ContextBuilder
from services.research import ResearchService
from utils.logger import logger
from workflows.graph_workflow import ContentGraphWorkflow


class ContentWorkflow:
    """Orchestrates the content creation workflow.
    
    This class manages the execution of Planner, Writer, and Reviewer agents
    using LangGraph for orchestration, with automatic retry logic for review failures.
    """
    
    MAX_ITERATIONS = 2
    APPROVAL_THRESHOLD = 8
    
    def __init__(self) -> None:
        """Initialize the ContentWorkflow with LangGraph workflow."""
        self.graph_workflow = ContentGraphWorkflow()
        # Keep legacy agents for backward compatibility if needed
        self.context_builder = ContextBuilder()
        self.research_service = ResearchService()
        self.planner = PlannerAgent()
        self.writer = WriterAgent()
        self.reviewer = ReviewerAgent()
    
    def run(self, topic: str) -> WorkflowResult:
        """Execute the content workflow for a given topic.
        
        Args:
            topic: User's topic or request for LinkedIn content.
            
        Returns:
            WorkflowResult containing the final post, approval status, and metadata.
        """
        # Use LangGraph workflow
        return self.graph_workflow.run(topic)
