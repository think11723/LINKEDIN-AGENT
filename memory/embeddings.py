"""Embedding utilities for LinkedIn Content Memory.

This module provides simple embedding generation for LinkedIn posts.
"""

from typing import List
from services.llm import generate_text
from utils.logger import logger


def generate_embedding(text: str) -> List[float]:
    """Generate a simple embedding for text.
    
    This is a lightweight implementation that uses the LLM to generate
    a semantic representation. For production, consider using dedicated
    embedding models like OpenAI's text-embedding-3-small.
    
    Args:
        text: Text to embed.
        
    Returns:
        List of float values representing the embedding.
    """
    try:
        # Use LLM to generate a semantic representation
        prompt = f"""Generate a 32-dimensional vector representation of the following text.
Return only 32 comma-separated float values between -1 and 1.

Text: {text}

Vector:"""
        
        response = generate_text(
            system_prompt="You are a text embedding generator. Output only numeric vectors.",
            user_prompt=prompt,
            temperature=0.1
        )
        
        # Parse the response into a list of floats
        values = [float(x.strip()) for x in response.split(',') if x.strip()]
        
        # Ensure we have exactly 32 values
        if len(values) < 32:
            values.extend([0.0] * (32 - len(values)))
        elif len(values) > 32:
            values = values[:32]
        
        return values
        
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        # Return zero vector as fallback
        return [0.0] * 32
