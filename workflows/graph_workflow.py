"""LangGraph-based workflow orchestration for LinkedIn Content Agent.

This module provides LangGraph-based orchestration for executing agents in sequence.
"""

from typing import Optional, List, Dict, Any, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from models.workflow_models import WorkflowState, WorkflowResult
from models.context_models import Context
from models.models import LinkedInPost
from agents.planner import PlannerAgent, ExecutionPlan
from agents.writer import WriterAgent
from agents.reviewer import ReviewerAgent, ReviewResult
from services.context_builder import ContextBuilder
from services.research import ResearchService
from utils.logger import logger


class GraphState(TypedDict):
    """State for LangGraph workflow execution."""
    
    topic: str
    context: Optional[Context]
    research_package: Optional[Any]
    execution_plan: Optional[ExecutionPlan]
    draft: Optional[LinkedInPost]
    review: Optional[ReviewResult]
    approved: bool
    review_passed: bool
    iteration: int
    max_iterations: int
    approval_threshold: int
    metadata: Dict[str, Any]
    error: Optional[str]


class ContentGraphWorkflow:
    """LangGraph-based workflow orchestration for content creation.
    
    This class uses LangGraph to orchestrate the execution of Context Builder,
    Research, Planner, Writer, and Reviewer agents with automatic retry logic.
    """
    
    MAX_ITERATIONS = 2
    APPROVAL_THRESHOLD = 8
    
    def __init__(self) -> None:
        """Initialize the workflow with agents and services."""
        self.context_builder = ContextBuilder()
        self.research_service = ResearchService()
        self.planner = PlannerAgent()
        self.writer = WriterAgent()
        self.reviewer = ReviewerAgent()
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow graph.
        
        Returns:
            Compiled LangGraph StateGraph.
        """
        # Create the graph
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("context_builder", self._context_builder_node)
        workflow.add_node("research", self._research_node)
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("writer", self._writer_node)
        workflow.add_node("reviewer", self._reviewer_node)
        workflow.add_node("set_approval_status", self._set_approval_status_node)
        workflow.add_node("approval_request", self._approval_request_node)
        workflow.add_node("handle_error", self._handle_error_node)
        
        # Define edges
        workflow.set_entry_point("context_builder")
        
        # Add conditional edges after each node to check for errors
        workflow.add_conditional_edges(
            "context_builder",
            self._check_error,
            {
                "continue": "research",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "research",
            self._check_error,
            {
                "continue": "planner",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "planner",
            self._check_error,
            {
                "continue": "writer",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "writer",
            self._check_error,
            {
                "continue": "reviewer",
                "error": "handle_error"
            }
        )
        
        # Conditional edge for review approval
        workflow.add_conditional_edges(
            "reviewer",
            self._should_continue_writing,
            {
                "continue": "writer",
                "approved": "set_approval_status",
                "max_reached": "set_approval_status",
                "error": "handle_error"
            }
        )
        
        workflow.add_edge("set_approval_status", "approval_request")
        workflow.add_edge("approval_request", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile()
    
    def _check_error(self, state: GraphState) -> str:
        """Check if an error occurred in the previous node.
        
        Args:
            state: Current graph state.
            
        Returns:
            "continue" if no error, "error" if error occurred.
        """
        if state.get("error"):
            logger.error(f"Error detected after node execution: {state['error']}")
            return "error"
        return "continue"
    
    def _set_approval_status_node(self, state: GraphState) -> GraphState:
        """Set approval status based on workflow decision.
        
        This node explicitly sets state["approved"] to ensure it persists
        before reaching the approval_request node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with approved flag set.
        """
        logger.info(f"[STATE TRACE] Before set_approval_status: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        
        # Determine approval status based on review
        # This logic mirrors the decision made in _should_continue_writing
        review_passed = False
        decision = None
        
        if state["review"] and state["review"].decision:
            decision = state["review"].decision.decision.lower()
            
            # Decision is authoritative
            if decision == "approved":
                review_passed = True
            elif decision == "needs revision":
                review_passed = False
            elif decision == "rejected":
                review_passed = False
            else:
                # Unknown decision - fall back to score
                if state["review"].scores.overall >= state["approval_threshold"]:
                    review_passed = True
        elif state["review"]:
            # No decision field - fall back to score threshold (legacy behavior)
            if state["review"].scores.overall >= state["approval_threshold"]:
                review_passed = True
        
        # Set approved flag based on review_passed
        if review_passed:
            state["approved"] = True
            state["metadata"]["approval_iteration"] = state["iteration"]
            state["metadata"]["approval_reason"] = f"Decision: {decision}" if decision else f"Score: {state['review'].scores.overall}/10"
            logger.info(f"Approval status set to TRUE - will send approval request")
        else:
            state["approved"] = False
            if state["iteration"] >= state["max_iterations"]:
                state["metadata"]["approval_skipped_reason"] = f"Max iterations reached. Final decision: {decision if decision else 'N/A'}"
            logger.info(f"Approval status set to FALSE - will skip approval request")
        
        logger.info(f"[STATE TRACE] After set_approval_status: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        return state
    
    def _context_builder_node(self, state: GraphState) -> GraphState:
        """Context Builder node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with context.
        """
        logger.info("Starting Context Builder")
        logger.info(f"[STATE TRACE] Before context_builder: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        
        try:
            context = self.context_builder.build(writing_style=None, topic=state["topic"])
            state["context"] = context
            logger.info("Context built successfully")
        except Exception as e:
            logger.error(f"Context Builder failed: {e}")
            state["error"] = str(e)
        
        logger.info(f"[STATE TRACE] After context_builder: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        return state
    
    def _research_node(self, state: GraphState) -> GraphState:
        """Research node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with research package.
        """
        logger.info("Starting Research Service")
        logger.info(f"[STATE TRACE] Before research: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        
        try:
            research_package = self.research_service.research(state["topic"])
            state["research_package"] = research_package
            logger.info("Research completed")
        except Exception as e:
            logger.error(f"Research failed: {e}")
            state["error"] = str(e)
        
        logger.info(f"[STATE TRACE] After research: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        return state
    
    def _planner_node(self, state: GraphState) -> GraphState:
        """Planner node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with execution plan.
        """
        logger.info("Starting Planner Agent")
        logger.info(f"[STATE TRACE] Before planner: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        
        try:
            execution_plan = self.planner.plan(state["topic"], state["context"])
            state["execution_plan"] = execution_plan
            logger.info("Planner completed")
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            state["error"] = str(e)
        
        logger.info(f"[STATE TRACE] After planner: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        return state
    
    def _writer_node(self, state: GraphState) -> GraphState:
        """Writer node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with draft.
        """
        iteration = state["iteration"] + 1
        state["iteration"] = iteration
        
        logger.info(f"Iteration {iteration}: Starting Writer Agent")
        logger.info(f"[STATE TRACE] Before writer: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        
        try:
            # Get edit instruction if this is a retry
            edit_instruction = state["review"].feedback if iteration > 1 else None
            
            # Write the post
            draft = self.writer.write(
                topic=state["execution_plan"].topic,
                intent=state["execution_plan"].intent,
                user_prompt=state["execution_plan"].topic,
                research=state["research_package"].raw_results if state["research_package"] else None,
                writing_style=state["execution_plan"].writing_style,
                edit_instruction=edit_instruction,
                context=state["context"],
                execution_plan=state["execution_plan"]
            )
            
            # Validate LinkedIn formatting
            from utils.linkedin_validator import LinkedInValidator
            validator = LinkedInValidator()
            validation_result = validator.validate(
                title=draft.title,
                content=draft.content,
                hashtags=draft.hashtags
            )
            
            if not validation_result.is_valid:
                logger.warning(f"Iteration {iteration}: LinkedIn formatting validation failed")
                for error in validation_result.errors:
                    logger.warning(f"  Error: {error}")
            elif validation_result.warnings:
                logger.info(f"Iteration {iteration}: LinkedIn formatting validation passed with warnings")
                for warning in validation_result.warnings:
                    logger.info(f"  Warning: {warning}")
            else:
                logger.info(f"Iteration {iteration}: LinkedIn formatting validation passed")
            
            state["draft"] = draft
            logger.info(f"Iteration {iteration}: Writer completed")
        except Exception as e:
            logger.error(f"Writer failed: {e}")
            state["error"] = str(e)
        
        logger.info(f"[STATE TRACE] After writer: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        return state
    
    def _reviewer_node(self, state: GraphState) -> GraphState:
        """Reviewer node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with review result.
        """
        iteration = state["iteration"]
        logger.info(f"Iteration {iteration}: Starting Reviewer Agent")
        logger.info(f"[STATE TRACE] Before reviewer: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        
        try:
            review = self.reviewer.review(state["draft"], state["context"])
            state["review"] = review
            
            # Debug logging: Print raw ReviewResult before any decisions
            logger.info(f"Iteration {iteration}: Raw ReviewResult - Score: {review.scores.overall}/10, Decision: {review.decision.decision if review.decision else 'N/A'}, Feedback: {review.feedback[:100] if review.feedback else 'N/A'}")
            
            logger.info(f"Iteration {iteration}: Review completed with score {review.scores.overall}/10")
        except Exception as e:
            logger.error(f"Reviewer failed: {e}")
            state["error"] = str(e)
        
        logger.info(f"[STATE TRACE] After reviewer: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        return state
    
    def _approval_request_node(self, state: GraphState) -> GraphState:
        """Approval Request node (saves draft and sends approval email).
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state.
        """
        logger.info("Creating approval request")
        logger.info(f"[STATE TRACE] Before approval_request: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        
        # Only create approval if ALL conditions are met:
        # 1. No errors occurred
        # 2. Draft exists and is valid
        # 3. Review exists and is valid
        # 4. Approved flag is True
        if state.get("error"):
            logger.error(f"Skipping approval request due to error: {state['error']}")
            state["metadata"]["approval_sent"] = False
            state["metadata"]["approval_skipped_reason"] = f"Error: {state['error']}"
            logger.info(f"[STATE TRACE] After approval_request (error path): approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
            return state
        
        if not state.get("draft"):
            logger.error("Skipping approval request: No draft exists")
            state["metadata"]["approval_sent"] = False
            state["metadata"]["approval_skipped_reason"] = "No draft"
            logger.info(f"[STATE TRACE] After approval_request (no draft): approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
            return state
        
        if not state.get("review"):
            logger.error("Skipping approval request: No review exists")
            state["metadata"]["approval_sent"] = False
            state["metadata"]["approval_skipped_reason"] = "No review"
            logger.info(f"[STATE TRACE] After approval_request (no review): approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
            return state
        
        if not state.get("approved"):
            logger.info("Skipping approval request: Not approved")
            state["metadata"]["approval_sent"] = False
            state["metadata"]["approval_skipped_reason"] = "Not approved"
            logger.info(f"[STATE TRACE] After approval_request (not approved): approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
            return state
        
        try:
            from approval.service import ApprovalService
            approval_service = ApprovalService()
            
            # Create draft and send approval email
            draft_id = approval_service.create_draft(
                topic=state["topic"],
                title=state["draft"].title,
                content=state["draft"].content,
                hashtags=state["draft"].hashtags,
                image_path=None,
                review_score=state["review"].scores.overall if state["review"] else 0,
                review_feedback=state["review"].feedback if state["review"] else "",
                research_summary=state["research_package"].summary if state["research_package"] else None
            )
            
            state["metadata"]["draft_id"] = draft_id
            state["metadata"]["approval_sent"] = True
            logger.info(f"Approval request created with draft ID: {draft_id}")
            
        except Exception as e:
            logger.error(f"Failed to create approval request: {e}")
            state["error"] = str(e)
            state["metadata"]["approval_sent"] = False
        
        logger.info(f"[STATE TRACE] After approval_request: approved={state.get('approved')}, review_exists={state.get('review') is not None}, draft_exists={state.get('draft') is not None}, error={state.get('error')}")
        return state
    
    def _handle_error_node(self, state: GraphState) -> GraphState:
        """Error handling node - logs error and ensures no approval is sent.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with error metadata.
        """
        error_msg = state.get("error", "Unknown error")
        logger.error(f"Workflow failed: {error_msg}")
        state["metadata"]["approval_sent"] = False
        state["metadata"]["approval_skipped_reason"] = f"Workflow error: {error_msg}"
        state["approved"] = False
        return state
    
    def _should_continue_writing(self, state: GraphState) -> str:
        """Determine whether to continue writing or finish.
        
        Args:
            state: Current graph state.
            
        Returns:
            "continue" if should rewrite, "approved" if approved, "max_reached" if max iterations reached, "error" if error occurred.
        """
        # Check for errors FIRST - this prevents approval on any error
        if state.get("error"):
            logger.error(f"Error detected in workflow: {state['error']}")
            return "error"
        
        # Check if review exists - if not, this is an error path
        if not state.get("review"):
            logger.error("No review result exists - treating as error")
            state["error"] = "Review failed to complete"
            return "error"
        
        # Check if draft exists - if not, this is an error path
        if not state.get("draft"):
            logger.error("No draft exists - treating as error")
            state["error"] = "Writer failed to complete"
            return "error"
        
        # APPROVAL POLICY: The explicit decision field is the authoritative source.
        # Score is supplementary information to support the decision.
        # Only approve if decision is explicitly "Approved".
        # If decision is missing, fall back to score threshold (legacy behavior).
        
        review_passed = False
        decision = None
        
        if state["review"].decision:
            decision = state["review"].decision.decision.lower()
            logger.info(f"Iteration {state['iteration']}: Review decision is '{decision}'")
            
            # Decision is authoritative
            if decision == "approved":
                review_passed = True
                logger.info(f"Iteration {state['iteration']}: Review passed based on explicit 'Approved' decision")
            elif decision == "needs revision":
                review_passed = False
                logger.info(f"Iteration {state['iteration']}: Review failed based on 'Needs Revision' decision")
            elif decision == "rejected":
                review_passed = False
                logger.info(f"Iteration {state['iteration']}: Review failed based on 'Rejected' decision")
            else:
                # Unknown decision - fall back to score
                logger.warning(f"Iteration {state['iteration']}: Unknown decision '{decision}', falling back to score")
                if state["review"].scores.overall >= state["approval_threshold"]:
                    review_passed = True
                    logger.info(f"Iteration {state['iteration']}: Review passed based on score threshold (Score: {state['review'].scores.overall}/10)")
        else:
            # No decision field - fall back to score threshold (legacy behavior)
            logger.warning(f"Iteration {state['iteration']}: No decision field, falling back to score threshold")
            if state["review"].scores.overall >= state["approval_threshold"]:
                review_passed = True
                logger.info(f"Iteration {state['iteration']}: Review passed based on score threshold (Score: {state['review'].scores.overall}/10)")
        
        if review_passed:
            logger.info(f"Iteration {state['iteration']}: Review PASSED - Will set approved=TRUE")
            return "approved"
        
        # Check if max iterations reached
        if state["iteration"] >= state["max_iterations"]:
            logger.info(f"Iteration {state['iteration']}: Max iterations reached without approval - Will set approved=FALSE")
            return "max_reached"
        
        # Continue writing
        logger.info(f"Iteration {state['iteration']}: Review FAILED - Will rewrite (Decision: {decision if decision else 'N/A'}, Score: {state['review'].scores.overall}/10)")
        return "continue"
    
    def run(self, topic: str) -> WorkflowResult:
        """Execute the LangGraph workflow for a given topic.
        
        Args:
            topic: User's topic or request for LinkedIn content.
            
        Returns:
            WorkflowResult containing the final post, approval status, and metadata.
        """
        logger.info(f"Starting LangGraph workflow for topic: {topic}")
        
        # Initialize state
        initial_state: GraphState = {
            "topic": topic,
            "context": None,
            "research_package": None,
            "execution_plan": None,
            "draft": None,
            "review": None,
            "approved": False,
            "iteration": 0,
            "max_iterations": self.MAX_ITERATIONS,
            "approval_threshold": self.APPROVAL_THRESHOLD,
            "metadata": {},
            "error": None
        }
        
        try:
            # Execute the graph
            final_state = self.graph.invoke(initial_state)
            
            # Build result
            result = WorkflowResult(
                topic=topic,
                final_post=final_state.get("draft"),
                approved=final_state.get("approved", False),
                iterations=final_state.get("iteration", 0),
                review_feedback=final_state.get("review").feedback if final_state.get("review") else None,
                review_scores=final_state.get("review").scores if final_state.get("review") else None,
                error=final_state.get("error"),
                metadata={
                    **final_state.get("metadata", {}),
                    "research_package": final_state.get("research_package")
                }
            )
            
            logger.info(f"LangGraph workflow completed. Approved: {result.approved}, Iterations: {result.iterations}")
            return result
            
        except Exception as e:
            logger.error(f"LangGraph workflow failed: {str(e)}")
            return WorkflowResult(
                topic=topic,
                final_post=initial_state.get("draft"),
                approved=False,
                iterations=initial_state.get("iteration", 0),
                review_feedback=initial_state.get("review").feedback if initial_state.get("review") else None,
                review_scores=initial_state.get("review").scores if initial_state.get("review") else None,
                error=str(e),
                metadata=initial_state.get("metadata", {})
            )
