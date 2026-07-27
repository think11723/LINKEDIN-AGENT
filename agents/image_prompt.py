"""Image Prompt Agent for LinkedIn Content Agent.

This agent generates high-quality image prompts based on LinkedIn posts.
The prompts are designed for AI image models to create professional illustrations.
"""

from typing import Dict
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from models.models import LinkedInPost
from config.config import config
from services.llm import generate_text
import re


console = Console()


class ImagePrompt(BaseModel):
    """Structured image prompt for AI image generation."""
    
    prompt: str = Field(description="Detailed prompt for AI image generation")
    style: str = Field(description="Selected illustration style")
    aspect_ratio: str = Field(description="Aspect ratio for the image (e.g., 16:9, 1:1)")
    filename: str = Field(description="Suggested filename for the image")


class ImagePromptAgent:
    """Agent that generates image prompts for LinkedIn posts."""
    
    def __init__(self) -> None:
        """Initialize the Image Prompt Agent."""
        self._setup_prompt()
    
    def _setup_prompt(self) -> None:
        """Set up the system prompt for image prompt generation."""
        self.system_prompt = """You are an expert at creating image prompts for AI image generation models.
Your goal is to generate ONE professional, detailed image prompt that supports a LinkedIn post.

IMPORTANT RULES:
- NEVER include text, logos, watermarks, or UI elements in the image
- Prefer illustrations over photorealistic images unless the topic specifically needs realism
- The image should be clean, modern, and suitable for LinkedIn
- Focus on visual storytelling that complements the post content

STYLE SELECTION:
Based on the topic, automatically choose an appropriate style:
- Technology/AI: futuristic abstract technology, digital illustration
- Education/Learning: modern flat illustration, clean educational style
- Career/Professional: clean professional workspace, minimalist business style
- Programming/Development: isometric software development illustration
- General: clean modern illustration with professional color palette

OUTPUT FORMAT:
Return your response in this format:
STYLE: [selected style]
PROMPT: [detailed image prompt]"""
    
    def generate(self, post: LinkedInPost) -> ImagePrompt:
        """Generate an image prompt based on the LinkedIn post.
        
        Args:
            post: LinkedInPost to base the image prompt on.
            
        Returns:
            ImagePrompt with prompt, style, aspect ratio, and filename.
        """
        # Determine style from topic
        style = self._determine_style(post.title, post.content)
        
        # Generate prompt
        prompt = self._generate_prompt(post, style)
        
        # Generate filename
        filename = self._generate_filename(post.title)
        
        # Set aspect ratio (LinkedIn prefers 16:9 or 1:1)
        aspect_ratio = "16:9"
        
        return ImagePrompt(
            prompt=prompt,
            style=style,
            aspect_ratio=aspect_ratio,
            filename=filename
        )
    
    def _determine_style(self, title: str, content: str) -> str:
        """Determine the appropriate illustration style based on topic.
        
        Args:
            title: Post title.
            content: Post content.
            
        Returns:
            Selected style string.
        """
        text = (title + " " + content).lower()
        
        # Technology/AI
        if any(keyword in text for keyword in ["ai", "artificial intelligence", "machine learning", "technology", "automation", "robot", "agent"]):
            return "futuristic abstract technology, digital illustration"
        
        # Education/Learning
        if any(keyword in text for keyword in ["learn", "education", "course", "tutorial", "study", "journey", "skill"]):
            return "modern flat illustration, clean educational style"
        
        # Programming/Development
        if any(keyword in text for keyword in ["code", "programming", "development", "software", "api", "framework", "stack", "mern", "python"]):
            return "isometric software development illustration"
        
        # Career/Professional
        if any(keyword in text for keyword in ["career", "job", "professional", "work", "business", "growth", "opportunity"]):
            return "clean professional workspace, minimalist business style"
        
        # Default
        return "clean modern illustration with professional color palette"
    
    def _generate_prompt(self, post: LinkedInPost, style: str) -> str:
        """Generate the detailed image prompt using LLM.
        
        Args:
            post: LinkedInPost to base the prompt on.
            style: Selected illustration style.
            
        Returns:
            Detailed image prompt string.
        """
        user_prompt = f"""Generate a detailed image prompt for a LinkedIn post.

Post Title: {post.title}
Post Content: {post.content[:200]}...
Selected Style: {style}

Create a professional, engaging image prompt that visually represents this topic.
The prompt should be detailed but concise (2-3 sentences)."""
        
        response = generate_text(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=0.5
        )
        
        return self._parse_response(response, style)
    
    def _parse_response(self, response: str, fallback_style: str) -> str:
        """Parse the LLM response to extract the prompt.
        
        Args:
            response: Raw response from LLM.
            fallback_style: Style to use if parsing fails.
            
        Returns:
            Extracted image prompt string.
        """
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith("PROMPT:"):
                return line.replace("PROMPT:", "").strip()
        
        # Fallback: return the whole response
        return response
    
    def _generate_filename(self, title: str) -> str:
        """Generate a clean filename based on the title.
        
        Args:
            title: Post title.
            
        Returns:
            Clean filename string (e.g., ai_agents_2026.png).
        """
        # Remove special characters and convert to lowercase
        clean = re.sub(r'[^\w\s-]', '', title.lower())
        # Replace spaces with underscores
        clean = re.sub(r'[-\s]+', '_', clean)
        # Limit length
        clean = clean[:50]
        # Add .png extension
        return f"{clean}.png"


def print_image_prompt(image_prompt: ImagePrompt) -> None:
    """Print image prompt details beautifully using Rich.
    
    Args:
        image_prompt: ImagePrompt to display.
    """
    console.print("\n")
    
    # Style panel
    console.print(Panel(
        f"[bold cyan]{image_prompt.style}[/bold cyan]",
        title="[bold]Selected Style[/bold]",
        border_style="cyan",
        padding=(0, 2)
    ))
    
    # Prompt
    console.print(f"\n[dim]Image Prompt:[/dim]")
    console.print(f"[white]{image_prompt.prompt}[/white]\n")
    
    # Details
    console.print(f"[dim]Aspect Ratio:[/dim] [cyan]{image_prompt.aspect_ratio}[/cyan]")
    console.print(f"[dim]Filename:[/dim] [cyan]{image_prompt.filename}[/cyan]")
    console.print("\n")


if __name__ == "__main__":
    # Test the Image Prompt Agent
    console.print("[bold]Testing Image Prompt Agent[/bold]\n")
    
    # Create sample LinkedInPost
    sample_post = LinkedInPost(
        title="The Rise of AI Agents in 2026",
        content="AI agents are transforming how we work and interact with technology. From automating repetitive tasks to providing intelligent assistance, these systems are becoming indispensable. The future looks promising with more sophisticated agents emerging.",
        hashtags=["#AI", "#Agents", "#Technology", "#Future"]
    )
    
    # Generate image prompt
    agent = ImagePromptAgent()
    image_prompt = agent.generate(sample_post)
    
    # Print results
    print_image_prompt(image_prompt)
