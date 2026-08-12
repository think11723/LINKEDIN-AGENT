"""Manual test for environment configuration."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from config.config import config


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Mask a secret value for display."""
    if not value or len(value) <= visible_chars:
        return "***"
    return value[:visible_chars] + "*" * (len(value) - visible_chars)


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
    print_header("Environment Configuration")
    
    all_passed = True
    
    # Step 1: Load .env
    try:
        load_dotenv()
        print_step("Load .env file")
    except Exception as e:
        print_step(f"Load .env file - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 2: Check DEFAULT_PROVIDER
    try:
        default_provider = os.getenv("DEFAULT_PROVIDER")
        if default_provider:
            print_step(f"DEFAULT_PROVIDER exists: {default_provider}")
        else:
            print_step("DEFAULT_PROVIDER missing - FAILED", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Check DEFAULT_PROVIDER - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Check API keys
    print("\nAPI Keys:")
    api_keys = {
        "HF_API_KEY": os.getenv("HF_API_KEY"),
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    }
    
    for key_name, key_value in api_keys.items():
        if key_value:
            print_step(f"{key_name}: {mask_secret(key_value)}")
        else:
            print_step(f"{key_name}: MISSING (may be OK if using other provider)")
    
    # Step 4: Check LinkedIn credentials
    print("\nLinkedIn Credentials:")
    linkedin_keys = {
        "LINKEDIN_CLIENT_ID": os.getenv("LINKEDIN_CLIENT_ID"),
        "LINKEDIN_CLIENT_SECRET": os.getenv("LINKEDIN_CLIENT_SECRET"),
        "LINKEDIN_REDIRECT_URI": os.getenv("LINKEDIN_REDIRECT_URI"),
    }
    
    for key_name, key_value in linkedin_keys.items():
        if key_value:
            print_step(f"{key_name}: {mask_secret(key_value)}")
        else:
            print_step(f"{key_name}: MISSING")
            all_passed = False
    
    # Step 5: Check LLM timeout
    try:
        timeout = os.getenv("LLM_TIMEOUT", "60")
        print_step(f"LLM_TIMEOUT: {timeout}s")
    except Exception as e:
        print_step(f"Check LLM_TIMEOUT - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Print model mappings
    print("\nModel Mappings:")
    model_vars = [k for k in os.environ.keys() if k.endswith("_MODEL")]
    for var in sorted(model_vars):
        value = os.getenv(var)
        if value:
            print_step(f"{var}: {value}")
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("Summary: PASS")
    else:
        print("Summary: FAIL - Some required configuration missing")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
