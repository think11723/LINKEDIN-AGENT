"""Run all manual integration tests."""

import os
import sys
import subprocess
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Test files in order
TEST_FILES = [
    "test_env.py",
    "test_provider_factory.py",
    "test_provider_connection.py",
    "test_embeddings.py",
    "test_memory.py",
    "test_research_agent.py",
    "test_planner_agent.py",
    "test_writer_agent.py",
    "test_reviewer_agent.py",
    "test_graph_workflow.py",
    "test_scheduler.py",
    "test_linkedin_auth.py",
    "test_publish.py",
    "test_cli.py",
    "test_end_to_end.py",
]


def print_header(title: str):
    """Print header."""
    print("=" * 60)
    print(title)
    print("=" * 60)


def run_test(test_file: str) -> tuple[bool, str]:
    """Run a single test file.
    
    Args:
        test_file: Name of test file
        
    Returns:
        Tuple of (success, output)
    """
    test_path = Path(__file__).parent / test_file
    
    if not test_path.exists():
        return False, f"Test file not found: {test_file}"
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per test
        )
        
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Test timed out after 5 minutes"
    except Exception as e:
        return False, f"Test execution failed: {str(e)}"


def main():
    print_header("Manual Integration Test Suite")
    
    results = {}
    start_time = time.time()
    
    # Run each test
    for test_file in TEST_FILES:
        test_name = test_file.replace("test_", "").replace(".py", "").replace("_", " ").title()
        print(f"\nRunning: {test_name}...")
        
        success, output = run_test(test_file)
        results[test_name] = success
        
        if success:
            print(f"  ✓ PASSED")
        else:
            print(f"  ✗ FAILED")
            # Print first few lines of error
            lines = output.split('\n')[:5]
            for line in lines:
                if line.strip():
                    print(f"    {line}")
    
    duration = time.time() - start_time
    
    # Print summary
    print_header("Test Results")
    
    passed = [name for name, success in results.items() if success]
    failed = [name for name, success in results.items() if not success]
    
    print("\nPASSED")
    for name in passed:
        print(f"✓ {name}")
    
    if failed:
        print("\nFAILED")
        for name in failed:
            print(f"✗ {name}")
    
    print("\n" + "=" * 60)
    print(f"Total")
    print(f"  Passed: {len(passed)}")
    print(f"  Failed: {len(failed)}")
    print(f"  Duration: {duration:.2f}s")
    print("=" * 60)
    
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
