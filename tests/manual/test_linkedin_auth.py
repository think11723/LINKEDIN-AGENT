"""Manual test for LinkedIn OAuth configuration."""

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


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value for display."""
    if not value or len(value) <= visible_chars:
        return "***"
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


def main():
    print_header("LinkedIn OAuth Configuration")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Check client ID
    try:
        client_id = os.getenv("LINKEDIN_CLIENT_ID")
        if client_id:
            print_step(f"LINKEDIN_CLIENT_ID: {mask_secret(client_id)}")
        else:
            print_step("LINKEDIN_CLIENT_ID - MISSING", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Check client ID - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 2: Check client secret
    try:
        client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
        if client_secret:
            print_step(f"LINKEDIN_CLIENT_SECRET: {mask_secret(client_secret)}")
        else:
            print_step("LINKEDIN_CLIENT_SECRET - MISSING", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Check client secret - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Check redirect URI
    try:
        redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI")
        if redirect_uri:
            print_step(f"LINKEDIN_REDIRECT_URI: {redirect_uri}")
        else:
            print_step("LINKEDIN_REDIRECT_URI - MISSING", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Check redirect URI - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Verify redirect URI format
    try:
        if redirect_uri:
            if redirect_uri.startswith("http://") or redirect_uri.startswith("https://"):
                print_step("Redirect URI format valid")
            else:
                print_step("Redirect URI format - INVALID (must start with http:// or https://)", "FAIL")
                all_passed = False
    except Exception as e:
        print_step(f"Verify redirect URI format - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Check for access token (optional)
    try:
        access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        if access_token:
            print_step(f"LINKEDIN_ACCESS_TOKEN: {mask_secret(access_token)} (optional)")
        else:
            print_step("LINKEDIN_ACCESS_TOKEN: Not set (OK, will use OAuth flow)")
    except Exception as e:
        print_step(f"Check access token - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Note about OAuth flow
    try:
        print("\n  Note: This test only validates configuration.")
        print("  Actual OAuth flow requires browser interaction.")
        print_step("OAuth configuration validated")
    except Exception as e:
        print_step(f"OAuth validation - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("Summary: PASS - Configuration valid")
    else:
        print("Summary: FAIL - Missing or invalid configuration")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
