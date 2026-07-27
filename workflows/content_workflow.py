"""Content workflow orchestration for LinkedIn Content Agent.

This module provides a clean orchestration layer for executing agents in sequence.
"""

from typing import Optional, List, Dict
from models.workflow_models import WorkflowState, WorkflowResult
from models.context_models import Context
from agents.planner import PlannerAgent
from agents.writer import WriterAgent
from agents.reviewer import ReviewerAgent
from services.search import search_web
from services.context_builder import ContextBuilder
from utils.logger import logger


class ContentWorkflow:
    """Orchestrates the content creation workflow.
    
    This class manages the execution of Planner, Writer, and Reviewer agents
    in sequence, with automatic retry logic for review failures.
    """
    
    MAX_ITERATIONS = 2
    APPROVAL_THRESHOLD = 8
    
    def __init__(self) -> None:
        """Initialize the ContentWorkflow with agents and context builder."""
        self.context_builder = ContextBuilder()
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
        logger.info(f"Starting workflow for topic: {topic}")
        
        # Initialize workflow state
        state = WorkflowState(topic=topic)
        
        try:
            # Step 0: Build context
            logger.info("Starting Context Builder")
            context = self.context_builder.build(writing_style=None)
            logger.info("Context built successfully")
            
            # Step 1: Planning
            logger.info("Starting Planner Agent")
            state.execution_plan = self._run_planner(topic, context)
            logger.info("Planner completed")
            
            # Step 2: Research (if needed)
            if state.execution_plan.requires_search:
                logger.info("Starting research")
                state.research = self._run_research(state.execution_plan.topic)
                logger.info("Research completed")
            
            # Step 3: Writing and Review loop
            state = self._run_write_review_loop(state, context)
            
            # Build result
            result = WorkflowResult(
                topic=topic,
                final_post=state.draft,
                approved=state.approved,
                iterations=state.iteration,
                review_feedback=state.review.feedback if state.review else None,
                review_scores=state.review.scores if state.review else None,
                metadata=state.metadata
            )
            
            logger.info(f"Workflow completed. Approved: {state.approved}, Iterations: {state.iteration}")
            return result
            
        except Exception as e:
            logger.error(f"Workflow failed: {str(e)}")
            return WorkflowResult(
                topic=topic,
                final_post=state.draft,
                approved=False,
                iterations=state.iteration,
                review_feedback=state.review.feedback if state.review else None,
                review_scores=state.review.scores if state.review else None,
                error=str(e),
                metadata=state.metadata
            )
    
    def _run_planner(self, topic: str, context: Context):
        """Execute the Planner Agent.
        
        Args:
            topic: User's topic.
            context: Unified context object.
            
        Returns:
            ExecutionPlan from the Planner Agent.
        """
        return self.planner.plan(topic, context)
    
    def _run_research(self, topic: str) -> List[Dict[str, str]]:
        """Execute web search for the topic.
        
        Args:
            topic: Topic to search for.
            
        Returns:
            List of search results.
        """
        return search_web(topic, max_results=5)
    
    def _run_write_review_loop(self, state: WorkflowState, context: Context) -> WorkflowState:
        """Execute the write-review loop with automatic retries.
        
        Args:
            state: Current workflow state.
            context: Unified context object.
            
        Returns:
            Updated workflow state.
        """
        iteration = 0
        
        while iteration < self.MAX_ITERATIONS:
            iteration += 1
            state.iteration = iteration
            
            logger.info(f"Iteration {iteration}: Starting Writer Agent")
            
            # Write
            edit_instruction = state.review.feedback if iteration > 1 else None
            state.draft = self._run_writer(
                state.execution_plan,
                state.research,
                edit_instruction,
                context
            )
            logger.info(f"Iteration {iteration}: Writer completed")
            
            # Review
            logger.info(f"Iteration {iteration}: Starting Reviewer Agent")
            state.review = self._run_reviewer(state.draft, context)
            logger.info(f"Iteration {iteration}: Review completed with score {state.review.scores.overall}/10")
            
            # Check approval
            if state.review.scores.overall >= self.APPROVAL_THRESHOLD:
                logger.info(f"Iteration {iteration}: Review passed")
                state.approved = True
                state.metadata["approval_iteration"] = iteration
                break
            else:
                logger.info(f"Iteration {iteration}: Review failed, will rewrite")
                state.approved = False
        
        return state
    
    def _run_writer(
        self,
        execution_plan,
        research: Optional[List[Dict[str, str]]],
        edit_instruction: Optional[str] = None,
        context: Optional[Context] = None
    ):
        """Execute the Writer Agent.
        
        Args:
            execution_plan: Execution plan from Planner.
            research: Optional research results.
            edit_instruction: Optional edit instruction for rewrites.
            context: Unified context object.
            
        Returns:
            LinkedInPost from the Writer Agent.
        """
        return self.writer.write(
            topic=execution_plan.topic,
            intent=execution_plan.intent,
            user_prompt=execution_plan.topic,
            research=research,
            writing_style=execution_plan.writing_style,
            edit_instruction=edit_instruction,
            context=context
        )
    
    def _run_reviewer(self, post, context: Optional[Context] = None):
        """Execute the Reviewer Agent.
        
        Args:
            post: LinkedInPost to review.
            context: Unified context object.
            
        Returns:
            ReviewResult from the Reviewer Agent.
        """
        return self.reviewer.review(post, context)
