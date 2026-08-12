"""Storage interface abstraction layer."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, List
from approval.models import ApprovalToken, DraftRecord


class StorageInterface(ABC):
    """Abstract interface for approval storage implementations."""
    
    @abstractmethod
    def save_token(self, token: ApprovalToken) -> None:
        """Save an approval token.
        
        Args:
            token: ApprovalToken to save.
        """
        pass
    
    @abstractmethod
    def get_token(self, token: str) -> Optional[ApprovalToken]:
        """Get a token by ID.
        
        Args:
            token: Token string.
            
        Returns:
            ApprovalToken or None if not found.
        """
        pass
    
    @abstractmethod
    def update_token(self, token: ApprovalToken) -> None:
        """Update an approval token.
        
        Args:
            token: ApprovalToken to update.
        """
        pass
    
    @abstractmethod
    def delete_token(self, token: str) -> bool:
        """Delete a token.
        
        Args:
            token: Token string.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    def save_draft(self, draft: DraftRecord) -> None:
        """Save a draft record.
        
        Args:
            draft: DraftRecord to save.
        """
        pass
    
    @abstractmethod
    def get_draft(self, draft_id: str) -> Optional[DraftRecord]:
        """Get a draft by ID.
        
        Args:
            draft_id: Draft identifier.
            
        Returns:
            DraftRecord or None if not found.
        """
        pass
    
    @abstractmethod
    def update_draft(self, draft: DraftRecord) -> None:
        """Update a draft record.
        
        Args:
            draft: DraftRecord to update.
        """
        pass
    
    @abstractmethod
    def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft.
        
        Args:
            draft_id: Draft identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        pass
    
    @abstractmethod
    def get_all_tokens(self) -> Dict[str, ApprovalToken]:
        """Get all tokens.
        
        Returns:
            Dictionary mapping token strings to ApprovalToken objects.
        """
        pass
    
    @abstractmethod
    def get_all_drafts(self) -> Dict[str, DraftRecord]:
        """Get all drafts.
        
        Returns:
            Dictionary mapping draft IDs to DraftRecord objects.
        """
        pass
    
    @abstractmethod
    def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens.
        
        Returns:
            Number of tokens cleaned up.
        """
        pass
