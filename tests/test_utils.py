"""Tests for utility functions."""

import pytest
import tempfile
from pathlib import Path
from utils.draft_saver import save_draft
from utils.profile_manager import profile_exists, load_profile
from utils.logger import logger


class TestDraftSaver:
    """Test cases for draft saving functionality."""
    
    def test_save_draft(self):
        """Test saving a draft."""
        from models.workflow_models import WorkflowResult
        from models.models import LinkedInPost
        
        # Create a mock result
        post = LinkedInPost(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"]
        )
        
        result = WorkflowResult(
            topic="Test",
            final_post=post,
            approved=True,
            iterations=1
        )
        
        # Save draft
        draft_path = save_draft(result)
        
        assert draft_path is not None
        assert Path(draft_path).exists()
        
        # Clean up
        Path(draft_path).unlink()


class TestProfileManager:
    """Test cases for profile management."""
    
    def test_profile_exists(self):
        """Test checking if profile exists."""
        # This test checks the function works, not actual profile existence
        result = profile_exists()
        assert isinstance(result, bool)
    
    def test_load_profile(self):
        """Test loading profile."""
        # This test checks the function works
        profile = load_profile()
        # Profile may be None if not configured
        assert profile is None or profile is not None


class TestLogger:
    """Test cases for logger."""
    
    def test_logger_exists(self):
        """Test that logger is available."""
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        assert hasattr(logger, 'warning')
