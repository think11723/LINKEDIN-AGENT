"""LinkedIn Content Agent - Main Orchestrator.

This is the central entry point that orchestrates all agents and tools
to create and publish LinkedIn posts from natural language prompts.
"""

from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from agents.planner import PlannerAgent, ExecutionPlan
from agents.writer import WriterAgent
from agents.reviewer import ReviewerAgent, ReviewResult, print_review_result
from agents.image_prompt import ImagePromptAgent, ImagePrompt, print_image_prompt
from agents.publisher import PublisherAgent
from tools.search import search_web
from tools.image_generator import generate_image
from utils.config import config
from utils.models import LinkedInPost


console = Console()


def display_welcome() -> None:
    """Display welcome message."""
    console.print("\n")
    
    # Main welcome panel
    console.print(Panel(
        "[bold cyan]LinkedIn Content Agent[/bold cyan]\n\n"
        "[dim]AI-powered LinkedIn post creator[/dim]\n\n"
        "[dim]✓ Planning  ✓ Research  ✓ Writing[/dim]\n"
        "[dim]✓ Review  ✓ Images  ✓ Publishing[/dim]",
        border_style="cyan",
        padding=(1, 3),
        title="🚀 Welcome",
        subtitle="v1.0"
    ))
    
    console.print("\n")


def get_user_prompt() -> str:
    """Get natural language prompt from user.
    
    Returns:
        User's input prompt.
    """
    console.print("\n")
    console.print(Panel(
        "[bold]What would you like to post about?[/bold]\n\n"
        "[dim]Example: Create a LinkedIn post about the future of AI Agents[/dim]",
        border_style="blue",
        padding=(0, 2)
    ))
    console.print("\n")
    
    user_input = console.input("[bold cyan]➜ [/bold cyan]")
    
    return user_input.strip()


def get_edit_instruction() -> str:
    """Get edit instruction from user.
    
    Returns:
        User's edit instruction.
    """
    console.print("\n")
    console.print(Panel(
        "[bold]How would you like to improve the post?[/bold]\n\n"
        "[dim]Examples:[/dim]\n"
        "[dim]• Make it shorter[/dim]\n"
        "[dim]• Make it technical[/dim]\n"
        "[dim]• Reduce emojis[/dim]\n"
        "[dim]• More storytelling[/dim]\n"
        "[dim]• Add statistics[/dim]\n"
        "[dim]• Make it suitable for recruiters[/dim]",
        border_style="blue",
        padding=(0, 2)
    ))
    console.print("\n")
    
    edit_instruction = console.input("[bold cyan]➜ [/bold cyan]")
    
    return edit_instruction.strip()


def display_status(message: str) -> None:
    """Display status message with spinner.
    
    Args:
        message: Status message to display.
    """
    with Progress(
        SpinnerColumn("dots"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
        refresh_per_second=10
    ) as progress:
        progress.add_task(f"[cyan]{message}[/cyan]", total=None)


def display_execution_plan(plan: ExecutionPlan) -> None:
    """Display the execution plan from Planner Agent.
    
    Args:
        plan: ExecutionPlan to display.
    """
    console.print("\n")
    
    table = Table(
        title="[bold]Execution Plan[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 1)
    )
    table.add_column("[dim]Aspect[/dim]", style="cyan", width=20)
    table.add_column("[dim]Details[/dim]", style="white")
    
    table.add_row("Topic", plan.topic)
    table.add_row("Intent", plan.intent)
    table.add_row("Tone", plan.tone)
    
    if plan.requires_search:
        table.add_row("Search Required", "[green]✓ Yes[/green]")
        table.add_row("Search Reason", plan.search_reason)
    else:
        table.add_row("Search Required", "[dim]✗ No[/dim]")
    
    console.print(table)
    console.print("\n")


def display_summary(
    plan: ExecutionPlan,
    review_result: ReviewResult,
    image_path: Optional[Path]
) -> None:
    """Display final summary before publishing.
    
    Args:
        plan: Execution plan.
        review_result: Review result with scores.
        image_path: Optional path to generated image.
    """
    console.print("\n")
    
    # Summary table
    table = Table(
        title="[bold]Content Summary[/bold]",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
        padding=(0, 1)
    )
    table.add_column("[dim]Aspect[/dim]", style="cyan", width=20)
    table.add_column("[dim]Value[/dim]", style="white")
    
    table.add_row("Topic", plan.topic)
    table.add_row("Intent", plan.intent)
    table.add_row("Writing Style", f"[cyan]{plan.writing_style.replace('_', ' ').title()}[/cyan]")
    table.add_row("Search Used", "[green]✓ Yes[/green]" if plan.requires_search else "[dim]✗ No[/dim]")
    
    # Color-code the review score
    score_color = "green" if review_result.scores.overall >= 8 else "yellow" if review_result.scores.overall >= 6 else "red"
    table.add_row("Review Score", f"[{score_color}]⭐ {review_result.scores.overall}/10[/{score_color}]")
    table.add_row("Was Improved", "[green]✓ Yes[/green]" if review_result.was_improved else "[dim]✗ No[/dim]")
    
    if image_path:
        table.add_row("Image", "[green]✓ Generated[/green]")
    else:
        table.add_row("Image", "[dim]✗ None[/dim]")
    
    console.print(table)
    console.print("\n")


def run_workflow(user_prompt: str) -> None:
    """Run the complete LinkedIn content creation workflow.
    
    Args:
        user_prompt: Natural language prompt from user.
    """
    # Step 1: Planning
    display_status("Planning...")
    planner = PlannerAgent()
    plan = planner.plan(user_prompt)
    display_execution_plan(plan)
    
    # Step 2: Research (if needed)
    research_results = None
    if plan.requires_search:
        display_status("Researching...")
        research_results = search_web(plan.topic, max_results=5)
    
    # Step 3: Build execution context
    execution_context = {
        "user_prompt": user_prompt,
        "topic": plan.topic,
        "intent": plan.intent,
        "research": research_results or [],
        "writing_style": plan.writing_style
    }
    
    # Regeneration loop
    regeneration_count = 0
    max_regenerations = 5
    
    while True:
        # Step 4: Writing
        display_status("Writing...")
        writer = WriterAgent()
        post = writer.write(
            topic=execution_context["topic"],
            intent=execution_context["intent"],
            user_prompt=execution_context["user_prompt"],
            research=execution_context["research"] if execution_context["research"] else None,
            writing_style=execution_context["writing_style"]
        )
        
        # Step 5: Reviewing
        display_status("Reviewing...")
        reviewer = ReviewerAgent()
        review_result = reviewer.review(post)
        print_review_result(review_result)
        
        # Step 6: Image Prompt Generation
        display_status("Generating image prompt...")
        image_prompt_agent = ImagePromptAgent()
        image_prompt = image_prompt_agent.generate(review_result.final_post)
        print_image_prompt(image_prompt)
        
        # Step 7: Image Generation
        display_status("Generating image...")
        image_path = generate_image(image_prompt)
        
        # Step 8: Display Summary
        display_summary(plan, review_result, image_path)
        
        # Step 9: Preview and Publish
        display_status("Preparing preview...")
        publisher = PublisherAgent()
        
        choice = publisher.preview(
            review_result.final_post, 
            image_path,
            regeneration_count,
            max_regenerations
        )
        
        if choice == "publish":
            # User confirmed publishing
            display_status("Publishing...")
            publisher.publish(review_result.final_post, image_path)
            break
        elif choice == "regenerate":
            # User wants to regenerate
            regeneration_count += 1
            console.print(f"\n[yellow]⚠[/yellow] [dim]Regenerating content... ({regeneration_count}/{max_regenerations})[/dim]\n")
            # Continue loop to regenerate
        elif choice == "edit":
            # User wants to edit
            edit_instruction = get_edit_instruction()
            if edit_instruction:
                # Step 4: Writing with edit instruction
                display_status("Editing...")
                writer = WriterAgent()
                post = writer.write(
                    topic=execution_context["topic"],
                    intent=execution_context["intent"],
                    user_prompt=execution_context["user_prompt"],
                    research=execution_context["research"] if execution_context["research"] else None,
                    writing_style=execution_context["writing_style"],
                    edit_instruction=edit_instruction
                )
                
                # Step 5: Reviewing
                display_status("Reviewing...")
                reviewer = ReviewerAgent()
                review_result = reviewer.review(post)
                print_review_result(review_result)
                
                # Step 6: Image Prompt Generation
                display_status("Generating new image prompt...")
                image_prompt_agent = ImagePromptAgent()
                image_prompt = image_prompt_agent.generate(review_result.final_post)
                print_image_prompt(image_prompt)
                
                # Step 7: Image Generation
                display_status("Generating new image...")
                image_path = generate_image(image_prompt)
                
                # Step 8: Display Summary
                display_summary(plan, review_result, image_path)
                
                # Continue loop to show preview again
            else:
                console.print("\n[yellow]⚠[/yellow] [dim]No edit instruction provided. Returning to preview.[/dim]\n")
        else:
            # User cancelled
            console.print("[dim]Workflow cancelled.[/dim]")
            break


def main() -> None:
    """Main entry point for the LinkedIn Content Agent."""
    # Validate configuration
    if not config.validate():
        console.print("\n")
        console.print(Panel(
            "[red]Configuration Error[/red]\n\n"
            "[dim]GEMINI_API_KEY not found in .env file[/dim]\n\n"
            "[dim]Please create a .env file with your Gemini API key[/dim]\n"
            "[dim]See .env.example for reference[/dim]",
            border_style="red",
            padding=(1, 2)
        ))
        console.print("\n")
        return
    
    # Display welcome
    display_welcome()
    
    # Get user prompt
    user_prompt = get_user_prompt()
    
    if not user_prompt:
        console.print("\n[yellow]⚠[/yellow] [dim]No prompt provided. Exiting.[/dim]\n")
        return
    
    # Run the workflow
    try:
        run_workflow(user_prompt)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠[/yellow] [dim]Interrupted by user.[/dim]\n")
    except Exception as e:
        console.print("\n")
        console.print(Panel(
            f"[red]Error[/red]\n\n[dim]{str(e)}[/dim]\n\n[dim]Please try again or check your configuration.[/dim]",
            border_style="red",
            padding=(1, 2)
        ))
        console.print("\n")
    
    # Completion message
    console.print("\n")
    console.print(Panel(
        "[bold cyan]Thank you for using LinkedIn Content Agent![/bold cyan]",
        border_style="cyan",
        padding=(0, 3)
    ))
    console.print("\n")


if __name__ == "__main__":
    main()
