"""Research models for LinkedIn Content Agent.

This module defines the data structures for research packages.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class ResearchPackage(BaseModel):
    """Structured research package containing questions, results, and summary."""
    
    topic: str = Field(description="Research topic")
    questions: List[str] = Field(description="Generated research questions")
    raw_results: List[Dict[str, str]] = Field(default_factory=list, description="Raw search results")
    summary: Optional[str] = Field(default=None, description="Research summary")
    sources: List[str] = Field(default_factory=list, description="Source URLs")
    
    def has_results(self) -> bool:
        """Check if research has results.
        
        Returns:
            True if results exist, False otherwise.
        """
        return len(self.raw_results) > 0
