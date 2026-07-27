"""Retriever for LinkedIn Content Memory.

This module retrieves relevant previous posts based on semantic similarity.
"""

from typing import List, Optional
from memory.models import PostMemory, MemorySummary
from memory.vector_store import VectorStore
from memory.embeddings import generate_embedding
from utils.logger import logger


class Retriever:
    """Retrieves relevant previous posts from memory."""
    
    def __init__(self, vector_store: VectorStore, post_store_path: str = "memory/posts.json"):
        """Initialize the retriever.
        
        Args:
            vector_store: Vector store for similarity search.
            post_store_path: Path to store post metadata on disk.
        """
        self.vector_store = vector_store
        self.post_store_path = post_store_path
        self.posts: dict = {}  # post_id -> PostMemory
        self._load_posts()
    
    def _load_posts(self) -> None:
        """Load post metadata from disk."""
        try:
            import json
            from pathlib import Path
            path = Path(self.post_store_path)
            if path.exists():
                with open(path, 'r') as f:
                    data = json.load(f)
                    for post_id, post_data in data.items():
                        self.posts[post_id] = PostMemory(**post_data)
                logger.info(f"Loaded {len(self.posts)} posts from disk")
        except Exception as e:
            logger.error(f"Failed to load posts: {e}")
            self.posts = {}
    
    def _save_posts(self) -> None:
        """Save post metadata to disk."""
        try:
            import json
            from pathlib import Path
            path = Path(self.post_store_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {post_id: post.dict() for post_id, post in self.posts.items()}
            with open(path, 'w') as f:
                json.dump(data, f)
            logger.info(f"Saved {len(self.posts)} posts to disk")
        except Exception as e:
            logger.error(f"Failed to save posts: {e}")
    
    def retrieve(self, topic: str, k: int = 5) -> List[PostMemory]:
        """Retrieve relevant posts for a topic.
        
        Args:
            topic: Current topic to find similar posts for.
            k: Number of posts to retrieve.
            
        Returns:
            List of relevant PostMemory objects.
        """
        if not self.posts:
            logger.info("No posts in memory to retrieve")
            return []
        
        # Generate embedding for the topic
        query_embedding = generate_embedding(topic)
        
        # Search for similar posts
        similar_post_ids = self.vector_store.search(query_embedding, k=k)
        
        # Retrieve post metadata
        relevant_posts = []
        for post_id, similarity in similar_post_ids:
            if post_id in self.posts:
                relevant_posts.append(self.posts[post_id])
        
        logger.info(f"Retrieved {len(relevant_posts)} relevant posts for topic: {topic}")
        return relevant_posts
    
    def summarize_for_context(self, topic: str, k: int = 5) -> MemorySummary:
        """Summarize retrieved posts for Writer Agent context.
        
        Args:
            topic: Current topic.
            k: Number of posts to consider.
            
        Returns:
            MemorySummary with condensed context.
        """
        relevant_posts = self.retrieve(topic, k=k)
        
        if not relevant_posts:
            return MemorySummary()
        
        # Extract information for summary
        relevant_topics = list(set([post.topic for post in relevant_posts]))
        used_hashtags = []
        writing_patterns = []
        cta_suggestions = []
        content_themes = []
        
        for post in relevant_posts:
            # Collect hashtags
            used_hashtags.extend(post.hashtags)
            
            # Extract writing patterns (first sentence)
            first_sentence = post.content.split('.')[0] if post.content else ""
            if first_sentence:
                writing_patterns.append(first_sentence[:50] + "...")
            
            # Extract CTA pattern
            if post.cta_pattern:
                cta_suggestions.append(post.cta_pattern)
            
            # Extract content themes (keywords from title)
            title_words = post.title.lower().split()
            content_themes.extend([w for w in title_words if len(w) > 4])
        
        # Deduplicate and limit
        used_hashtags = list(set(used_hashtags))[:10]
        writing_patterns = list(set(writing_patterns))[:5]
        cta_suggestions = list(set(cta_suggestions))[:3]
        content_themes = list(set(content_themes))[:5]
        
        summary = MemorySummary(
            relevant_topics=relevant_topics[:3],
            used_hashtags=used_hashtags,
            writing_patterns=writing_patterns,
            cta_suggestions=cta_suggestions,
            content_themes=content_themes
        )
        
        logger.info(f"Generated memory summary with {len(relevant_topics)} topics, {len(used_hashtags)} hashtags")
        return summary
