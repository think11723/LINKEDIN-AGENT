"""Manual test for reviewer agent."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from agents.reviewer import ReviewerAgent
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
    print_header("Reviewer Agent")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize reviewer agent
    try:
        reviewer = ReviewerAgent()
        print_step("ReviewerAgent initialization")
    except Exception as e:
        print_step(f"ReviewerAgent initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Create test post
    try:
        test_post = LinkedInPost(
            title="Test Post for Review",
            content="This is a test post. It has some content that needs to be reviewed for quality and engagement. The post should be professional and engaging for LinkedIn.",
            hashtags=["#test", "#review"]
        )
        print_step("Test post created")
    except Exception as e:
        print_step(f"Create test post - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Run reviewer
    try:
        print("\nRunning reviewer...")
        result = reviewer.review(test_post)
        print_step("Reviewer execution completed")
    except Exception as e:
        print_step(f"Reviewer execution - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 4: Verify scores
    try:
        if result.scores:
            print(f"  Overall score: {result.scores.overall_score}/10")
            print_step("Review scores generated")
        else:
            print_step("Review scores - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Scores verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Print dimension scores
    try:
        if result.scores:
            print(f"\n  Dimension scores:")
            print(f"    Hook: {result.scores.hook_score}/10")
            print(f"    Structure: {result.scores.structure_score}/10")
            print(f"    Engagement: {result.scores.engagement_score}/10")
            print(f"    Clarity: {result.scores.clarity_score}/10")
            print_step("Dimension scores displayed")
    except Exception as e:
        print_step(f"Display scores - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Check feedback
    try:
        if result.feedback:
            print(f"\n  Feedback: {result.feedback[:200]}...")
            print_step("Feedback generated")
        else:
            print_step("Feedback - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Feedback check - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 7: Check approval decision
    try:
        if result.decision:
            print(f"\n  Approval: {result.decision.approved}")
            print(f"  Reason: {result.decision.reason[:100]}...")
            print_step("Approval decision made")
        else:
            print_step("Approval decision - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Approval check - FAILED: {e}", "FAIL")
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
