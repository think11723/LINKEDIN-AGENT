"""Writer Agent for LinkedIn Content Agent.

This agent generates professional LinkedIn posts based on execution context.
It uses Gemini LLM to create engaging, natural content without marketing fluff.

The raw LLM output is normalized through
:func:`utils.linkedin_content.normalize_linkedin_post` before being
returned. That single canonical normalization layer is the final
defense against residual Markdown markers (##, **, etc.) and
"Hashtags: ..." leakage that LLMs frequently produce. The Draft
Viewer, approval, and LinkedIn publishing all consume the
normalized form, so they never re-apply their own cleanup.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
from config.config import config
from models.models import LinkedInPost
from models.context_models import Context
from utils.linkedin_content import normalize_linkedin_post
from utils.parsers import create_linkedin_post
from utils.style_manager import load_style_prompt
from services.llm import LLMFactory
import logging
logger = logging.getLogger(__name__)


console = Console()


class WriterAgent:
    """Agent that generates professional LinkedIn posts."""
    
    def __init__(self) -> None:
        """Initialize the Writer Agent."""
        # Phase 8E: prefer LLMFactory.fallback() so a runtime 429 / 404 /
        # 401 / 5xx on the first provider in the priority list
        # automatically cascades to the secondary and tertiary providers.
        self.llm = LLMFactory.fallback("writer")
        self._setup_prompt()

    def provider_info(self) -> dict[str, str]:
        """Return ``{"provider": ..., "model": ...}`` for the last-resolved LLM."""
        llm = getattr(self, "llm", None)
        if llm is None:
            return {"provider": "unknown", "model": "unknown"}
        return {
            "provider": getattr(llm, "provider_name", "unknown"),
            "model": getattr(llm, "model", "unknown"),
        }
    
    def _setup_prompt(self) -> None:
        """Set up the system prompt for LinkedIn content generation.

        Explicitly teaches the model what 'native LinkedIn' means:
        plain text, no Markdown, no document structure, with a
        concrete BAD vs GOOD example so the model has a target
        image of LinkedIn-native output.
        """
        system_prompt = """You are an experienced software engineer and LinkedIn content creator.
Your goal is to write professional, engaging LinkedIn posts that sound authentic and natural.

YOU ARE WRITING A NATIVE LINKEDIN POST, NOT A MARKDOWN DOCUMENT.

LinkedIn does NOT render Markdown. NEVER use ANY of:

- # ## ### #### for headings
- **bold** or __bold__ Markdown emphasis
- *italic* or _italic_ Markdown emphasis
- `inline code` backticks or ```code fences```
- Markdown tables with | --- |
- Markdown links like [text](url)
- ___ or *** horizontal rules
- A footer label like "Hashtags:" followed by a list of tags
- Article/document-style structure (title, intro, numbered sections, conclusion)
- Bullet points with leading hyphens at line starts (- item)
  (LinkedIn renders leading hyphens as plain text, which looks broken)

Instead use LinkedIn-native plain-text formatting:

- Short paragraphs (1-3 lines max each)
- Blank lines between paragraphs (LinkedIn renders blank lines as paragraph breaks)
- Emojis sparingly for emphasis (max 2-3 per post total)
- A single strong opening line as the hook
- Occasional standalone one-line emphasis (just bold-ish through brevity, not markup)
- Bullets rendered as "→ item" or "• item" (visible character, not Markdown hyphen)
- Conversational but professional tone

EXAMPLE: BAD (this is what an LLM naturally produces, looks broken on LinkedIn):

```
## 5 Things I Learned

**First**, RAG is powerful.

- Better retrieval
- Better grounding

Hashtags: #AI #RAG
```

Why it's bad:
- "##" renders as literal "##" on LinkedIn
- "**First**" renders as literal asterisks around the word
- "- Better retrieval" renders with literal hyphens (Markdown list)
- "Hashtags:" footer is unnatural and the hashtags would be inside the body

EXAMPLE: GOOD (the SAME content, properly LinkedIn-native):

```
5 things I learned building RAG systems

RAG isn't just about adding a vector database to an LLM.

The interesting part is what happens between the user's question and the final answer.

→ Better retrieval
→ Better grounding
→ More controllable context

The biggest lesson?

A good RAG system is as much about retrieval quality as it is about the model itself.

#AI #RAG #GenerativeAI
```

Why it's good:
- Plain text, no Markdown syntax
- Short readable paragraphs with blank-line separators
- Bullets rendered as "→ item" with a visible arrow
- Hashtags at the end WITHOUT a "Hashtags:" label
- Reads naturally in the LinkedIn feed

DO NOT FORCE THIS EXACT STRUCTURE ON EVERY POST. Use it as a style target. The model has stylistic freedom — vary the hook, the rhythm, the bullet style. The non-negotiable rules are: no Markdown, plain text, blank lines between paragraphs, hashtags at the end without a label.

LINKEDIN POST STRUCTURE (guidelines, not a fixed template):

1. Hook — A strong opening that grabs attention within the first two lines. Never use clickbait.
2. Story / context — Explain why you explored this topic, what problem you faced, what you learned. Keep it personal.
3. Main insight — Present information using bullets or numbered lists. Bullets can be "→", "•", or short numbered lines ("1." / "2.").
4. Real example — Include a practical coding insight, real-world analogy, or project experience. Do not generate textbook explanations.
5. Key takeaway — End with "The biggest lesson for me was..." or similar.
6. Call to action — Engage readers with questions like "What do you think?" or "How would you explain this?" Avoid generic "Follow for more."
7. Hashtags — 3-6 relevant hashtags at the END of the post, with NO preceding label. Example: "#Python #OOP #SoftwareEngineering #Programming #Developer"

WRITING STYLE:
Write like a software engineer documenting their journey. Tone should be:
- Curious
- Honest
- Reflective
- Confident
- Educational

Avoid sounding like ChatGPT, textbook language, or corporate marketing.

PERSONAL VOICE:
When appropriate, reference learning journey naturally:
- Building projects
- Learning AI Agents
- Learning LangGraph
- Learning RAG
- Learning Full Stack
- Experimenting with Python

Only use context already available in memory/profile. Do NOT invent fake stories.

READABILITY RULES:
- Maximum paragraph length: 3 lines
- Maximum sentence length: 20-25 words
- Add whitespace frequently (LinkedIn renders blank lines as paragraph breaks)
- Optimize for mobile viewing
- Avoid walls of text

LENGTH: 180-300 words total.

RESEARCH INTEGRATION:
If research results are provided:
- Incorporate insights naturally into the narrative
- Never mention sources or URLs in the body
- Never copy snippets verbatim
- Summarize findings in your own words
- Use research to add credibility, not as the main content
- Reference key statistics or facts when relevant

PERSONALIZATION:
Use the author's profile information to:
- Match their expertise level and voice
- Reference their actual skills and experience
- Align with their career goals and interests
- Maintain consistency with their professional brand

QUALITY CHECKLIST (self-validate before returning):
✓ No Markdown syntax (no ##, **, *, _, `, |, -, etc.)
✓ No backticks
✓ No **bold** or *italic* or _italic_ markers
✓ Strong first-line hook
✓ Personal tone
✓ Professional formatting
✓ Easy to read on mobile
✓ Practical insight
✓ CTA included
✓ Relevant hashtags included at end WITHOUT a label

If any validation fails, automatically rewrite the post before returning it."""

        self.system_prompt = system_prompt
    
    async def write(
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
        logger.info("===== Writer: Sending request to LLM =====")
        # The LLM is async (FallbackProvider.generate_text is a
        # coroutine that walks the provider chain). Awaiting it
        # actually executes the call; without ``await`` we'd get a
        # coroutine object and the next line (``response.text``)
        # would fail with "'coroutine' object has no attribute 'text'".
        response = await self.llm.generate_text(prompt, temperature=0.7)
        logger.info("===== Writer: Response received =====")
        
        # Parse the structured TITLE/CONTENT/HASHTAGS sections from the
        # LLM response, then run the result through the canonical
        # LinkedIn content normalizer. The normalizer strips any
        # residual Markdown markers, removes trailing "Hashtags:" lines,
        # and produces a clean LinkedIn-native representation. This is
        # the ONLY place where Writer output is normalized — downstream
        # code (Draft Viewer, approval, publishing) trusts the
        # normalized form.
        parsed = create_linkedin_post(
            response.text, fallback_title="LinkedIn Post"
        )
        post = normalize_linkedin_post(
            title=parsed.title,
            content=parsed.content,
            hashtags=parsed.hashtags,
        )

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
