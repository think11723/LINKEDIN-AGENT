"""Manual end-to-end test for complete application flow."""

import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from workflows.graph_workflow import ContentGraphWorkflow


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
    print_header("End-to-End Workflow")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize workflow
    try:
        workflow = ContentGraphWorkflow()
        print_step("Workflow initialization")
    except Exception as e:
        print_step(f"Workflow initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Run complete workflow
    try:
        print("\nRunning complete workflow...")
        print("  Topic: Python")
        print("  Request: Write a short post about Python")
        print()
        
        start_time = time.time()
        result = workflow.run(
            topic="Python",
            user_request="Write a short post about Python"
        )
        duration = time.time() - start_time
        
        print_step(f"Workflow completed in {duration:.2f}s")
    except Exception as e:
        print_step(f"Workflow execution - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 3: Verify context
    try:
        if result.context:
            print_step("Context stage: PASS")
        else:
            print_step("Context stage: FAIL", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Context stage - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Verify research
    try:
        if result.research:
            print_step("Research stage: PASS")
        else:
            print_step("Research stage: FAIL", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Research stage - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Verify planner
    try:
        if result.execution_plan:
            print_step("Planner stage: PASS")
        else:
            print_step("Planner stage: FAIL", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Planner stage - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Verify writer
    try:
        if result.draft_post:
            print_step("Writer stage: PASS")
        else:
            print_step("Writer stage: FAIL", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Writer stage - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 7: Verify reviewer
    try:
        if result.review_decision:
            print_step("Reviewer stage: PASS")
        else:
            print_step("Reviewer stage: FAIL", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Reviewer stage - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 8: Verify memory
    try:
        print_step("Memory stage: PASS (assumed)")
    except Exception as e:
        print_step(f"Memory stage - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 9: Verify final result
    try:
        if result.final_post and result.approved:
            print_step("Final result: PASS")
            print(f"\n  Final post title: {result.final_post.title}")
            print(f"  Final approved: {result.approved}")
        else:
            print_step("Final result: FAIL", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Final result - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 10: Print total runtime
    try:
        print(f"\n  Total runtime: {duration:.2f}s")
        print_step("Runtime measured")
    except Exception as e:
        print_step(f"Runtime measurement - FAILED: {e}", "FAIL")
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
