"""Tests for workflow execution."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from workflows.content_workflow import ContentWorkflow
from models.workflow_models import WorkflowResult


class TestContentWorkflow:
    """Test cases for ContentWorkflow."""
    
    @pytest.fixture
    def workflow(self):
        """Create a workflow instance."""
        return ContentWorkflow()
    
    @patch('workflows.graph_workflow.ContextBuilder')
    @patch('workflows.graph_workflow.ResearchService')
    @patch('workflows.graph_workflow.PlannerAgent')
    @patch('workflows.graph_workflow.WriterAgent')
    @patch('workflows.graph_workflow.ReviewerAgent')
    def test_workflow_initialization(self, mock_reviewer, mock_writer, mock_planner, mock_research, mock_context):
        """Test workflow initializes correctly."""
        workflow = ContentWorkflow()
        assert workflow.graph_workflow is not None
        assert workflow.context_builder is not None
        assert workflow.research_service is not None
        assert workflow.planner is not None
        assert workflow.writer is not None
        assert workflow.reviewer is not None
    
    @patch('workflows.content_workflow.ContentGraphWorkflow')
    def test_workflow_run_calls_graph_workflow(self, mock_graph):
        """Test workflow run delegates to graph workflow."""
        mock_instance = Mock()
        mock_graph.return_value = mock_instance

        # WorkflowResult requires every field even when the type
        # annotation is Optional (Pydantic v2 strictness — see
        # models/workflow_models.py). Supply them explicitly so the
        # mock matches the production constructor.
        expected_result = WorkflowResult(
            topic="test topic",
            final_post=None,
            approved=False,
            iterations=1,
            review_feedback=None,
            review_scores=None,
        )
        mock_instance.run.return_value = expected_result

        workflow = ContentWorkflow()
        result = workflow.run("test topic")

        mock_instance.run.assert_called_once_with(
            "test topic", research_package=None
        )
        assert result == expected_result

    @patch('workflows.content_workflow.ContentGraphWorkflow')
    def test_workflow_run_handles_error(self, mock_graph):
        """Test workflow run propagates a graph-level error result.

        In the current architecture, ``ContentGraphWorkflow`` (the LangGraph
        pipeline) populates ``WorkflowResult.error`` via its ``handle_error``
        node when a node fails; ``ContentWorkflow.run`` simply delegates
        and does not catch Python exceptions. This test verifies that a
        ``WorkflowResult`` carrying an ``error`` field is propagated
        unchanged through ``ContentWorkflow.run`` — which is the contract
        ``backend.app.services.workflow_service.WorkflowService`` relies on
        (``if result.error: raise HTTPException(500, result.error)``).
        """
        mock_instance = Mock()
        mock_graph.return_value = mock_instance
        error_result = WorkflowResult(
            topic="test topic",
            final_post=None,
            approved=False,
            iterations=0,
            review_feedback=None,
            review_scores=None,
            error="Test error",
        )
        mock_instance.run.return_value = error_result

        workflow = ContentWorkflow()
        result = workflow.run("test topic")

        assert result.error == "Test error"
        assert result.approved is False
