"""Manual test for planner agent."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from agents.planner import PlannerAgent
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
    print_header("Planner Agent")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize planner agent
    try:
        planner = PlannerAgent()
        print_step("PlannerAgent initialization")
    except Exception as e:
        print_step(f"PlannerAgent initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Create fake research data
    try:
        fake_research = {
            "topic": "Python programming",
            "questions": ["What is Python?", "Why use Python?"],
            "summary": "Python is a popular programming language known for simplicity and versatility.",
            "sources": ["https://python.org"]
        }
        print_step("Fake research data created")
    except Exception as e:
        print_step(f"Create fake research - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Run planner
    try:
        print("\nRunning planner...")
        result = planner.plan("Write a post about Python programming")
        print_step("Planner execution completed")
    except Exception as e:
        print_step(f"Planner execution - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 4: Verify execution plan
    try:
        print(f"  Topic: {result.topic}")
        print(f"  Intent: {result.intent}")
        print(f"  Requires search: {result.requires_search}")
        print_step("Execution plan generated")
    except Exception as e:
        print_step(f"Execution plan verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Print outline preview
    try:
        print(f"\n  Plan details:")
        print(f"    Tone: {result.tone}")
        print(f"    Writing style: {result.writing_style}")
        print_step("Plan details displayed")
    except Exception as e:
        print_step(f"Display plan - FAILED: {e}", "FAIL")
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
