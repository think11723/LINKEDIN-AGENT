"""Job store for LinkedIn Content Scheduler.

This module provides persistent storage for scheduled jobs.
"""

from typing import List, Optional
import json
import uuid
from pathlib import Path
from scheduler.models import ScheduledJob, JobStatus
from utils.logger import logger


class JobStore:
    """Persistent storage for scheduled jobs."""
    
    def __init__(self, storage_path: str = "scheduler/jobs.json"):
        """Initialize the job store.
        
        Args:
            storage_path: Path to store job data on disk.
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.jobs: dict = {}  # job_id -> ScheduledJob
        self._load_from_disk()
    
    def _load_from_disk(self) -> None:
        """Load jobs from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for job_id, job_data in data.items():
                        self.jobs[job_id] = ScheduledJob(**job_data)
                logger.info(f"Loaded {len(self.jobs)} jobs from disk")
            except Exception as e:
                logger.error(f"Failed to load jobs: {e}")
                self.jobs = {}
    
    def _save_to_disk(self) -> None:
        """Save jobs to disk."""
        try:
            data = {job_id: job.dict() for job_id, job in self.jobs.items()}
            with open(self.storage_path, 'w') as f:
                json.dump(data, f, default=str)
            logger.info(f"Saved {len(self.jobs)} jobs to disk")
        except Exception as e:
            logger.error(f"Failed to save jobs: {e}")
    
    def add(self, job: ScheduledJob) -> None:
        """Add a job to the store.
        
        Args:
            job: ScheduledJob to add.
        """
        self.jobs[job.job_id] = job
        self._save_to_disk()
        logger.info(f"Added job {job.job_id} to store")
    
    def get(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a job by ID.
        
        Args:
            job_id: Job identifier.
            
        Returns:
            ScheduledJob or None if not found.
        """
        return self.jobs.get(job_id)
    
    def get_pending_jobs(self) -> List[ScheduledJob]:
        """Get all pending jobs.
        
        Returns:
            List of pending ScheduledJob objects.
        """
        return [job for job in self.jobs.values() if job.status == JobStatus.PENDING]
    
    def get_due_jobs(self) -> List[ScheduledJob]:
        """Get jobs that are due for execution.
        
        Returns:
            List of due ScheduledJob objects.
        """
        from datetime import datetime
        now = datetime.utcnow()
        return [job for job in self.jobs.values() 
                if job.status == JobStatus.PENDING and job.scheduled_time <= now]
    
    def update(self, job: ScheduledJob) -> None:
        """Update a job in the store.
        
        Args:
            job: ScheduledJob to update.
        """
        if job.job_id in self.jobs:
            self.jobs[job.job_id] = job
            self._save_to_disk()
            logger.info(f"Updated job {job.job_id}")
    
    def delete(self, job_id: str) -> bool:
        """Delete a job from the store.
        
        Args:
            job_id: Job identifier.
            
        Returns:
            True if deleted, False if not found.
        """
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save_to_disk()
            logger.info(f"Deleted job {job_id}")
            return True
        return False
    
    def get_all_jobs(self) -> List[ScheduledJob]:
        """Get all jobs.
        
        Returns:
            List of all ScheduledJob objects.
        """
        return list(self.jobs.values())
    
    def clear(self) -> None:
        """Clear all jobs from the store."""
        self.jobs = {}
        self._save_to_disk()
        logger.info("Job store cleared")
    
    def get_stats(self) -> dict:
        """Get statistics about the job store.
        
        Returns:
            Dictionary with job statistics.
        """
        status_counts = {}
        for job in self.jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total_jobs": len(self.jobs),
            "status_counts": status_counts,
            "pending_jobs": len(self.get_pending_jobs()),
            "storage_path": str(self.storage_path)
        }
