"""Models for LinkedIn Content Scheduler.

This module defines data models for scheduled LinkedIn posts.
"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """Status of a scheduled job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledJob(BaseModel):
    """Model for a scheduled LinkedIn post."""
    
    job_id: str = Field(description="Unique identifier for the job")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    hashtags: list = Field(default_factory=list, description="Post hashtags")
    image_path: Optional[str] = Field(default=None, description="Optional path to image file")
    scheduled_time: datetime = Field(description="Scheduled publication time")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Job status")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    
    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries
    
    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.updated_at = datetime.utcnow()
    
    def mark_running(self) -> None:
        """Mark job as running."""
        self.status = JobStatus.RUNNING
        self.updated_at = datetime.utcnow()
    
    def mark_completed(self) -> None:
        """Mark job as completed."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_failed(self, error_message: str) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.error_message = error_message
        self.updated_at = datetime.utcnow()
    
    def mark_cancelled(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.updated_at = datetime.utcnow()
