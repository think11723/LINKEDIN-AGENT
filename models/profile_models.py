"""Profile models for LinkedIn Content Agent.

This module defines Pydantic models for user profile data,
enabling type-safe profile management and validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BasicInfo(BaseModel):
    """Basic user information."""
    
    full_name: str = Field(description="User's full name")
    preferred_name: str = Field(description="Preferred name for posts")
    headline: str = Field(description="LinkedIn headline")
    current_role: str = Field(description="Current job role")
    organisation: str = Field(description="Current organisation/company")
    location: str = Field(description="Current location")
    years_of_experience: int = Field(description="Years of professional experience")


class Education(BaseModel):
    """Education information."""
    
    degree: str = Field(description="Degree obtained")
    college: str = Field(description="College/University name")
    graduation_year: Optional[int] = Field(default=None, description="Year of graduation")


class ProfessionalSummary(BaseModel):
    """Professional summary and goals."""
    
    about_me: str = Field(description="Brief about me section")
    career_goal: str = Field(description="Long-term career goal")
    current_learning: str = Field(description="Currently learning topics")


class Skills(BaseModel):
    """User skills organized by category."""
    
    technical_skills: List[str] = Field(default_factory=list, description="Technical programming skills")
    soft_skills: List[str] = Field(default_factory=list, description="Soft skills")
    frameworks: List[str] = Field(default_factory=list, description="Frameworks and libraries")
    languages: List[str] = Field(default_factory=list, description="Programming and spoken languages")
    tools: List[str] = Field(default_factory=list, description="Development tools")
    databases: List[str] = Field(default_factory=list, description="Database technologies")
    cloud: List[str] = Field(default_factory=list, description="Cloud platforms")
    ai_stack: List[str] = Field(default_factory=list, description="AI/ML technologies")


class Project(BaseModel):
    """Project information."""
    
    name: str = Field(description="Project name")
    short_description: str = Field(description="Brief project description")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")
    achievements: List[str] = Field(default_factory=list, description="Key achievements")
    github: Optional[str] = Field(default=None, description="GitHub repository URL")
    live_demo: Optional[str] = Field(default=None, description="Live demo URL")


class Experience(BaseModel):
    """Work experience information."""
    
    role: str = Field(description="Job role/title")
    company: str = Field(description="Company name")
    duration: str = Field(description="Duration (e.g., '2020 - Present')")
    responsibilities: List[str] = Field(default_factory=list, description="Key responsibilities")
    achievements: List[str] = Field(default_factory=list, description="Key achievements")


class Certification(BaseModel):
    """Certification information."""
    
    title: str = Field(description="Certification title")
    issuer: str = Field(description="Issuing organization")
    year: int = Field(description="Year obtained")


class WritingPreferences(BaseModel):
    """Writing style preferences."""
    
    preferred_tone: str = Field(description="Preferred writing tone")
    favourite_opening_style: str = Field(description="Preferred opening style")
    emoji_usage: str = Field(description="Emoji usage preference")
    paragraph_length: str = Field(description="Preferred paragraph length")
    preferred_cta_style: str = Field(description="Preferred call-to-action style")


class PersonalBranding(BaseModel):
    """Personal branding information."""
    
    target_audience: str = Field(description="Target audience for posts")
    niche: str = Field(description="Content niche")
    expertise: str = Field(description="Areas of expertise")
    topics_to_write_about: List[str] = Field(default_factory=list, description="Topics to write about")
    topics_to_avoid: List[str] = Field(default_factory=list, description="Topics to avoid")


class Achievements(BaseModel):
    """Achievements and milestones."""
    
    hackathons: List[str] = Field(default_factory=list, description="Hackathon achievements")
    competitions: List[str] = Field(default_factory=list, description="Competition results")
    awards: List[str] = Field(default_factory=list, description="Awards received")
    milestones: List[str] = Field(default_factory=list, description="Career milestones")


class SocialLinks(BaseModel):
    """Social media and portfolio links."""
    
    github: Optional[str] = Field(default=None, description="GitHub profile URL")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    portfolio: Optional[str] = Field(default=None, description="Portfolio website URL")
    twitter: Optional[str] = Field(default=None, description="Twitter/X profile URL")
    website: Optional[str] = Field(default=None, description="Personal website URL")


class Profile(BaseModel):
    """Complete user profile for LinkedIn content generation."""
    
    basic_info: BasicInfo
    education: Education
    professional_summary: ProfessionalSummary
    skills: Skills
    projects: List[Project] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    writing_preferences: WritingPreferences
    personal_branding: PersonalBranding
    achievements: Achievements
    social_links: SocialLinks
    
    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "basic_info": {
                    "full_name": "Jane Doe",
                    "preferred_name": "Jane",
                    "headline": "Software Engineer",
                    "current_role": "Software Engineer",
                    "organisation": "Tech Company",
                    "location": "San Francisco",
                    "years_of_experience": 5
                }
            }
        }
