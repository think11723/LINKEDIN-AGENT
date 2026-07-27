"""Standalone CLI for running the scheduler.

This script starts the scheduler runner to execute scheduled jobs.
"""

import sys
from scheduler.service import SchedulerService
from utils.logger import logger


def main():
    """Main entry point for the scheduler runner."""
    print("LinkedIn Content Agent - Scheduler Runner")
    print("=" * 50)
    
    scheduler_service = SchedulerService()
    
    # Show stats
    stats = scheduler_service.get_stats()
    print(f"\nScheduler Stats:")
    print(f"  Total Jobs: {stats['total_jobs']}")
    print(f"  Pending Jobs: {stats['pending_jobs']}")
    print(f"  Status Counts: {stats['status_counts']}")
    
    # Ask for check interval
    from rich.prompt import Prompt
    check_interval = Prompt.ask("\nCheck interval (seconds)", default="60")
    check_interval = int(check_interval)
    
    print(f"\nStarting scheduler runner with {check_interval}s interval...")
    print("Press Ctrl+C to stop\n")
    
    try:
        scheduler_service.start_runner(check_interval)
    except KeyboardInterrupt:
        print("\n\nScheduler runner stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
