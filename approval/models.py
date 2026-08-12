"""Approval models for Human-in-the-Loop system."""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ApprovalStatus(str, Enum):
    """Approval status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalToken(BaseModel):
    """Approval token model."""
    
    token: str = Field(description="Unique approval token (UUID)")
    draft_id: str = Field(description="Draft identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Token creation time")
    expires_at: datetime = Field(description="Token expiry time")
    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING, description="Approval status")
    used: bool = Field(default=False, description="Whether token has been used")
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if token is valid (not expired, not used, pending)."""
        return not self.used and not self.is_expired() and self.status == ApprovalStatus.PENDING
    
    def is_approved(self) -> bool:
        """Check if token is approved."""
        return self.status == ApprovalStatus.APPROVED


class DraftVersion(BaseModel):
    """Draft version model."""
    
    version_number: int = Field(description="Version number")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    hashtags: List[str] = Field(default_factory=list, description="Post hashtags")
    edited_at: datetime = Field(default_factory=datetime.utcnow, description="Edit timestamp")
    edited_by: str = Field(default="owner", description="Who edited this version")


class DraftRecord(BaseModel):
    """Draft record for storage."""
    
    draft_id: str = Field(description="Draft identifier")
    topic: str = Field(description="Original topic")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    hashtags: List[str] = Field(default_factory=list, description="Post hashtags")
    image_path: Optional[str] = Field(default=None, description="Path to generated image")
    review_score: int = Field(description="Review score (1-10)")
    review_feedback: str = Field(description="Reviewer feedback")
    research_summary: Optional[str] = Field(default=None, description="Research summary")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Draft creation time")
    published_at: Optional[datetime] = Field(default=None, description="Publish timestamp")
    linkedin_post_id: Optional[str] = Field(default=None, description="LinkedIn post ID after publishing")
    approval_token: Optional[str] = Field(default=None, description="Associated approval token")
    current_version: int = Field(default=1, description="Current version number")
    versions: List[DraftVersion] = Field(default_factory=list, description="Version history")
    scheduled_publish_time: Optional[datetime] = Field(default=None, description="Scheduled publish time")
    publish_failure_reason: Optional[str] = Field(default=None, description="Reason for publish failure")
    
    def add_version(self, title: str, content: str, hashtags: List[str], edited_by: str = "owner") -> None:
        """Add a new version to the draft.
        
        Args:
            title: New title.
            content: New content.
            hashtags: New hashtags.
            edited_by: Who made the edit.
        """
        self.current_version += 1
        version = DraftVersion(
            version_number=self.current_version,
            title=title,
            content=content,
            hashtags=hashtags,
            edited_by=edited_by
        )
        self.versions.append(version)
        # Update current values
        self.title = title
        self.content = content
        self.hashtags = hashtags
