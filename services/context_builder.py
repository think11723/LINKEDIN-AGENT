"""Context Builder for LinkedIn Content Agent.

This module builds a unified context object containing all user-specific
information needed by AI agents.
"""

from typing import Optional
from models.context_models import Context
from models.profile_models import Profile
from config.config import config
from utils.profile_manager import load_profile, get_profile_summary, profile_exists
from utils.style_manager import load_style_prompt
from utils.logger import logger


class ContextBuilder:
    """Builds unified context for AI agents.
    
    This class collects profile data, writing preferences, configuration,
    and other user-specific information into a single Context object.
    """
    
    def build(self, writing_style: Optional[str] = None, topic: Optional[str] = None) -> Context:
        """Build the unified context object.
        
        Args:
            writing_style: Optional writing style to use. If not provided,
                          will use default or detect from profile.
            topic: Optional topic for memory retrieval.
            
        Returns:
            Context object with all user-specific information.
        """
        logger.info("Building context")
        
        # Load profile
        profile = load_profile()
        profile_summary = None
        if profile:
            profile_summary = get_profile_summary(profile)
            logger.info("Profile loaded successfully")
        else:
            logger.info("No profile found, using defaults")
        
        # Extract profile information
        target_audience = None
        niche = None
        expertise = None
        career_goal = None
        current_learning = None
        achievements = None
        technical_skills = None
        soft_skills = None
        preferred_tone = None
        emoji_usage = None
        
        if profile:
            target_audience = profile.personal_branding.target_audience
            niche = profile.personal_branding.niche
            expertise = profile.personal_branding.expertise
            career_goal = profile.professional_summary.career_goal
            current_learning = profile.professional_summary.current_learning
            achievements = profile.achievements.milestones if profile.achievements else None
            technical_skills = profile.skills.technical_skills
            soft_skills = profile.skills.soft_skills
            preferred_tone = profile.writing_preferences.preferred_tone
            emoji_usage = profile.writing_preferences.emoji_usage
        
        # Determine writing style
        if not writing_style:
            writing_style = "professional"
        
        # Load style prompt
        style_prompt = load_style_prompt(writing_style)
        
        # Retrieve memory context if topic is provided
        memory_context = None
        if topic:
            try:
                from memory.service import MemoryService
                memory_service = MemoryService()
                memory_context = memory_service.get_memory_context_string(topic, k=3)
                logger.info("Memory context retrieved successfully")
            except Exception as e:
                logger.warning(f"Failed to retrieve memory context: {e}")
        
        # Build context
        context = Context(
            profile=profile,
            profile_summary=profile_summary,
            writing_style=writing_style,
            preferred_tone=preferred_tone,
            emoji_usage=emoji_usage,
            target_audience=target_audience,
            niche=niche,
            expertise=expertise,
            career_goal=career_goal,
            current_learning=current_learning,
            achievements=achievements,
            technical_skills=technical_skills,
            soft_skills=soft_skills,
            llm_model_name=config.model_name,
            temperature=0.7,
            metadata={
                "style_prompt": style_prompt,
                "has_profile": profile is not None,
                "memory_context": memory_context
            }
        )
        
        logger.info(f"Context built successfully. Has profile: {context.has_profile()}, Has memory: {memory_context is not None}")
        return context
