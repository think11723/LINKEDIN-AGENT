"""Embedding utilities for LinkedIn Content Memory.

This module provides embedding generation using dedicated embedding models.
"""

from typing import List
from services.llm.embeddings import EmbeddingFactory, EmbeddingResponse
from utils.logger import logger
from services.llm.config import LLMConfig


def generate_embedding(text: str) -> List[float]:
    """Generate an embedding for text using dedicated embedding model.
    
    This uses Hugging Face's sentence-transformers model for proper embeddings.
    For production, consider using dedicated embedding services like OpenAI's text-embedding-3-small.
    
    Args:
        text: Text to embed.
        
    Returns:
        List of float values representing the embedding.
    """
    try:
        # Get embedding provider
        provider = EmbeddingFactory.get(
            provider="huggingface",
            api_key=LLMConfig.HF_API_KEY,
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Generate embedding
        response = provider.generate_embedding(text)
        
        # Normalize to 32 dimensions for consistency with existing implementation
        embedding = response.embedding
        
        # Pad or truncate to 32 dimensions
        if len(embedding) < 32:
            embedding.extend([0.0] * (32 - len(embedding)))
        elif len(embedding) > 32:
            embedding = embedding[:32]
        
        return embedding
        
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        # Return zero vector as fallback
        return [0.0] * 32
