"""Scheduler Service for LinkedIn Content Agent.

This module orchestrates the scheduling system for LinkedIn posts.
"""

from typing import Optional
from datetime import datetime, timedelta
import uuid
from scheduler.models import ScheduledJob, JobStatus
from scheduler.job_store import JobStore
from scheduler.runner import SchedulerRunner
from utils.logger import logger


class SchedulerService:
    """Service for managing scheduled LinkedIn posts."""
    
    def __init__(self):
        """Initialize the scheduler service."""
        self.job_store = JobStore()
        self.runner = SchedulerRunner(self.job_store)
        logger.info("Scheduler service initialized")
    
    def schedule_post(
        self,
        title: str,
        content: str,
        hashtags: list,
        scheduled_time: datetime,
        image_path: Optional[str] = None,
        max_retries: int = 3
    ) -> str:
        """Schedule a LinkedIn post for future publication.
        
        Args:
            title: Post title.
            content: Post content.
            hashtags: Post hashtags.
            scheduled_time: When to publish the post.
            image_path: Optional path to image file.
            max_retries: Maximum retry attempts on failure.
            
        Returns:
            Job ID of the scheduled job.
        """
        # Validate scheduled time is in the future
        if scheduled_time <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        
        # Create job
        job = ScheduledJob(
            job_id=str(uuid.uuid4()),
            title=title,
            content=content,
            hashtags=hashtags,
            image_path=image_path,
            scheduled_time=scheduled_time,
            status=JobStatus.PENDING,
            max_retries=max_retries
        )
        
        # Store job
        self.job_store.add(job)
        
        logger.info(f"Scheduled post for {scheduled_time} with job ID: {job.job_id}")
        return job.job_id
    
    def schedule_post_in_minutes(
        self,
        title: str,
        content: str,
        hashtags: list,
        minutes: int,
        image_path: Optional[str] = None,
        max_retries: int = 3
    ) -> str:
        """Schedule a LinkedIn post N minutes from now.
        
        Args:
            title: Post title.
            content: Post content.
            hashtags: Post hashtags.
            minutes: Minutes from now to schedule.
            image_path: Optional path to image file.
            max_retries: Maximum retry attempts on failure.
            
        Returns:
            Job ID of the scheduled job.
        """
        scheduled_time = datetime.utcnow() + timedelta(minutes=minutes)
        return self.schedule_post(title, content, hashtags, scheduled_time, image_path, max_retries)
    
    def schedule_post_in_hours(
        self,
        title: str,
        content: str,
        hashtags: list,
        hours: int,
        image_path: Optional[str] = None,
        max_retries: int = 3
    ) -> str:
        """Schedule a LinkedIn post N hours from now.
        
        Args:
            title: Post title.
            content: Post content.
            hashtags: Post hashtags.
            hours: Hours from now to schedule.
            image_path: Optional path to image file.
            max_retries: Maximum retry attempts on failure.
            
        Returns:
            Job ID of the scheduled job.
        """
        scheduled_time = datetime.utcnow() + timedelta(hours=hours)
        return self.schedule_post(title, content, hashtags, scheduled_time, image_path, max_retries)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled job.
        
        Args:
            job_id: Job identifier.
            
        Returns:
            True if cancelled, False if not found.
        """
        job = self.job_store.get(job_id)
        if not job:
            return False
        
        if job.status != JobStatus.PENDING:
            logger.warning(f"Cannot cancel job {job_id} with status {job.status}")
            return False
        
        job.mark_cancelled()
        self.job_store.update(job)
        logger.info(f"Cancelled job {job_id}")
        return True
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a job by ID.
        
        Args:
            job_id: Job identifier.
            
        Returns:
            ScheduledJob or None if not found.
        """
        return self.job_store.get(job_id)
    
    def get_pending_jobs(self) -> list:
        """Get all pending jobs.
        
        Returns:
            List of pending ScheduledJob objects.
        """
        return self.job_store.get_pending_jobs()
    
    def get_all_jobs(self) -> list:
        """Get all jobs.
        
        Returns:
            List of all ScheduledJob objects.
        """
        return self.job_store.get_all_jobs()
    
    def execute_due_jobs(self) -> int:
        """Execute due jobs once.
        
        Returns:
            Number of jobs executed.
        """
        return self.runner.execute_once()
    
    def start_runner(self, check_interval: int = 60) -> None:
        """Start the continuous scheduler runner.
        
        Args:
            check_interval: Seconds between job checks.
        """
        self.runner.start(check_interval)
    
    def stop_runner(self) -> None:
        """Stop the scheduler runner."""
        self.runner.stop()
    
    def get_stats(self) -> dict:
        """Get scheduler statistics.
        
        Returns:
            Dictionary with scheduler statistics.
        """
        return self.job_store.get_stats()
    
    def clear_all_jobs(self) -> None:
        """Clear all jobs from the scheduler."""
        self.job_store.clear()
        logger.info("All jobs cleared from scheduler")
