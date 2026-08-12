"""Manual test for publishing payload (mocked)."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
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
    print_header("Publish Payload (Mocked)")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Create test post
    try:
        test_post = LinkedInPost(
            title="Test Post for Publishing",
            content="This is a test post to verify the publishing payload structure. It should be properly formatted for LinkedIn's UGC API.",
            hashtags=["#test", "#publish"]
        )
        print_step("Test post created")
    except Exception as e:
        print_step(f"Create test post - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Construct payload
    try:
        payload = {
            "author": "urn:li:person:PLACEHOLDER",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": test_post.content
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        print_step("Publishing payload constructed")
    except Exception as e:
        print_step(f"Construct payload - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Verify payload structure
    try:
        required_keys = ["author", "lifecycleState", "specificContent", "visibility"]
        for key in required_keys:
            if key not in payload:
                print_step(f"Payload missing key: {key}", "FAIL")
                all_passed = False
        if all_passed:
            print_step("Payload structure valid")
    except Exception as e:
        print_step(f"Verify payload structure - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Print payload preview
    try:
        print(f"\n  Payload preview:")
        print(f"  Author: {payload['author']}")
        print(f"  Lifecycle: {payload['lifecycleState']}")
        print(f"  Content length: {len(payload['specificContent']['com.linkedin.ugc.ShareContent']['shareCommentary']['text'])}")
        print_step("Payload preview displayed")
    except Exception as e:
        print_step(f"Display payload - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Verify content
    try:
        content = payload['specificContent']['com.linkedin.ugc.ShareContent']['shareCommentary']['text']
        if content and len(content) > 0:
            print_step("Content present in payload")
        else:
            print_step("Content - FAILED (empty)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Verify content - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Note about API call
    try:
        print("\n  Note: This test only validates payload structure.")
        print("  Actual LinkedIn API call is NOT made (mocked).")
        print_step("Mock validation completed")
    except Exception as e:
        print_step(f"Mock validation - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("Summary: PASS - Payload structure valid")
    else:
        print("Summary: FAIL - Payload structure invalid")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
