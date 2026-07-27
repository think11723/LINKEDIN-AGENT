"""Writer Agent for LinkedIn Content Agent.

This agent generates professional LinkedIn posts based on execution context.
It uses Gemini LLM to create engaging, natural content without marketing fluff.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
from config.config import config
from models.models import LinkedInPost
from models.context_models import Context
from utils.parsers import create_linkedin_post
from utils.style_manager import load_style_prompt
from services.llm import generate_text


console = Console()


class WriterAgent:
    """Agent that generates professional LinkedIn posts."""
    
    def __init__(self) -> None:
        """Initialize the Writer Agent."""
        self._setup_prompt()
    
    def _setup_prompt(self) -> None:
        """Set up the system prompt for LinkedIn content generation."""
        system_prompt = """You are an experienced software engineer and LinkedIn content creator. 
Your goal is to write professional, engaging LinkedIn posts that sound authentic and natural.

IMPORTANT GUIDELINES:
- Write like a real professional sharing insights, not marketing copy
- Never exaggerate or use hype language
- Avoid excessive emojis (use sparingly if at all)
- No rocket ships, fire emojis, or clickbait tactics
- Be genuine, thoughtful, and informative
- Use first-person perspective when sharing personal experiences
- Keep sentences clear and readable

LINKEDIN POST STRUCTURE:
1. Hook: Grab attention with a compelling opening
2. Short story/introduction: Set context naturally
3. Main insights: Share 2-3 key points with substance
4. Actionable takeaway: Give readers something practical
5. Closing: Professional sign-off
6. Hashtags: 5-10 relevant hashtags at the end

LENGTH: 200-350 words total.

RESEARCH INTEGRATION:
If research results are provided, incorporate insights naturally.
- Never mention sources or URLs
- Never copy snippets verbatim
- Summarize findings in your own words
- Use research to add credibility, not as the main content"""

        self.system_prompt = system_prompt
    
    def write(
        self,
        topic: str,
        intent: str,
        user_prompt: str,
        research: Optional[List[Dict[str, str]]] = None,
        writing_style: str = "professional",
        edit_instruction: Optional[str] = None,
        context: Optional[Context] = None
    ) -> LinkedInPost:
        """Generate a LinkedIn post based on execution context.
        
        Args:
            topic: Main topic of the post.
            intent: User's intent (e.g., share experience, discuss trend).
            user_prompt: Original user request.
            research: Optional search results for grounding.
            writing_style: Writing style for the post.
            edit_instruction: Optional edit instruction for refining the post.
            context: Unified context object with user preferences.
            
        Returns:
            LinkedInPost: Structured LinkedIn post with title, content, and hashtags.
        """
        # Use context for profile summary
        profile_summary = context.profile_summary if context else None
        
        # Load style-specific prompt from context if available
        if context and context.get_style_prompt():
            self.system_prompt = context.get_style_prompt()
        else:
            # Fallback to loading from file
            style_prompt = load_style_prompt(writing_style)
            if style_prompt:
                self.system_prompt = style_prompt
            else:
                # Fallback to default prompt if style not found
                self._setup_prompt()
        
        # Build context
        context = self._build_context(topic, intent, user_prompt, research, profile_summary, edit_instruction)
        
        # Create prompt
        prompt = self._create_prompt(context)
        
        # Generate content
        response = generate_text(
            system_prompt=self.system_prompt,
            user_prompt=prompt,
            temperature=0.7
        )
        
        # Parse response
        post = create_linkedin_post(response, fallback_title="LinkedIn Post")
        
        return post
    
    def _build_context(
        self,
        topic: str,
        intent: str,
        user_prompt: str,
        research: Optional[List[Dict[str, str]]],
        profile_summary: Optional[str] = None,
        edit_instruction: Optional[str] = None
    ) -> str:
        """Build context string for the LLM.
        
        Args:
            topic: Main topic.
            intent: User intent.
            user_prompt: Original prompt.
            research: Optional research results.
            profile_summary: Optional profile summary for personalization.
            edit_instruction: Optional edit instruction for refinement.
            
        Returns:
            Formatted context string.
        """
        context = f"Topic: {topic}\n"
        context += f"Intent: {intent}\n"
        context += f"Original Request: {user_prompt}\n"
        
        # Add profile summary if available
        if profile_summary:
            context += f"\nAuthor Profile: {profile_summary}\n"
        
        if research:
            context += "\nResearch Insights:\n"
            for i, result in enumerate(research[:3], 1):
                context += f"- {result['title']}: {result['snippet'][:200]}...\n"
        
        # Add edit instruction if provided
        if edit_instruction:
            context += f"\nEdit Instruction: {edit_instruction}\n"
        
        return context
    
    def _create_prompt(self, context: str) -> str:
        """Create the full prompt for the LLM.
        
        Args:
            context: Built context string.
            
        Returns:
            Full prompt for content generation.
        """
        prompt = f"""Based on the following context, write a LinkedIn post:

{context}

Generate a complete LinkedIn post following the structure and guidelines provided.
Return your response in this format:

TITLE: [post title]
CONTENT: [post content]
HASHTAGS: [comma-separated hashtags]"""
        
        return prompt
    


def save_markdown(post: LinkedInPost, output_path: Optional[Path] = None) -> None:
    """Save LinkedIn post as Markdown file.
    
    Args:
        post: LinkedInPost to save.
        output_path: Optional custom output path. Defaults to output/latest_post.md.
    """
    if output_path is None:
        output_path = config.output_dir / "latest_post.md"
    
    markdown_content = f"# {post.title}\n\n"
    markdown_content += f"{post.content}\n\n"
    markdown_content += " ".join(post.hashtags)
    
    output_path.write_text(markdown_content, encoding='utf-8')
    console.print(f"[green]✓[/green] [dim]Post saved to:[/dim] [cyan]{output_path}[/cyan]")


def print_post(post: LinkedInPost) -> None:
    """Print LinkedIn post beautifully using Rich.
    
    Args:
        post: LinkedInPost to display.
    """
    console.print("\n")
    
    # Title
    console.print(Panel(
        f"[bold cyan]{post.title}[/bold cyan]",
        title="LinkedIn Post",
        border_style="cyan"
    ))
    
    # Content
    console.print(f"\n{post.content}\n")
    
    # Hashtags
    console.print(f"[dim]{', '.join(post.hashtags)}[/dim]")
    console.print("\n")


if __name__ == "__main__":
    # Test the Writer Agent
    console.print("[bold]Testing Writer Agent[/bold]\n")
    
    agent = WriterAgent()
    
    # Generate sample post
    post = agent.write(
        topic="AI Agents in 2026",
        intent="discuss industry trend",
        user_prompt="AI Agents in 2026",
        research=None
    )
    
    # Print beautifully
    print_post(post)
    
    # Save as markdown
    save_markdown(post)
