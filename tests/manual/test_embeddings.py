"""Manual test for embedding provider."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from services.llm.embeddings import EmbeddingFactory
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
    print_header("Embedding Provider")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize embedding provider
    try:
        provider = EmbeddingFactory.get(
            provider="huggingface",
            api_key=LLMConfig.HF_API_KEY,
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        print_step(f"Embedding provider: {provider.__class__.__name__}")
        print(f"  Model: {provider.model}")
    except Exception as e:
        print_step(f"Embedding provider initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Generate embedding
    try:
        print("\nGenerating embedding for test text...")
        test_text = "This is a test sentence for embedding generation."
        response = provider.generate_embedding(test_text)
        print_step("Embedding generated successfully")
    except Exception as e:
        print_step(f"Embedding generation - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 3: Check embedding length
    try:
        embedding_length = len(response.embedding)
        print(f"  Embedding length: {embedding_length}")
        print_step(f"Embedding length: {embedding_length}")
    except Exception as e:
        print_step(f"Embedding length check - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 4: Print vector preview
    try:
        preview = response.embedding[:5]
        print(f"  Vector preview: {preview}")
        print_step("Vector preview displayed")
    except Exception as e:
        print_step(f"Vector preview - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Check latency
    try:
        print(f"  Latency: {response.latency:.2f}s")
        print_step(f"Latency: {response.latency:.2f}s")
    except Exception as e:
        print_step(f"Latency check - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Check metadata
    try:
        print(f"  Provider: {response.metadata.get('provider')}")
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
