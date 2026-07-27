"""Vector store for LinkedIn Content Memory.

This module provides a simple in-memory vector store for storing
and retrieving embeddings of LinkedIn posts.
"""

from typing import List, Optional, Tuple
import json
from pathlib import Path
import numpy as np
from memory.models import PostMemory
from utils.logger import logger


class VectorStore:
    """Simple in-memory vector store for LinkedIn post embeddings."""
    
    def __init__(self, storage_path: str = "memory/vector_store.json"):
        """Initialize the vector store.
        
        Args:
            storage_path: Path to store vector data on disk.
        """
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.embeddings: List[List[float]] = []
        self.post_ids: List[str] = []
        self._load_from_disk()
    
    def _load_from_disk(self) -> None:
        """Load vector store data from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self.embeddings = data.get('embeddings', [])
                    self.post_ids = data.get('post_ids', [])
                logger.info(f"Loaded {len(self.embeddings)} embeddings from disk")
            except Exception as e:
                logger.error(f"Failed to load vector store: {e}")
                self.embeddings = []
                self.post_ids = []
    
    def _save_to_disk(self) -> None:
        """Save vector store data to disk."""
        try:
            data = {
                'embeddings': self.embeddings,
                'post_ids': self.post_ids
            }
            with open(self.storage_path, 'w') as f:
                json.dump(data, f)
            logger.info(f"Saved {len(self.embeddings)} embeddings to disk")
        except Exception as e:
            logger.error(f"Failed to save vector store: {e}")
    
    def add(self, post_id: str, embedding: List[float]) -> None:
        """Add an embedding to the store.
        
        Args:
            post_id: Unique identifier for the post.
            embedding: Vector embedding.
        """
        self.embeddings.append(embedding)
        self.post_ids.append(post_id)
        self._save_to_disk()
    
    def search(self, query_embedding: List[float], k: int = 5) -> List[Tuple[str, float]]:
        """Search for similar embeddings.
        
        Args:
            query_embedding: Query vector embedding.
            k: Number of results to return.
            
        Returns:
            List of (post_id, similarity_score) tuples.
        """
        if not self.embeddings:
            return []
        
        # Convert to numpy arrays for efficient computation
        query_vec = np.array(query_embedding)
        embeddings_matrix = np.array(self.embeddings)
        
        # Compute cosine similarity
        similarities = []
        for i, embedding in enumerate(self.embeddings):
            vec = np.array(embedding)
            # Cosine similarity
            similarity = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec))
            similarities.append((self.post_ids[i], float(similarity)))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k results
        return similarities[:k]
    
    def delete(self, post_id: str) -> bool:
        """Delete an embedding from the store.
        
        Args:
            post_id: Post identifier to delete.
            
        Returns:
            True if deleted, False if not found.
        """
        if post_id not in self.post_ids:
            return False
        
        index = self.post_ids.index(post_id)
        self.post_ids.pop(index)
        self.embeddings.pop(index)
        self._save_to_disk()
        return True
    
    def clear(self) -> None:
        """Clear all embeddings from the store."""
        self.embeddings = []
        self.post_ids = []
        self._save_to_disk()
        logger.info("Vector store cleared")
