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

LINKEDIN POST STRUCTURE:
1. Compelling Hook: Grab attention with a strong opening statement or question
2. Context: Briefly set the scene with relevant background
3. Main Insights: Share 2-3 substantive points with depth
4. Actionable Takeaway: Give readers something practical they can apply
5. Closing Thought: Professional sign-off with meaningful reflection
6. Call-to-Action: Clear next step or question to engage readers
7. Hashtags: 5-10 relevant hashtags at the end only

WRITING STYLE RULES:
- Professional but conversational tone
- Short, readable paragraphs (2-3 sentences max)
- Natural transitions between ideas
- First-person perspective for personal experiences
- Clear, concise sentences
- Avoid jargon unless explaining it

CONTENT QUALITY:
- Practical insights over generic advice
- Educational value over promotional content
- Credibility through specific examples
- Concise storytelling
- Informative rather than promotional

WHAT TO AVOID:
- Clickbait titles or exaggerated claims
- Unnecessary hype or buzzwords
- Generic motivational quotes
- Excessive emojis (use sparingly, maximum 2-3 per post)
- Rocket ships, fire emojis, or similar clickbait tactics
- Marketing language or sales pitches

LENGTH: 180-300 words total.

RESEARCH INTEGRATION:
If research results are provided:
- Incorporate insights naturally into the narrative
- Never mention sources or URLs
- Never copy snippets verbatim
- Summarize findings in your own words
- Use research to add credibility, not as the main content
- Reference key statistics or facts when relevant

PERSONALIZATION:
Use the author's profile information to:
- Match their expertise level and voice
- Reference their actual skills and experience
- Align with their career goals and interests
- Maintain consistency with their professional brand"""

        self.system_prompt = system_prompt
    
    def write(
        self,
        topic: str,
        intent: str,
        user_prompt: str,
        research: Optional[List[Dict[str, str]]] = None,
        writing_style: str = "professional",
        edit_instruction: Optional[str] = None,
        context: Optional[Context] = None,
        execution_plan: Optional[object] = None
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
            execution_plan: Optional execution plan from Planner with structured information.
            
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
        
        # Build context with enhanced information
        context_str = self._build_context(topic, intent, user_prompt, research, profile_summary, edit_instruction, execution_plan, context)
        
        # Create prompt
        prompt = self._create_prompt(context_str)
        
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
        edit_instruction: Optional[str] = None,
        execution_plan: Optional[object] = None,
        context: Optional[Context] = None
    ) -> str:
        """Build context string for the LLM.
        
        Args:
            topic: Main topic.
            intent: User intent.
            user_prompt: Original prompt.
            research: Optional research results.
            profile_summary: Optional profile summary for personalization.
            edit_instruction: Optional edit instruction for refinement.
            execution_plan: Optional execution plan from Planner with structured information.
            context: Optional unified context object with user preferences.
            
        Returns:
            Formatted context string.
        """
        context_str = f"Topic: {topic}\n"
        context_str += f"Intent: {intent}\n"
        context_str += f"Original Request: {user_prompt}\n"
        
        # Add execution plan details if available
        if execution_plan:
            context_str += f"\nExecution Plan:\n"
            if hasattr(execution_plan, 'key_points'):
                context_str += f"Key Points: {', '.join(execution_plan.key_points)}\n"
            if hasattr(execution_plan, 'angle'):
                context_str += f"Angle: {execution_plan.angle}\n"
            if hasattr(execution_plan, 'target_audience'):
                context_str += f"Target Audience: {execution_plan.target_audience}\n"
        
        # Add profile summary if available
        if profile_summary:
            context_str += f"\nAuthor Profile: {profile_summary}\n"
        
        # Add additional context information
        if context:
            if context.expertise:
                context_str += f"Author Expertise: {context.expertise}\n"
            if context.niche:
                context_str += f"Content Niche: {context.niche}\n"
            if context.target_audience:
                context_str += f"Target Audience: {context.target_audience}\n"
        
        if research:
            context_str += "\nResearch Insights:\n"
            for i, result in enumerate(research[:3], 1):
                context_str += f"- {result['title']}: {result['snippet'][:200]}...\n"
        
        # Add edit instruction if provided
        if edit_instruction:
            context_str += f"\nEdit Instruction: {edit_instruction}\n"
        
        return context_str
    
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
