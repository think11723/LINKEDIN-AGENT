"""Tests for memory indexing and retrieval."""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from memory.service import MemoryService
from memory.models import PostMemory, MemorySummary


class TestMemoryService:
    """Test cases for MemoryService."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def memory_service(self, temp_dir):
        """Create a MemoryService instance with temp storage."""
        service = MemoryService()
        # Override storage paths to use temp directory
        service.job_store.storage_path = Path(temp_dir) / "jobs.json"
        service.job_store.storage_path.parent.mkdir(parents=True, exist_ok=True)
        return service
    
    def test_index_post(self, memory_service):
        """Test indexing a post."""
        job_id = memory_service.index_post(
            topic="AI Agents",
            title="AI Agents in 2026",
            content="AI agents are changing software development...",
            hashtags=["#AI", "#SoftwareEngineering"],
            writing_style="professional"
        )
        
        assert job_id is not None
        assert isinstance(job_id, str)
        
        # Verify post was stored
        job = memory_service.job_store.get(job_id)
        assert job is not None
        assert job.title == "AI Agents in 2026"
    
    def test_retrieve_memory(self, memory_service):
        """Test retrieving memory for a topic."""
        # Index a post
        memory_service.index_post(
            topic="AI Agents",
            title="AI Agents in 2026",
            content="AI agents are changing software development...",
            hashtags=["#AI", "#SoftwareEngineering"],
            writing_style="professional"
        )
        
        # Retrieve memory
        summary = memory_service.retrieve_memory("AI Agents")
        
        assert summary is not None
        assert isinstance(summary, MemorySummary)
    
    def test_get_memory_context_string(self, memory_service):
        """Test getting memory context string."""
        # Index a post
        memory_service.index_post(
            topic="AI Agents",
            title="AI Agents in 2026",
            content="AI agents are changing software development...",
            hashtags=["#AI", "#SoftwareEngineering"],
            writing_style="professional"
        )
        
        # Get context string
        context = memory_service.get_memory_context_string("AI Agents", k=1)
        
        assert context is not None
        assert isinstance(context, str)
        assert len(context) > 0
    
    def test_clear_memory(self, memory_service):
        """Test clearing memory."""
        # Index a post
        memory_service.index_post(
            topic="AI Agents",
            title="AI Agents in 2026",
            content="AI agents are changing software development...",
            hashtags=["#AI", "#SoftwareEngineering"],
            writing_style="professional"
        )
        
        # Clear memory
        memory_service.clear_memory()
        
        # Verify memory is cleared
        stats = memory_service.get_memory_stats()
        assert stats["total_jobs"] == 0
    
    def test_get_memory_stats(self, memory_service):
        """Test getting memory statistics."""
        # Index multiple posts
        memory_service.index_post(
            topic="AI Agents",
            title="AI Agents in 2026",
            content="AI agents are changing software development...",
            hashtags=["#AI"],
            writing_style="professional"
        )
        
        memory_service.index_post(
            topic="Machine Learning",
            title="ML Trends",
            content="Machine learning is evolving...",
            hashtags=["#ML"],
            writing_style="professional"
        )
        
        # Get stats
        stats = memory_service.get_memory_stats()
        
        assert stats["total_jobs"] == 2
        assert "storage_path" in stats
