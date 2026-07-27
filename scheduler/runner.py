"""Runner for LinkedIn Content Scheduler.

This module executes scheduled jobs by calling the LinkedInService.
"""

import time
from typing import Optional
from scheduler.models import ScheduledJob, JobStatus
from scheduler.job_store import JobStore
from services.linkedin import LinkedInService
from utils.logger import logger


class SchedulerRunner:
    """Runner for executing scheduled jobs."""
    
    def __init__(self, job_store: JobStore):
        """Initialize the scheduler runner.
        
        Args:
            job_store: Job store for retrieving and updating jobs.
        """
        self.job_store = job_store
        self.linkedin_service = LinkedInService()
        self.running = False
    
    def start(self, check_interval: int = 60) -> None:
        """Start the scheduler runner.
        
        Args:
            check_interval: Seconds between job checks.
        """
        self.running = True
        logger.info(f"Scheduler runner started with check interval: {check_interval}s")
        
        while self.running:
            try:
                self._check_and_execute_jobs()
                time.sleep(check_interval)
            except KeyboardInterrupt:
                logger.info("Scheduler runner stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Error in scheduler runner: {e}")
                time.sleep(check_interval)
    
    def stop(self) -> None:
        """Stop the scheduler runner."""
        self.running = False
        logger.info("Scheduler runner stopped")
    
    def _check_and_execute_jobs(self) -> None:
        """Check for due jobs and execute them."""
        due_jobs = self.job_store.get_due_jobs()
        
        if not due_jobs:
            return
        
        logger.info(f"Found {len(due_jobs)} due jobs")
        
        for job in due_jobs:
            self._execute_job(job)
    
    def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a single job.
        
        Args:
            job: ScheduledJob to execute.
        """
        logger.info(f"Executing job {job.job_id}")
        
        # Mark job as running
        job.mark_running()
        self.job_store.update(job)
        
        try:
            # Authenticate with LinkedIn
            if not self.linkedin_service.authenticate():
                raise Exception("LinkedIn authentication failed")
            
            # Publish the post
            result = self.linkedin_service.publish_post(
                job.title,
                job.content,
                job.hashtags,
                job.image_path
            )
            
            if "error" in result:
                raise Exception(result["error"])
            
            # Mark job as completed
            job.mark_completed()
            self.job_store.update(job)
            logger.info(f"Job {job.job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}")
            
            # Check if we can retry
            if job.can_retry():
                job.increment_retry()
                job.status = JobStatus.PENDING  # Reset to pending for retry
                self.job_store.update(job)
                logger.info(f"Job {job.job_id} will be retried (attempt {job.retry_count}/{job.max_retries})")
            else:
                job.mark_failed(str(e))
                self.job_store.update(job)
                logger.error(f"Job {job.job_id} failed permanently after {job.retry_count} retries")
    
    def execute_once(self) -> int:
        """Execute due jobs once and return count.
        
        Returns:
            Number of jobs executed.
        """
        due_jobs = self.job_store.get_due_jobs()
        count = 0
        
        for job in due_jobs:
            self._execute_job(job)
            count += 1
        
        return count
