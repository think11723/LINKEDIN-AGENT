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

Source-aware mode (Phase 5):

When the optional ``source`` dict is supplied, the Writer treats the
input as a ``SOURCE INSPIRED`` post — not a generic topic post. It
emits a real LinkedIn-style post that:

* preserves only facts grounded in the supplied source facts,
* never invents metrics, users, scale, ownership, or features,
* uses a source-type-specific narrative angle
  (see :mod:`backend.app.services.sources.classification`),
* ends naturally with a tasteful attribution to the source URL,
* explicitly distinguishes ``SOURCE FACTS`` (grounding) from
  ``USER'S DESIRED ANGLE`` (the framing hint) and the writing style.

The base prompt already teaches LinkedIn-native formatting (no
Markdown, no "Hashtags:" label, bullets as ``→`` or ``•``, short
paragraphs). Source mode ADDS an anti-hallucination block and
type-specific guidance to the user message so the model can
recognize what kind of source it is dealing with.
"""

from typing import Any, Dict, List, Optional
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
        execution_plan: Optional[object] = None,
        source: Optional[Dict[str, Any]] = None,
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
            source: Optional Phase-5 source context. When provided the
                writer treats the post as source-inspired and applies
                strict grounding rules (no fabrication of metrics,
                users, scale, ownership, or features).

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

        # Build context with enhanced information. When ``source`` is
        # provided we always include its facts in the user message
        # (the LLM must see them, not just the legacy research
        # snippets), and the framing hint is forwarded as the user's
        # "desired angle".
        context_str = self._build_context(
            topic,
            intent,
            user_prompt,
            research,
            profile_summary,
            edit_instruction,
            execution_plan,
            context,
            source=source,
        )

        # Create prompt. In source mode, prepend an anti-hallucination
        # block to the user message that explicitly distinguishes
        # source facts (grounding) from the user's desired angle.
        if source:
            prompt = self._create_source_prompt(context_str, source)
        else:
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
        context: Optional[Context] = None,
        source: Optional[Dict[str, Any]] = None,
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
            source: Optional Phase-5 source context. When supplied, its
                facts are emitted under a clearly-labelled "SOURCE
                FACTS" block in the user message and the framing hint
                is forwarded as the "USER'S DESIRED ANGLE".

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

        # Source-aware block. The writer prompt places these facts in
        # an explicit "SOURCE FACTS" section so the model can read
        # them as grounding rather than as background colour.
        if source:
            context_str += "\n=== SOURCE FACTS (GROUNDING — DO NOT INVENT) ===\n"
            context_str += f"Source Type: {source.get('source_type') or 'webpage'}\n"
            if source.get('source_title'):
                context_str += f"Source Title: {source['source_title']}\n"
            if source.get('source_url'):
                context_str += f"Source URL: {source['source_url']}\n"
            if source.get('source_summary'):
                context_str += f"Source Summary: {source['source_summary'][:1500]}\n"
            facts = source.get('key_points') or []
            if facts:
                context_str += "Key Points:\n"
                for fact in facts[:8]:
                    context_str += f"- {str(fact)[:300]}\n"
            tech = source.get('technical_details') or []
            if tech:
                context_str += "Technical Details:\n"
                for detail in tech[:6]:
                    context_str += f"- {str(detail)[:300]}\n"
            author = source.get('author') or source.get('source_metadata', {}).get('owner') if isinstance(source.get('source_metadata'), dict) else None
            if author:
                context_str += f"Author / Owner: {author}\n"
            framing = source.get('framing_hint')
            if framing:
                context_str += f"\n=== USER'S DESIRED ANGLE (framing hint) ===\n{str(framing)[:600]}\n"
            context_str += (
                "\nGROUNDING RULES:\n"
                "- Every factual claim in the post MUST be supported by the SOURCE FACTS above.\n"
                "- If a number, scale, user count, ownership, or feature is not in the SOURCE FACTS, do not invent it.\n"
                "- Never claim the user 'built' or 'discovered' the source unless the user explicitly said so.\n"
                "- If the SOURCE FACTS are empty or irrelevant, write a short, honest post that says you came across the source and want to share it, and link to it.\n"
            )

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

    # ------------------------------------------------------------------
    # Phase 5 / source-aware prompt
    # ------------------------------------------------------------------

    #: Narrative-angle instruction per source type. Kept here (not
    #: imported from the API layer) so the Writer stays self-contained
    #: and runnable in CLI / notebook contexts.
    _SOURCE_NARRATIVE_ANGLES: Dict[str, str] = {
        "github_repository": (
            "Treat this as a software engineering audience. Focus on the project's "
            "purpose, the technical idea behind it, and why a working developer would "
            "find it interesting. Mention the primary language, the README's first "
            "substantive paragraph, and any listed features if they are clearly supported."
        ),
        "github_readme": (
            "Treat this as a focused technical-document read. Highlight the README's "
            "core claim, the architecture or design decision, and what a developer "
            "would learn by reading the document."
        ),
        "blog_article": (
            "Treat this as a working professional's reaction to an article. Lead with "
            "the article's strongest insight, then add a useful interpretation or "
            "contrasting angle. Do not just paraphrase."
        ),
        "documentation": (
            "Treat this as a developer reading docs. Highlight the capability the docs "
            "describe, the use case, and the practical takeaway for a working engineer."
        ),
        "product_page": (
            "Treat this as a launch / announcement page. Focus on what changed, why "
            "it matters, and who benefits. Keep it factual and useful, not promotional."
        ),
        "generic_webpage": (
            "Treat this as a general public page. Lead with the strongest insight or "
            "the most useful interpretation, and end with a clean link to the source."
        ),
    }

    def _create_source_prompt(self, context: str, source: Dict[str, Any]) -> str:
        """Build a source-aware user message for the LLM.

        Prepends an explicit "this is a source-inspired post" block
        to the standard prompt so the model:

        * recognizes the input as a source (not a topic prompt),
        * applies the matching narrative angle,
        * obeys the grounding rules emitted by :meth:`_build_context`,
        * produces a post that is not a summary of the source but
          rather a LinkedIn-style reaction to it.
        """
        source_type = (source or {}).get("source_type") or "generic_webpage"
        angle = self._SOURCE_NARRATIVE_ANGLES.get(
            source_type,
            self._SOURCE_NARRATIVE_ANGLES["generic_webpage"],
        )
        source_url = (source or {}).get("source_url") or ""
        framing = (source or {}).get("framing_hint") or ""

        # Anti-summary guidance: explicitly tell the model what the
        # output should NOT look like and what it SHOULD look like.
        bad_example = (
            "BAD (this is what a generic LLM produces, looks broken on LinkedIn):\n"
            "----\n"
            "This GitHub repository is a software project.\n"
            "It uses Python.\n"
            "It has several features.\n"
            "You can find it here: https://github.com/owner/repo\n"
            "----\n"
            "Why it is bad: it reads like a documentation summary, not a human "
            "LinkedIn post. There is no hook, no insight, no reaction, and no "
            "value for the reader.\n"
        )
        good_example = (
            "GOOD (the same source, properly LinkedIn-native):\n"
            "----\n"
            "Came across an interesting approach to building ...\n\n"
            "What caught my attention was the way it ...\n\n"
            "A few things stood out:\n"
            "• ...\n"
            "• ...\n"
            "• ...\n\n"
            "The bigger takeaway for me:\n"
            "...\n\n"
            "🔗 Worth exploring if you're working with ...\n"
            "https://github.com/owner/repo\n\n"
            "#OpenSource #Python\n"
            "----\n"
            "Why it is good: it has a hook, an honest reaction, useful bullets, a "
            "takeaway, a tasteful link, and relevant hashtags. It does NOT pretend "
            "the user built the project.\n"
        )

        framing_block = (
            f"USER FRAMING HINT (optional): {framing}\n"
            if framing
            else "USER FRAMING HINT: none — choose a sensible angle yourself.\n"
        )

        # Inline the source URL in the prompt so the model can decide
        # whether to surface it in the post.
        url_block = (
            f"SOURCE URL (include as a plain link, NOT as [text](url)): {source_url}\n"
            if source_url
            else "SOURCE URL: (none — the source may not have a public URL)\n"
        )

        prompt = f"""This request is a SOURCE-INSPIRED LinkedIn post. The user pasted
a public URL and the system has already fetched and analyzed the source.

Your job is NOT to summarize the source. Your job is to write a real
LinkedIn post — the kind a thoughtful professional would publish after
reading the source.

SOURCE TYPE: {source_type}
NARRATIVE ANGLE: {angle}
{framing_block}{url_block}
{bad_example}{good_example}
═══════════════════════════════════════════════════════════════
CONTEXT (grounding + planning):

{context}

═══════════════════════════════════════════════════════════════

Write a LinkedIn post for the SOURCE INSPIRED by the SOURCE FACTS above.
Apply every LinkedIn-native rule from the system prompt: no Markdown,
plain text, blank-line paragraph breaks, emojis sparingly, "→" or "•"
bullets, hashtags at the end WITHOUT a "Hashtags:" label.

If a "USER FRAMING HINT" is present, take the hint as the angle.
If not, choose an angle that matches the SOURCE TYPE.

If a SOURCE URL is present, include it as a plain inline link at the
end of the post (e.g. "🔗 Worth exploring: https://..."). Do NOT
surround it with Markdown link syntax.

Do NOT invent any metric, user count, feature, ownership claim, or
performance number that is not present in the SOURCE FACTS.

Return your response in this exact format:

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
