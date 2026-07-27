"""Memory Service for LinkedIn Content Agent.

This module orchestrates the memory system for storing and retrieving
LinkedIn post information to improve future content generation.
"""

from typing import Optional
from memory.models import PostMemory, MemorySummary
from memory.vector_store import VectorStore
from memory.retriever import Retriever
from memory.indexer import Indexer
from utils.logger import logger


class MemoryService:
    """Service for managing LinkedIn content memory."""
    
    def __init__(self):
        """Initialize the memory service."""
        self.vector_store = VectorStore()
        self.retriever = Retriever(self.vector_store)
        self.indexer = Indexer(self.vector_store)
        logger.info("Memory service initialized")
    
    def index_post(
        self,
        topic: str,
        title: str,
        content: str,
        hashtags: list,
        writing_style: str = "professional",
        cta_pattern: Optional[str] = None
    ) -> str:
        """Index a new LinkedIn post into memory.
        
        Args:
            topic: Post topic.
            title: Post title.
            content: Post content.
            hashtags: Post hashtags.
            writing_style: Writing style used.
            cta_pattern: Call-to-action pattern used.
            
        Returns:
            Post ID of the indexed post.
        """
        # Extract CTA pattern if not provided
        if cta_pattern is None:
            cta_pattern = self.indexer.extract_cta_pattern(content)
        
        # Index the post
        post_id = self.indexer.index_post(
            topic=topic,
            title=title,
            content=content,
            hashtags=hashtags,
            writing_style=writing_style,
            cta_pattern=cta_pattern
        )
        
        # Store full post metadata in retriever's post store
        post_memory = PostMemory(
            post_id=post_id,
            topic=topic,
            title=title,
            content=content,
            hashtags=hashtags,
            writing_style=writing_style,
            cta_pattern=cta_pattern,
            embedding=None  # Already stored in vector store
        )
        
        # Add to retriever's posts dict and save
        self.retriever.posts[post_id] = post_memory
        self.retriever._save_posts()
        
        logger.info(f"Post indexed successfully: {post_id}")
        return post_id
    
    def retrieve_memory(self, topic: str, k: int = 5) -> MemorySummary:
        """Retrieve relevant memory for a topic.
        
        Args:
            topic: Current topic.
            k: Number of posts to consider.
            
        Returns:
            MemorySummary with condensed context for the Writer Agent.
        """
        summary = self.retriever.summarize_for_context(topic, k=k)
        logger.info(f"Retrieved memory summary for topic: {topic}")
        return summary
    
    def get_memory_context_string(self, topic: str, k: int = 5) -> str:
        """Get memory context as a string for the Writer Agent.
        
        Args:
            topic: Current topic.
            k: Number of posts to consider.
            
        Returns:
            Formatted context string.
        """
        summary = self.retrieve_memory(topic, k=k)
        return summary.to_context_string()
    
    def clear_memory(self) -> None:
        """Clear all memory data."""
        self.vector_store.clear()
        self.retriever.posts = {}
        self.retriever._save_posts()
        logger.info("Memory cleared")
    
    def get_memory_stats(self) -> dict:
        """Get statistics about the memory store.
        
        Returns:
            Dictionary with memory statistics.
        """
        return {
            "total_posts": len(self.retriever.posts),
            "total_embeddings": len(self.vector_store.embeddings),
            "storage_path": str(self.vector_store.storage_path)
        }
