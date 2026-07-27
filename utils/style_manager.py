"""Style Manager for LinkedIn Content Agent.

This module handles writing style detection and prompt loading
for different LinkedIn writing styles.
"""

from pathlib import Path
from typing import Optional


# Supported writing styles
STYLES = [
    "professional",
    "storytelling",
    "technical_deep_dive",
    "educational",
    "founder",
    "career_journey",
    "beginner_friendly",
    "opinion",
    "product_launch",
    "hiring"
]

# Style detection keywords
STYLE_KEYWORDS = {
    "storytelling": ["story", "narrative", "personal story", "share my story", "journey"],
    "technical_deep_dive": ["technical", "deep dive", "technical deep dive", "deep dive into", "explain how", "how it works"],
    "educational": ["educational", "teach", "explain", "tutorial", "learn", "beginner guide"],
    "founder": ["founder", "startup", "building", "entrepreneur", "company building"],
    "career_journey": ["career", "career journey", "professional growth", "career advice", "job"],
    "beginner_friendly": ["beginner", "new to", "starting out", "getting started", "for beginners"],
    "opinion": ["opinion", "my take", "i think", "my perspective", "thoughts on"],
    "product_launch": ["launch", "product", "announcing", "we built", "introducing"],
    "hiring": ["hiring", "we're hiring", "join our team", "recruiting", "job opening"]
}

STYLES_DIR = Path(__file__).parent.parent / "prompts" / "styles"


def detect_style(user_prompt: str) -> str:
    """Detect writing style from user prompt.
    
    Args:
        user_prompt: User's natural language prompt.
        
    Returns:
        Detected writing style (defaults to "professional").
    """
    prompt_lower = user_prompt.lower()
    
    # Check for style-specific keywords
    for style, keywords in STYLE_KEYWORDS.items():
        if any(keyword in prompt_lower for keyword in keywords):
            return style
    
    # Default to professional
    return "professional"


def load_style_prompt(style: str) -> Optional[str]:
    """Load prompt template for a specific writing style.
    
    Args:
        style: Writing style name.
        
    Returns:
        Prompt template string, or None if not found.
    """
    # Normalize style name (replace spaces with underscores)
    style_filename = f"{style}.txt"
    style_path = STYLES_DIR / style_filename
    
    if not style_path.exists():
        return None
    
    try:
        with open(style_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def get_available_styles() -> list[str]:
    """Get list of available writing styles.
    
    Returns:
        List of available style names.
    """
    available = []
    
    if not STYLES_DIR.exists():
        return available
    
    for style_file in STYLES_DIR.glob("*.txt"):
        style_name = style_file.stem
        if style_name in STYLES:
            available.append(style_name)
    
    return available


def style_exists(style: str) -> bool:
    """Check if a writing style exists.
    
    Args:
        style: Writing style name.
        
    Returns:
        True if style exists, False otherwise.
    """
    style_filename = f"{style}.txt"
    style_path = STYLES_DIR / style_filename
    return style_path.exists()


if __name__ == "__main__":
    # Test style detection
    test_prompts = [
        "Write a storytelling post about my career",
        "Create a technical deep dive on React",
        "Write an educational post about Python",
        "Share a founder story about building my startup",
        "Write about my career journey",
        "Create a beginner-friendly guide to Docker",
        "Share my opinion on AI",
        "Announce our new product launch",
        "Write a hiring post for our team",
        "Write a professional post about leadership"
    ]
    
    for prompt in test_prompts:
        detected = detect_style(prompt)
        print(f"Prompt: {prompt}")
        print(f"Detected: {detected}\n")
