"""JSON storage implementation for approval system."""

import json
from pathlib import Path
from typing import Optional, Dict
from approval.storage.interface import StorageInterface
from approval.models import ApprovalToken, ApprovalStatus
from utils.logger import logger


class JSONStorage(StorageInterface):
    """JSON file-based storage implementation."""
    
    def __init__(self, storage_path: str = "approval/approval_data.json"):
        """Initialize JSON storage.
        
        Args:
            storage_path: Path to JSON storage file.
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.tokens: Dict[str, ApprovalToken] = {}
        self.drafts: Dict[str, object] = {}
        self._load()
    
    def _load(self) -> None:
        """Load data from disk."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    
                    # Load tokens
                    for token_data in data.get("tokens", []):
                        token = ApprovalToken(**token_data)
                        self.tokens[token.token] = token
                    
                    # Load drafts
                    for draft_data in data.get("drafts", []):
                        self.drafts[draft_data["draft_id"]] = draft_data
                    
                    logger.info(f"Loaded {len(self.tokens)} tokens and {len(self.drafts)} drafts from JSON")
        except Exception as e:
            logger.error(f"Failed to load JSON storage: {e}")
            self.tokens = {}
            self.drafts = {}
    
    def _save(self) -> None:
        """Save data to disk."""
        try:
            data = {
                "tokens": [token.model_dump() for token in self.tokens.values()],
                "drafts": list(self.drafts.values())
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.debug(f"Saved {len(self.tokens)} tokens and {len(self.drafts)} drafts to JSON")
        except Exception as e:
            logger.error(f"Failed to save JSON storage: {e}")
    
    def save_token(self, token: ApprovalToken) -> None:
        """Save an approval token."""
        self.tokens[token.token] = token
        self._save()
    
    def get_token(self, token: str) -> Optional[ApprovalToken]:
        """Get a token by ID."""
        return self.tokens.get(token)
    
    def update_token(self, token: ApprovalToken) -> None:
        """Update an approval token."""
        if token.token in self.tokens:
            self.tokens[token.token] = token
            self._save()
    
    def delete_token(self, token: str) -> bool:
        """Delete a token."""
        if token in self.tokens:
            del self.tokens[token]
            self._save()
            return True
        return False
    
    def save_draft(self, draft: object) -> None:
        """Save a draft record."""
        self.drafts[draft.draft_id] = draft.model_dump() if hasattr(draft, 'model_dump') else draft
        self._save()
    
    def get_draft(self, draft_id: str) -> Optional[object]:
        """Get a draft by ID."""
        draft_data = self.drafts.get(draft_id)
        if draft_data:
            from approval.models import DraftRecord
            return DraftRecord(**draft_data)
        return None
    
    def update_draft(self, draft: object) -> None:
        """Update a draft record."""
        if draft.draft_id in self.drafts:
            self.drafts[draft.draft_id] = draft.model_dump() if hasattr(draft, 'model_dump') else draft
            self._save()
    
    def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft."""
        if draft_id in self.drafts:
            del self.drafts[draft_id]
            self._save()
            return True
        return False
    
    def get_all_tokens(self) -> Dict[str, ApprovalToken]:
        """Get all tokens."""
        return self.tokens.copy()
    
    def get_all_drafts(self) -> Dict[str, object]:
        """Get all drafts."""
        return self.drafts.copy()
    
    def get_token_by_draft_id(self, draft_id: str) -> Optional[ApprovalToken]:
        """Get a token by draft ID.
        
        Args:
            draft_id: Draft identifier.
            
        Returns:
            ApprovalToken or None if not found.
        """
        for token in self.tokens.values():
            if token.draft_id == draft_id:
                return token
        return None
    
    def cleanup_expired_tokens(self) -> int:
        """Clean up expired tokens."""
        count = 0
        tokens_to_remove = []
        
        for token_str, token in self.tokens.items():
            if token.is_expired() and token.status == ApprovalStatus.PENDING:
                token.status = ApprovalStatus.EXPIRED
                tokens_to_remove.append(token_str)
                count += 1
        
        for token_str in tokens_to_remove:
            del self.tokens[token_str]
        
        if count > 0:
            self._save()
            logger.info(f"Cleaned up {count} expired tokens")
        
        return count
