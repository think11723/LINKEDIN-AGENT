"""Integration tests for approval system."""

import pytest
import time
from datetime import datetime, timedelta
from approval.models import ApprovalToken, ApprovalStatus, DraftRecord
from approval.store import ApprovalStore
from approval.service import ApprovalService


class TestApprovalStore:
    """Tests for ApprovalStore."""
    
    def test_create_token(self):
        """Test token creation."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        token = store.create_token("draft_123", expiry_hours=24)
        
        assert token.token is not None
        assert token.draft_id == "draft_123"
        assert token.status == ApprovalStatus.PENDING
        assert not token.used
        assert token.is_valid()
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")
    
    def test_token_expiry(self):
        """Test token expiry."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        token = store.create_token("draft_123", expiry_hours=1)
        
        # Token should not be expired immediately
        assert not token.is_expired()
        
        # Manually set expiry to past
        token.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert token.is_expired()
        assert not token.is_valid()
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")
    
    def test_approve_token(self):
        """Test token approval."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        token = store.create_token("draft_123", expiry_hours=24)
        
        # Approve token
        result = store.approve_token(token.token)
        assert result is True
        
        # Verify token is marked as approved
        approved_token = store.get_token(token.token)
        assert approved_token.status == ApprovalStatus.APPROVED
        assert approved_token.used is True
        
        # Cannot approve again
        result = store.approve_token(token.token)
        assert result is False
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")
    
    def test_reject_token(self):
        """Test token rejection."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        token = store.create_token("draft_123", expiry_hours=24)
        
        # Reject token
        result = store.reject_token(token.token)
        assert result is True
        
        # Verify token is marked as rejected
        rejected_token = store.get_token(token.token)
        assert rejected_token.status == ApprovalStatus.REJECTED
        assert rejected_token.used is True
        
        # Cannot reject again
        result = store.reject_token(token.token)
        assert result is False
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")
    
    def test_invalid_token(self):
        """Test invalid token handling."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        
        # Approve non-existent token
        result = store.approve_token("invalid_token")
        assert result is False
        
        # Reject non-existent token
        result = store.reject_token("invalid_token")
        assert result is False
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")
    
    def test_draft_save_and_retrieve(self):
        """Test draft save and retrieve."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        
        draft = DraftRecord(
            draft_id="draft_123",
            topic="AI Agents",
            title="The Rise of AI Agents",
            content="Test content",
            hashtags=["#AI", "#Agents"],
            review_score=8,
            review_feedback="Good post"
        )
        
        store.save_draft(draft)
        retrieved = store.get_draft("draft_123")
        
        assert retrieved is not None
        assert retrieved.title == "The Rise of AI Agents"
        assert retrieved.review_score == 8
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")
    
    def test_draft_by_token(self):
        """Test retrieving draft by token."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        
        draft = DraftRecord(
            draft_id="draft_123",
            topic="AI Agents",
            title="The Rise of AI Agents",
            content="Test content",
            hashtags=["#AI", "#Agents"],
            review_score=8,
            review_feedback="Good post"
        )
        
        store.save_draft(draft)
        token = store.create_token("draft_123", expiry_hours=24)
        
        retrieved = store.get_draft_by_token(token.token)
        assert retrieved is not None
        assert retrieved.draft_id == "draft_123"
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")
    
    def test_mark_draft_published(self):
        """Test marking draft as published."""
        store = ApprovalStore(storage_path="test_approval_data.json")
        
        draft = DraftRecord(
            draft_id="draft_123",
            topic="AI Agents",
            title="The Rise of AI Agents",
            content="Test content",
            hashtags=["#AI", "#Agents"],
            review_score=8,
            review_feedback="Good post"
        )
        
        store.save_draft(draft)
        store.mark_draft_published("draft_123", "linkedin_post_123")
        
        retrieved = store.get_draft("draft_123")
        assert retrieved.published_at is not None
        assert retrieved.linkedin_post_id == "linkedin_post_123"
        
        # Cleanup
        import os
        if os.path.exists("test_approval_data.json"):
            os.remove("test_approval_data.json")


class TestApprovalService:
    """Tests for ApprovalService."""
    
    def test_create_draft(self):
        """Test draft creation."""
        service = ApprovalService()
        
        draft_id = service.create_draft(
            topic="AI Agents",
            title="The Rise of AI Agents",
            content="Test content about AI agents",
            hashtags=["#AI", "#Agents"],
            review_score=8,
            review_feedback="Good post",
            research_summary="AI agents are transforming industries"
        )
        
        assert draft_id is not None
        
        # Verify draft was saved
        draft = service.store.get_draft(draft_id)
        assert draft is not None
        assert draft.title == "The Rise of AI Agents"
        assert draft.approval_token is not None
        
        # Cleanup
        import os
        if os.path.exists("approval/approval_data.json"):
            os.remove("approval/approval_data.json")
    
    def test_approve_invalid_token(self):
        """Test approving with invalid token."""
        service = ApprovalService()
        
        success, message = service.approve("invalid_token")
        assert success is False
        assert "Invalid token" in message
    
    def test_reject_invalid_token(self):
        """Test rejecting with invalid token."""
        service = ApprovalService()
        
        success, message = service.reject("invalid_token")
        assert success is False
        assert "Invalid token" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
