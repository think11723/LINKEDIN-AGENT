"""Indexer for LinkedIn Content Memory.

This module indexes new posts into the memory system.
"""

from typing import Optional
from datetime import datetime
import uuid
from memory.models import PostMemory
from memory.vector_store import VectorStore
from memory.embeddings import generate_embedding
from utils.logger import logger


class Indexer:
    """Indexes new LinkedIn posts into memory."""
    
    def __init__(self, vector_store: VectorStore):
        """Initialize the indexer.
        
        Args:
            vector_store: Vector store for storing embeddings.
        """
        self.vector_store = vector_store
    
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
        # Generate unique post ID
        post_id = str(uuid.uuid4())
        
        # Generate embedding for the post
        text_to_embed = f"{topic} {title} {content}"
        embedding = generate_embedding(text_to_embed)
        
        # Create post memory entry
        post_memory = PostMemory(
            post_id=post_id,
            topic=topic,
            title=title,
            content=content,
            hashtags=hashtags,
            writing_style=writing_style,
            cta_pattern=cta_pattern,
            created_at=datetime.utcnow(),
            embedding=embedding
        )
        
        # Store embedding in vector store
        self.vector_store.add(post_id, embedding)
        
        # Store post metadata (handled by retriever's save mechanism)
        # We'll use the retriever to save the full post data
        
        logger.info(f"Indexed post {post_id} for topic: {topic}")
        return post_id
    
    def extract_cta_pattern(self, content: str) -> Optional[str]:
        """Extract the call-to-action pattern from content.
        
        Args:
            content: Post content.
            
        Returns:
            CTA pattern or None if not found.
        """
        # Look for common CTA patterns
        cta_indicators = [
            "what do you think",
            "let me know",
            "share your thoughts",
            "how about you",
            "what's your take",
            "comment below",
            "drop a comment"
        ]
        
        content_lower = content.lower()
        for indicator in cta_indicators:
            if indicator in content_lower:
                # Extract the sentence containing the CTA
                sentences = content.split('.')
                for sentence in sentences:
                    if indicator in sentence.lower():
                        return sentence.strip()
        
        return None
