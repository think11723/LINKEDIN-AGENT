"""Approval token storage using storage abstraction layer."""

import uuid
from typing import Optional
from datetime import datetime, timedelta
from approval.models import ApprovalToken, ApprovalStatus, DraftRecord
from approval.storage.interface import StorageInterface
from approval.storage.json_storage import JSONStorage
from utils.logger import logger


class ApprovalStore:
    """Storage for approval tokens and drafts using storage abstraction."""
    
    def __init__(self, storage: Optional[StorageInterface] = None, storage_path: str = "approval/approval_data.json"):
        """Initialize the approval store.
        
        Args:
            storage: StorageInterface implementation (uses JSONStorage if None).
            storage_path: Path for JSON storage (only used if storage is None).
        """
        self.storage = storage if storage is not None else JSONStorage(storage_path)
        logger.info("Approval store initialized with storage backend")
    
    def create_token(self, draft_id: str, expiry_hours: int = 24) -> ApprovalToken:
        """Create a new approval token.
        
        Args:
            draft_id: Draft identifier.
            expiry_hours: Token expiry in hours (default 24).
            
        Returns:
            ApprovalToken object.
        """
        token_str = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=expiry_hours)
        
        token = ApprovalToken(
            token=token_str,
            draft_id=draft_id,
            expires_at=expires_at,
            status=ApprovalStatus.PENDING
        )
        
        self.storage.save_token(token)
        logger.info(f"Created approval token {token_str[:8]}... for draft {draft_id}")
        return token
    
    def get_token(self, token: str) -> Optional[ApprovalToken]:
        """Get a token by ID.
        
        Args:
            token: Token string.
            
        Returns:
            ApprovalToken or None if not found.
        """
        return self.storage.get_token(token)
    
    def approve_token(self, token: str) -> bool:
        """Mark a token as approved.
        
        Args:
            token: Token string.
            
        Returns:
            True if successful, False otherwise.
        """
        approval_token = self.get_token(token)
        if not approval_token:
            return False
        
        if not approval_token.is_valid():
            return False
        
        approval_token.status = ApprovalStatus.APPROVED
        approval_token.used = True
        self.storage.update_token(approval_token)
        logger.info(f"Approved token {token[:8]}...")
        return True
    
    def reject_token(self, token: str) -> bool:
        """Mark a token as rejected.
        
        Args:
            token: Token string.
            
        Returns:
            True if successful, False otherwise.
        """
        approval_token = self.get_token(token)
        if not approval_token:
            return False
        
        if not approval_token.is_valid():
            return False
        
        approval_token.status = ApprovalStatus.REJECTED
        approval_token.used = True
        self.storage.update_token(approval_token)
        logger.info(f"Rejected token {token[:8]}...")
        return True
    
    def save_draft(self, draft: DraftRecord) -> None:
        """Save a draft record.
        
        Args:
            draft: DraftRecord to save.
        """
        self.storage.save_draft(draft)
        logger.info(f"Saved draft {draft.draft_id}")
    
    def get_draft(self, draft_id: str) -> Optional[DraftRecord]:
        """Get a draft by ID.
        
        Args:
            draft_id: Draft identifier.
            
        Returns:
            DraftRecord or None if not found.
        """
        return self.storage.get_draft(draft_id)
    
    def get_draft_by_token(self, token: str) -> Optional[DraftRecord]:
        """Get a draft by approval token.
        
        Args:
            token: Approval token string.
            
        Returns:
            DraftRecord or None if not found.
        """
        approval_token = self.get_token(token)
        if not approval_token:
            return None
        return self.get_draft(approval_token.draft_id)
    
    def get_token_by_draft_id(self, draft_id: str) -> Optional[ApprovalToken]:
        """Get a token by draft ID.
        
        Args:
            draft_id: Draft identifier.
            
        Returns:
            ApprovalToken or None if not found.
        """
        return self.storage.get_token_by_draft_id(draft_id)
    
    def mark_draft_published(self, draft_id: str, linkedin_post_id: str) -> None:
        """Mark a draft as published.
        
        Args:
            draft_id: Draft identifier.
            linkedin_post_id: LinkedIn post ID.
        """
        draft = self.get_draft(draft_id)
        if draft:
            draft.published_at = datetime.utcnow()
            draft.linkedin_post_id = linkedin_post_id
            self.storage.update_draft(draft)
            logger.info(f"Marked draft {draft_id} as published with LinkedIn ID {linkedin_post_id}")
    
    def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens.
        
        Returns:
            Number of tokens cleaned up.
        """
        return self.storage.cleanup_expired_tokens()
