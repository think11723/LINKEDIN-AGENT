"""Shared data models for LinkedIn Content Agent.

This module contains Pydantic models used across multiple agents and utilities.
"""

from typing import List
from pydantic import BaseModel, Field


class LinkedInPost(BaseModel):
    """Structured LinkedIn post."""
    
    title: str = Field(description="Title of the LinkedIn post")
    content: str = Field(description="Main content of the post (200-350 words)")
    hashtags: List[str] = Field(description="5-10 relevant hashtags")
