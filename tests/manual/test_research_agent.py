"""Manual test for research agent."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from services.research import ResearchService


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
    print_header("Research Agent")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize research service
    try:
        research = ResearchService()
        print_step("ResearchService initialization")
    except Exception as e:
        print_step(f"ResearchService initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Run research on tiny topic
    try:
        print("\nRunning research on tiny topic...")
        topic = "Python"
        result = research.research(topic)
        print_step(f"Research completed for topic: {topic}")
    except Exception as e:
        print_step(f"Research execution - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 3: Verify research package
    try:
        print(f"  Questions generated: {len(result.questions)}")
        print(f"  Raw results: {len(result.raw_results)}")
        print(f"  Sources: {len(result.sources)}")
        print_step("Research package structure valid")
    except Exception as e:
        print_step(f"Research package verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Print sample questions
    try:
        if result.questions:
            print(f"\n  Sample questions:")
            for q in result.questions[:3]:
                print(f"    - {q}")
            print_step("Research questions displayed")
    except Exception as e:
        print_step(f"Display questions - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Print summary
    try:
        print(f"\n  Summary: {result.summary[:200]}...")
        print_step("Research summary available")
    except Exception as e:
        print_step(f"Display summary - FAILED: {e}", "FAIL")
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
