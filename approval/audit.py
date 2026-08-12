"""Audit log system for approval workflow."""

from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class AuditEventType(str, Enum):
    """Audit event types."""
    DRAFT_CREATED = "draft_created"
    DRAFT_EDITED = "draft_edited"
    EMAIL_SENT = "email_sent"
    EMAIL_FAILED = "email_failed"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    PUBLISH_FAILED = "publish_failed"
    SCHEDULED = "scheduled"
    MEMORY_INDEXED = "memory_indexed"
    TOKEN_CREATED = "token_created"
    TOKEN_EXPIRED = "token_expired"


class AuditEvent(BaseModel):
    """Audit event model."""
    
    event_id: str = Field(description="Unique event identifier")
    event_type: AuditEventType = Field(description="Type of event")
    draft_id: Optional[str] = Field(default=None, description="Associated draft ID")
    token: Optional[str] = Field(default=None, description="Associated token")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    status: str = Field(default="success", description="Event status")
    details: Dict = Field(default_factory=dict, description="Additional event details")
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "draft_id": self.draft_id,
            "token": self.token,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status,
            "details": self.details
        }


class AuditLog:
    """Audit log manager."""
    
    def __init__(self, storage_path: str = "approval/audit_log.json"):
        """Initialize audit log.
        
        Args:
            storage_path: Path to audit log JSON file.
        """
        self.storage_path = storage_path
        self.events: List[AuditEvent] = []
        self._load()
    
    def _load(self) -> None:
        """Load audit log from disk."""
        import json
        from pathlib import Path
        
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    for event_data in data:
                        event = AuditEvent(
                            event_id=event_data["event_id"],
                            event_type=AuditEventType(event_data["event_type"]),
                            draft_id=event_data.get("draft_id"),
                            token=event_data.get("token"),
                            timestamp=datetime.fromisoformat(event_data["timestamp"]),
                            status=event_data.get("status", "success"),
                            details=event_data.get("details", {})
                        )
                        self.events.append(event)
        except Exception as e:
            from utils.logger import logger
            logger.error(f"Failed to load audit log: {e}")
            self.events = []
    
    def _save(self) -> None:
        """Save audit log to disk."""
        import json
        from pathlib import Path
        
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = [event.to_dict() for event in self.events]
            with open(path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            from utils.logger import logger
            logger.error(f"Failed to save audit log: {e}")
    
    def log_event(
        self,
        event_type: AuditEventType,
        draft_id: Optional[str] = None,
        token: Optional[str] = None,
        status: str = "success",
        **details
    ) -> None:
        """Log an audit event.
        
        Args:
            event_type: Type of event.
            draft_id: Associated draft ID.
            token: Associated token.
            status: Event status.
            **details: Additional event details.
        """
        import uuid
        
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            draft_id=draft_id,
            token=token,
            status=status,
            details=details
        )
        
        self.events.append(event)
        self._save()
    
    def get_events_for_draft(self, draft_id: str) -> List[AuditEvent]:
        """Get all events for a draft.
        
        Args:
            draft_id: Draft identifier.
            
        Returns:
            List of audit events.
        """
        return [e for e in self.events if e.draft_id == draft_id]
    
    def get_events_for_token(self, token: str) -> List[AuditEvent]:
        """Get all events for a token.
        
        Args:
            token: Token string.
            
        Returns:
            List of audit events.
        """
        return [e for e in self.events if e.token == token]
    
    def get_events_by_type(self, event_type: AuditEventType) -> List[AuditEvent]:
        """Get all events of a specific type.
        
        Args:
            event_type: Event type.
            
        Returns:
            List of audit events.
        """
        return [e for e in self.events if e.event_type == event_type]
    
    def cleanup_old_events(self, days: int = 30) -> int:
        """Clean up events older than specified days.
        
        Args:
            days: Number of days to keep.
            
        Returns:
            Number of events removed.
        """
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        original_count = len(self.events)
        self.events = [e for e in self.events if e.timestamp > cutoff]
        
        if len(self.events) < original_count:
            self._save()
        
        return original_count - len(self.events)
