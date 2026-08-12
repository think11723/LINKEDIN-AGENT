"""Manual test for LLM provider factory."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from services.llm import LLMFactory
from services.llm.config import LLMConfig


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
    print_header("Provider Factory")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Test LLMConfig initialization
    try:
        config = LLMConfig()
        print_step("LLMConfig initialization")
    except Exception as e:
        print_step(f"LLMConfig initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Check default provider
    try:
        default_provider = config.DEFAULT_PROVIDER
        print_step(f"Default provider: {default_provider}")
    except Exception as e:
        print_step(f"Check default provider - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Test provider selection for each agent
    print("\nProvider Selection:")
    agents = ["writer", "reviewer", "planner", "research"]
    
    for agent in agents:
        try:
            model_name = config.get_model(agent)
            print_step(f"{agent} -> {config.DEFAULT_PROVIDER} ({model_name})")
        except Exception as e:
            print_step(f"{agent} provider selection - FAILED: {e}", "FAIL")
            all_passed = False
    
    # Step 4: Test LLMFactory.get() for writer
    try:
        provider = LLMFactory.get("writer")
        print_step(f"LLMFactory.get('writer') -> {provider.__class__.__name__}")
        print(f"  Model: {provider.model}")
        print(f"  Timeout: {provider.timeout}s")
        print(f"  Max retries: {provider.max_retries}")
    except Exception as e:
        print_step(f"LLMFactory.get('writer') - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Test provider caching
    try:
        provider1 = LLMFactory.get("writer")
        provider2 = LLMFactory.get("writer")
        if provider1 is provider2:
            print_step("Provider caching works (same instance)")
        else:
            print_step("Provider caching - FAILED (different instances)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Provider caching test - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Test provider override
    try:
        provider = LLMFactory.get("writer", provider="huggingface")
        print_step(f"Provider override: {provider.__class__.__name__}")
    except Exception as e:
        print_step(f"Provider override - FAILED: {e}", "FAIL")
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
