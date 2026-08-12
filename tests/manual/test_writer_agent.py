"""Manual test for writer agent."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from agents.writer import WriterAgent
from models.workflow_models import WorkflowState


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
    print_header("Writer Agent")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize writer agent
    try:
        writer = WriterAgent()
        print_step("WriterAgent initialization")
    except Exception as e:
        print_step(f"WriterAgent initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Create fake outline
    try:
        fake_outline = [
            "Introduction to Python",
            "Key features of Python",
            "Why learn Python in 2026",
            "Getting started with Python"
        ]
        print_step("Fake outline created")
    except Exception as e:
        print_step(f"Create fake outline - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Run writer
    try:
        print("\nRunning writer...")
        state = WorkflowState(
            topic="Python programming",
            user_request="Write a post about Python"
        )
        result = writer.write(state, fake_outline, research_summary="Python is a versatile language.")
        print_step("Writer execution completed")
    except Exception as e:
        print_step(f"Writer execution - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 4: Verify post generated
    try:
        if result.draft_post:
            print(f"  Post title: {result.draft_post.title}")
            print(f"  Post length: {len(result.draft_post.content)} chars")
            print_step("Post generated successfully")
        else:
            print_step("Post generation - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Post verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Print content preview
    try:
        if result.draft_post and result.draft_post.content:
            preview = result.draft_post.content[:500]
            print(f"\n  Content preview:")
            print(f"  {preview}...")
            print_step("Content preview displayed")
    except Exception as e:
        print_step(f"Display content - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Verify hashtags
    try:
        if result.draft_post and result.draft_post.hashtags:
            print(f"\n  Hashtags: {' '.join(result.draft_post.hashtags)}")
            print_step("Hashtags generated")
    except Exception as e:
        print_step(f"Hashtags verification - FAILED: {e}", "FAIL")
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
