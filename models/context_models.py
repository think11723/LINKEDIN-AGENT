"""Context models for LinkedIn Content Agent.

This module defines the unified context object that contains all user-specific
information needed by AI agents.
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel, Field
from models.profile_models import Profile

if TYPE_CHECKING:
    from config.config import Config


class Context(BaseModel):
    """Unified context object containing all user-specific information.
    
    This is the single source of truth for user context, providing
    profile, preferences, and configuration to all agents.
    """
    
    # Profile information
    profile: Optional[Profile] = Field(default=None, description="User profile data")
    profile_summary: Optional[str] = Field(default=None, description="Concise profile summary for AI")
    
    # Writing preferences
    writing_style: str = Field(default="professional", description="Default writing style")
    preferred_tone: Optional[str] = Field(default=None, description="Preferred tone for posts")
    emoji_usage: Optional[str] = Field(default=None, description="Emoji usage preference")
    
    # Target audience and branding
    target_audience: Optional[str] = Field(default=None, description="Target audience for posts")
    niche: Optional[str] = Field(default=None, description="Content niche")
    expertise: Optional[str] = Field(default=None, description="Areas of expertise")
    
    # Goals and achievements
    career_goal: Optional[str] = Field(default=None, description="Long-term career goal")
    current_learning: Optional[str] = Field(default=None, description="Currently learning topics")
    achievements: Optional[list] = Field(default=None, description="Key achievements and milestones")
    
    # Skills
    technical_skills: Optional[list] = Field(default=None, description="Technical skills")
    soft_skills: Optional[list] = Field(default=None, description="Soft skills")
    
    # Configuration
    llm_model_name: Optional[str] = Field(default=None, description="LLM model name")
    temperature: Optional[float] = Field(default=None, description="LLM temperature")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    def has_profile(self) -> bool:
        """Check if profile data is available.
        
        Returns:
            True if profile data exists, False otherwise.
        """
        return self.profile is not None
    
    def get_style_prompt(self) -> Optional[str]:
        """Get the style-specific prompt for the configured writing style.
        
        Returns:
            Style prompt string if available, None otherwise.
        """
        # This will be loaded by the ContextBuilder
        return self.metadata.get("style_prompt")
