"""Manual test for scheduler service."""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from services.scheduler import SchedulerService
from models.models import LinkedInPost


def print_header(title: str):
    """Print test header."""
    print("=" * 60)
    print(f"TEST: {title}")
    print("=" * 60)


def print_step(step: str, status: str = "PASS"):
    """Print test step."""
    symbol = "✓" if status == "PASS" else "✗"
    print(f"{symbol} {step}")


def main():
    print_header("Scheduler Service")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize scheduler
    try:
        scheduler = SchedulerService()
        print_step("SchedulerService initialization")
    except Exception as e:
        print_step(f"Scheduler initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Clear existing jobs
    try:
        scheduler.clear_jobs()
        print_step("Existing jobs cleared")
    except Exception as e:
        print_step(f"Clear jobs - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Create test post
    try:
        test_post = LinkedInPost(
            title="Scheduled Test Post",
            content="This is a test post for scheduling.",
            hashtags=["#test", "#scheduler"]
        )
        print_step("Test post created")
    except Exception as e:
        print_step(f"Create test post - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Schedule a job
    try:
        scheduled_time = datetime.now() + timedelta(minutes=5)
        job_id = scheduler.schedule_post(
            title=test_post.title,
            content=test_post.content,
            hashtags=test_post.hashtags,
            scheduled_time=scheduled_time
        )
        print_step(f"Job scheduled: {job_id}")
    except Exception as e:
        print_step(f"Schedule job - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: List jobs
    try:
        jobs = scheduler.list_jobs()
        print(f"  Total jobs: {len(jobs)}")
        print_step("Job list retrieved")
    except Exception as e:
        print_step(f"List jobs - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Get job details
    try:
        if jobs:
            job = jobs[0]
            print(f"  Job ID: {job.get('job_id')}")
            print(f"  Scheduled time: {job.get('scheduled_time')}")
            print_step("Job details retrieved")
    except Exception as e:
        print_step(f"Get job details - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 7: Get statistics
    try:
        stats = scheduler.get_stats()
        print(f"  Total jobs: {stats.get('total_jobs', 0)}")
        print(f"  Pending jobs: {stats.get('pending_jobs', 0)}")
        print_step("Statistics retrieved")
    except Exception as e:
        print_step(f"Get statistics - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 8: Cancel job
    try:
        if job_id:
            cancelled = scheduler.cancel_job(job_id)
            print(f"  Job cancelled: {cancelled}")
            print_step("Job cancellation")
    except Exception as e:
        print_step(f"Cancel job - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 9: Clear jobs (cleanup)
    try:
        scheduler.clear_jobs()
        print_step("Jobs cleared (cleanup)")
    except Exception as e:
        print_step(f"Clear jobs (cleanup) - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("Summary: PASS")
    else:
        print("Summary: FAIL")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
