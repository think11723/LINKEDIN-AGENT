"""Memory models for LinkedIn Content Agent.

This module defines data models for storing and retrieving
information about previously generated LinkedIn posts.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class PostMemory(BaseModel):
    """Memory entry for a LinkedIn post."""
    
    post_id: str = Field(description="Unique identifier for the post")
    topic: str = Field(description="Original topic of the post")
    title: str = Field(description="Post title")
    content: str = Field(description="Post content")
    hashtags: List[str] = Field(default_factory=list, description="Post hashtags")
    writing_style: str = Field(default="professional", description="Writing style used")
    cta_pattern: Optional[str] = Field(default=None, description="Call-to-action pattern used")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    embedding: Optional[List[float]] = Field(default=None, description="Vector embedding for retrieval")


class MemorySummary(BaseModel):
    """Summarized memory context for the Writer Agent."""
    
    relevant_topics: List[str] = Field(default_factory=list, description="Previously covered similar topics")
    used_hashtags: List[str] = Field(default_factory=list, description="Hashtags used in similar posts")
    writing_patterns: List[str] = Field(default_factory=list, description="Common writing patterns to avoid repetition")
    cta_suggestions: List[str] = Field(default_factory=list, description="Alternative CTA patterns to consider")
    content_themes: List[str] = Field(default_factory=list, description="Common themes in previous posts")
    
    def to_context_string(self) -> str:
        """Convert summary to context string for the Writer Agent."""
        context_parts = []
        
        if self.relevant_topics:
            context_parts.append(f"Previously covered similar topics: {', '.join(self.relevant_topics)}")
        
        if self.used_hashtags:
            context_parts.append(f"Hashtags used in similar posts: {', '.join(self.used_hashtags)}")
        
        if self.writing_patterns:
            context_parts.append(f"Writing patterns to avoid repeating: {', '.join(self.writing_patterns)}")
        
        if self.cta_suggestions:
            context_parts.append(f"Alternative CTA patterns to consider: {', '.join(self.cta_suggestions)}")
        
        if self.content_themes:
            context_parts.append(f"Common themes in previous posts: {', '.join(self.content_themes)}")
        
        return "\n".join(context_parts) if context_parts else "No relevant memory found."
