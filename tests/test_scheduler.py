"""Tests for scheduler job lifecycle."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from scheduler.service import SchedulerService
from scheduler.models import ScheduledJob, JobStatus


class TestSchedulerService:
    """Test cases for SchedulerService."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def scheduler_service(self, temp_dir):
        """Create a SchedulerService instance with temp storage."""
        service = SchedulerService()
        # Override storage path to use temp directory
        service.job_store.storage_path = Path(temp_dir) / "jobs.json"
        service.job_store.storage_path.parent.mkdir(parents=True, exist_ok=True)
        return service
    
    def test_schedule_post(self, scheduler_service):
        """Test scheduling a post."""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        job_id = scheduler_service.schedule_post(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"],
            scheduled_time=scheduled_time
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
        
        # Verify job was stored
        job = scheduler_service.get_job(job_id)
        assert job is not None
        assert job.title == "Test Post"
        assert job.status == JobStatus.PENDING
    
    def test_schedule_post_in_minutes(self, scheduler_service):
        """Test scheduling a post in minutes."""
        job_id = scheduler_service.schedule_post_in_minutes(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"],
            minutes=30
        )
        
        assert job_id is not None
        job = scheduler_service.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
    
    def test_schedule_post_in_hours(self, scheduler_service):
        """Test scheduling a post in hours."""
        job_id = scheduler_service.schedule_post_in_hours(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"],
            hours=2
        )
        
        assert job_id is not None
        job = scheduler_service.get_job(job_id)
        assert job is not None
        assert job.status == JobStatus.PENDING
    
    def test_schedule_post_with_image(self, scheduler_service):
        """Test scheduling a post with an image."""
        job_id = scheduler_service.schedule_post(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"],
            scheduled_time=datetime.utcnow() + timedelta(hours=1),
            image_path="/path/to/image.png"
        )
        
        assert job_id is not None
        job = scheduler_service.get_job(job_id)
        assert job is not None
        assert job.image_path == "/path/to/image.png"
    
    def test_cancel_job(self, scheduler_service):
        """Test canceling a scheduled job."""
        job_id = scheduler_service.schedule_post_in_minutes(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"],
            minutes=30
        )
        
        result = scheduler_service.cancel_job(job_id)
        assert result is True
        
        job = scheduler_service.get_job(job_id)
        assert job.status == JobStatus.CANCELLED
    
    def test_get_pending_jobs(self, scheduler_service):
        """Test getting pending jobs."""
        # Schedule multiple jobs
        scheduler_service.schedule_post_in_minutes(
            title="Post 1",
            content="Content 1",
            hashtags=["#Test1"],
            minutes=30
        )
        
        scheduler_service.schedule_post_in_minutes(
            title="Post 2",
            content="Content 2",
            hashtags=["#Test2"],
            minutes=60
        )
        
        pending_jobs = scheduler_service.get_pending_jobs()
        assert len(pending_jobs) == 2
    
    def test_get_all_jobs(self, scheduler_service):
        """Test getting all jobs."""
        scheduler_service.schedule_post_in_minutes(
            title="Post 1",
            content="Content 1",
            hashtags=["#Test"],
            minutes=30
        )
        
        all_jobs = scheduler_service.get_all_jobs()
        assert len(all_jobs) == 1
    
    def test_get_stats(self, scheduler_service):
        """Test getting scheduler statistics."""
        scheduler_service.schedule_post_in_minutes(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"],
            minutes=30
        )
        
        stats = scheduler_service.get_stats()
        assert stats["total_jobs"] == 1
        assert stats["pending_jobs"] == 1
        assert "storage_path" in stats
    
    def test_clear_all_jobs(self, scheduler_service):
        """Test clearing all jobs."""
        scheduler_service.schedule_post_in_minutes(
            title="Test Post",
            content="Test content",
            hashtags=["#Test"],
            minutes=30
        )
        
        scheduler_service.clear_all_jobs()
        
        stats = scheduler_service.get_stats()
        assert stats["total_jobs"] == 0
    
    def test_schedule_post_invalid_time(self, scheduler_service):
        """Test scheduling a post with invalid time (past)."""
        past_time = datetime.utcnow() - timedelta(hours=1)
        
        with pytest.raises(ValueError, match="Scheduled time must be in the future"):
            scheduler_service.schedule_post(
                title="Test Post",
                content="Test content",
                hashtags=["#Test"],
                scheduled_time=past_time
            )
