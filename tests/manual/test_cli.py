"""Manual test for CLI (smoke test)."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv


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
    print_header("CLI (Smoke Test)")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Import app module
    try:
        from app import main
        print_step("CLI module import")
    except Exception as e:
        print_step(f"CLI module import - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Verify CLI functions exist
    try:
        from app import display_menu, validate_image_path
        print_step("CLI functions available")
    except Exception as e:
        print_step(f"CLI functions check - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Test validate_image_path
    try:
        is_valid, error = validate_image_path("")
        print_step(f"validate_image_path function works (empty path: {is_valid})")
    except Exception as e:
        print_step(f"validate_image_path test - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Note about interactive CLI
    try:
        print("\n  Note: CLI is interactive and requires user input.")
        print("  This test only verifies module loading and function availability.")
        print("  Full CLI test requires manual interaction.")
        print_step("CLI smoke test completed")
    except Exception as e:
        print_step(f"CLI smoke test - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("Summary: PASS - CLI module loads correctly")
    else:
        print("Summary: FAIL - CLI module has issues")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
