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
    
    @patch('workflows.graph_workflow.ContentGraphWorkflow')
    def test_workflow_run_calls_graph_workflow(self, mock_graph):
        """Test workflow run delegates to graph workflow."""
        mock_instance = Mock()
        mock_graph.return_value = mock_instance
        
        expected_result = WorkflowResult(
            topic="test topic",
            final_post=None,
            approved=False,
            iterations=1
        )
        mock_instance.run.return_value = expected_result
        
        workflow = ContentWorkflow()
        result = workflow.run("test topic")
        
        mock_instance.run.assert_called_once_with("test topic")
        assert result == expected_result
    
    @patch('workflows.graph_workflow.ContentGraphWorkflow')
    def test_workflow_run_handles_error(self, mock_graph):
        """Test workflow run handles errors gracefully."""
        mock_instance = Mock()
        mock_graph.return_value = mock_instance
        mock_instance.run.side_effect = Exception("Test error")
        
        workflow = ContentWorkflow()
        result = workflow.run("test topic")
        
        assert result.error == "Test error"
        assert result.approved is False
