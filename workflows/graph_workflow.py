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
        workflow.add_node("memory_index", self._memory_index_node)
        
        # Define edges
        workflow.set_entry_point("context_builder")
        workflow.add_edge("context_builder", "research")
        workflow.add_edge("research", "planner")
        workflow.add_edge("planner", "writer")
        workflow.add_edge("writer", "reviewer")
        
        # Conditional edge for review approval
        workflow.add_conditional_edges(
            "reviewer",
            self._should_continue_writing,
            {
                "continue": "writer",
                "approved": "memory_index",
                "max_reached": "memory_index"
            }
        )
        
        workflow.add_edge("memory_index", END)
        
        return workflow.compile()
    
    def _context_builder_node(self, state: GraphState) -> GraphState:
        """Context Builder node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with context.
        """
        logger.info("Starting Context Builder")
        try:
            context = self.context_builder.build(writing_style=None, topic=state["topic"])
            state["context"] = context
            logger.info("Context built successfully")
        except Exception as e:
            logger.error(f"Context Builder failed: {e}")
            state["error"] = str(e)
        return state
    
    def _research_node(self, state: GraphState) -> GraphState:
        """Research node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with research package.
        """
        logger.info("Starting Research Service")
        try:
            research_package = self.research_service.research(state["topic"])
            state["research_package"] = research_package
            logger.info("Research completed")
        except Exception as e:
            logger.error(f"Research failed: {e}")
            state["error"] = str(e)
        return state
    
    def _planner_node(self, state: GraphState) -> GraphState:
        """Planner node.
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state with execution plan.
        """
        logger.info("Starting Planner Agent")
        try:
            execution_plan = self.planner.plan(state["topic"], state["context"])
            state["execution_plan"] = execution_plan
            logger.info("Planner completed")
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            state["error"] = str(e)
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
            state["draft"] = draft
            logger.info(f"Iteration {iteration}: Writer completed")
        except Exception as e:
            logger.error(f"Writer failed: {e}")
            state["error"] = str(e)
        
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
        
        try:
            review = self.reviewer.review(state["draft"], state["context"])
            state["review"] = review
            logger.info(f"Iteration {iteration}: Review completed with score {review.scores.overall}/10")
        except Exception as e:
            logger.error(f"Reviewer failed: {e}")
            state["error"] = str(e)
        
        return state
    
    def _memory_index_node(self, state: GraphState) -> GraphState:
        """Memory Index node (executes after approval or max iterations).
        
        Args:
            state: Current graph state.
            
        Returns:
            Updated state.
        """
        # Only index if approved
        if state["approved"] and state["draft"]:
            try:
                from memory.service import MemoryService
                memory_service = MemoryService()
                memory_service.index_post(
                    topic=state["topic"],
                    title=state["draft"].title,
                    content=state["draft"].content,
                    hashtags=state["draft"].hashtags,
                    writing_style=state["context"].writing_style if state["context"] else "professional"
                )
                logger.info("Post indexed in memory successfully")
            except Exception as e:
                logger.warning(f"Failed to index post in memory: {e}")
        
        return state
    
    def _should_continue_writing(self, state: GraphState) -> str:
        """Determine whether to continue writing or finish.
        
        Args:
            state: Current graph state.
            
        Returns:
            "continue" if should rewrite, "approved" if approved, "max_reached" if max iterations reached.
        """
        # Check for errors
        if state.get("error"):
            return "max_reached"
        
        # Check if review passed
        if state["review"] and state["review"].scores.overall >= state["approval_threshold"]:
            state["approved"] = True
            state["metadata"]["approval_iteration"] = state["iteration"]
            logger.info(f"Iteration {state['iteration']}: Review passed")
            return "approved"
        
        # Check if max iterations reached
        if state["iteration"] >= state["max_iterations"]:
            state["approved"] = False
            logger.info(f"Max iterations reached without approval")
            return "max_reached"
        
        # Continue writing
        state["approved"] = False
        logger.info(f"Iteration {state['iteration']}: Review failed, will rewrite")
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
