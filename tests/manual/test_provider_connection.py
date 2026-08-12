"""Manual test for provider connection and basic inference."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from services.llm import LLMFactory


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
    print_header("Provider Connection")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Get provider
    try:
        provider = LLMFactory.get("writer")
        print_step(f"Provider: {provider.__class__.__name__}")
        print(f"  Model: {provider.model}")
    except Exception as e:
        print_step(f"Get provider - FAILED: {e}", "FAIL")
        return 1
    
    # Step 2: Send small prompt
    try:
        print("\nSending test prompt...")
        response = provider.generate_text("Reply with exactly the word OK.")
        print_step("HTTP request succeeded")
    except Exception as e:
        print_step(f"HTTP request - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 3: Verify response
    try:
        print(f"  Response: {response.text[:100]}")
        print_step(f"Response received ({len(response.text)} chars)")
    except Exception as e:
        print_step(f"Response verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Check latency
    try:
        print(f"  Latency: {response.latency:.2f}s")
        print_step(f"Latency measured: {response.latency:.2f}s")
    except Exception as e:
        print_step(f"Latency check - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Check token usage if available
    try:
        if response.tokens_used:
            print(f"  Tokens used: {response.tokens_used}")
            print_step(f"Token usage: {response.tokens_used}")
        else:
            print_step("Token usage: Not available (OK)")
    except Exception as e:
        print_step(f"Token usage check - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Check metadata
    try:
        print(f"  Provider: {response.metadata.get('provider')}")
        print(f"  HTTP status: {response.metadata.get('http_status')}")
        print_step("Metadata present")
    except Exception as e:
        print_step(f"Metadata check - FAILED: {e}", "FAIL")
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
