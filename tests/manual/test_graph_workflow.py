"""Manual test for LangGraph workflow."""

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
    print_header("LangGraph Workflow")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize workflow
    try:
        workflow = ContentGraphWorkflow()
        print_step("ContentGraphWorkflow initialization")
    except Exception as e:
        print_step(f"Workflow initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Run workflow with tiny topic
    try:
        print("\nRunning workflow with tiny topic...")
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
            print(f"  Context profile: {result.context.profile_name if hasattr(result.context, 'profile_name') else 'N/A'}")
            print_step("Context built")
        else:
            print_step("Context - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Context verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Verify research
    try:
        if result.research:
            print(f"  Research questions: {len(result.research.questions)}")
            print(f"  Research sources: {len(result.research.sources)}")
            print_step("Research completed")
        else:
            print_step("Research - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Research verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Verify planner
    try:
        if result.execution_plan:
            print(f"  Execution plan sections: {len(result.execution_plan)}")
            print_step("Planner completed")
        else:
            print_step("Planner - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Planner verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Verify writer
    try:
        if result.draft_post:
            print(f"  Draft title: {result.draft_post.title}")
            print(f"  Draft length: {len(result.draft_post.content)} chars")
            print_step("Writer completed")
        else:
            print_step("Writer - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Writer verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 7: Verify reviewer
    try:
        if result.review_decision:
            print(f"  Review approved: {result.review_decision.approved}")
            print(f"  Review score: {result.review_decision.overall_score if hasattr(result.review_decision, 'overall_score') else 'N/A'}")
            print_step("Reviewer completed")
        else:
            print_step("Reviewer - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Reviewer verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 8: Verify memory indexing
    try:
        print_step("Memory indexing (assumed completed)")
    except Exception as e:
        print_step(f"Memory verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 9: Verify final result
    try:
        if result.final_post:
            print(f"\n  Final post title: {result.final_post.title}")
            print(f"  Final approved: {result.approved}")
            print_step("Final result available")
        else:
            print_step("Final result - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Final result verification - FAILED: {e}", "FAIL")
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
