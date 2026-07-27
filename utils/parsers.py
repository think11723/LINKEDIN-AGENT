"""Shared parsing utilities for LinkedIn Content Agent.

This module provides common parsing functions used across multiple agents.
"""

from typing import List, Tuple
from utils.models import LinkedInPost


def parse_structured_response(response: str, fallback_title: str = "LinkedIn Post") -> Tuple[str, str, List[str]]:
    """Parse a structured response with TITLE, CONTENT, and HASHTAGS sections.
    
    Args:
        response: Raw response string to parse.
        fallback_title: Default title if parsing fails.
        
    Returns:
        Tuple of (title, content, hashtags list).
    """
    lines = response.split('\n')
    
    title = fallback_title
    content = ""
    hashtags = []
    
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
            current_section = "title"
        elif line.startswith("CONTENT:"):
            current_section = "content"
        elif line.startswith("HASHTAGS:"):
            current_section = "hashtags"
            hashtag_line = line.replace("HASHTAGS:", "").strip()
            hashtags = [tag.strip() for tag in hashtag_line.split(",")]
        elif current_section == "content":
            content += line + "\n"
    
    # Clean up content
    content = content.strip()
    
    # Fallback if parsing failed
    if not content:
        content = response
    
    return title, content, hashtags


def create_linkedin_post(
    response: str,
    original_post: LinkedInPost = None,
    fallback_title: str = "LinkedIn Post"
) -> LinkedInPost:
    """Create a LinkedInPost from a structured response.
    
    Args:
        response: Raw response string to parse.
        original_post: Optional original post for fallback values.
        fallback_title: Default title if parsing fails.
        
    Returns:
        LinkedInPost object.
    """
    title, content, hashtags = parse_structured_response(response, fallback_title)
    
    # Use fallback values if needed
    if not hashtags and original_post:
        hashtags = original_post.hashtags
    
    return LinkedInPost(
        title=title,
        content=content,
        hashtags=hashtags
    )
