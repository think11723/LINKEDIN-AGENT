"""Test provider priority configuration."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from services.llm.config import LLMConfig

print("Testing Provider Priority Configuration")
print("=" * 50)
print(f"Provider Priority: {LLMConfig.get_provider_priority()}")
print(f"Default Provider: {LLMConfig.DEFAULT_PROVIDER}")
print("=" * 50)
