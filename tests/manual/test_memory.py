"""Manual test for memory service."""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
from memory.service import MemoryService


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
    print_header("Memory Service")
    
    all_passed = True
    
    # Load environment
    load_dotenv()
    
    # Step 1: Initialize memory service
    try:
        memory = MemoryService()
        print_step("MemoryService initialization")
    except Exception as e:
        print_step(f"MemoryService initialization - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 2: Clear existing memory
    try:
        memory.clear_memory()
        print_step("Memory cleared")
    except Exception as e:
        print_step(f"Clear memory - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 3: Create test post data
    try:
        test_topic = "Test Topic"
        test_title = "Test Post for Memory"
        test_content = "This is a test post to verify memory storage and retrieval functionality. The post should be professional and engaging for LinkedIn."
        test_hashtags = ["#test", "#memory"]
        print_step("Test post data created")
    except Exception as e:
        print_step(f"Create test post - FAILED: {e}", "FAIL")
        all_passed = False
        return 1
    
    # Step 4: Store post in memory
    try:
        post_id = memory.index_post(
            topic=test_topic,
            title=test_title,
            content=test_content,
            hashtags=test_hashtags
        )
        print_step("Post indexed in memory")
    except Exception as e:
        print_step(f"Index post - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 5: Retrieve from memory
    try:
        summary = memory.retrieve_memory("test post memory", k=5)
        print_step(f"Memory retrieved for topic")
        print(f"  Summary available: {summary is not None}")
    except Exception as e:
        print_step(f"Retrieve from memory - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 6: Verify similarity search
    try:
        if summary:
            print_step("Similarity search working")
        else:
            print_step("Similarity search - FAILED (no results)", "FAIL")
            all_passed = False
    except Exception as e:
        print_step(f"Similarity search verification - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 7: Get statistics
    try:
        stats = memory.get_memory_stats()
        print(f"  Total posts: {stats.get('total_posts', 0)}")
        print(f"  Total embeddings: {stats.get('total_embeddings', 0)}")
        print_step("Memory statistics retrieved")
    except Exception as e:
        print_step(f"Get statistics - FAILED: {e}", "FAIL")
        all_passed = False
    
    # Step 8: Clear memory again
    try:
        memory.clear_memory()
        print_step("Memory cleared (cleanup)")
    except Exception as e:
        print_step(f"Clear memory (cleanup) - FAILED: {e}", "FAIL")
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
