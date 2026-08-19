"""LinkedIn Content Agent - CLI Application Runner.

This is the main entry point for generating LinkedIn content.
"""

import sys
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from workflows.content_workflow import ContentWorkflow
from utils.draft_saver import save_draft
from utils.logger import logger
from services.linkedin import LinkedInService

console = Console()


def validate_image_path(image_path: str) -> tuple[bool, str]:
    """Validate an image file path.
    
    Args:
        image_path: Path to the image file.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    if not image_path:
        return True, ""
    
    # Check if file exists
    path = Path(image_path)
    if not path.exists():
        return False, f"File not found: {image_path}"
    
    # Check file extension
    valid_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    if path.suffix.lower() not in valid_extensions:
        return False, f"Invalid image format. Supported: PNG, JPG, JPEG, WEBP"
    
    # Check if it's a file (not directory)
    if not path.is_file():
        return False, f"Path is not a file: {image_path}"
    
    return True, ""


def display_welcome():
    """Display welcome message."""
    welcome_text = """
╔════════════════════════════════════════════════════════════╗
║          AI LinkedIn Content Agent - CLI Runner            ║
╚════════════════════════════════════════════════════════════╝

Generate professional LinkedIn posts using AI.
"""
    console.print(Panel(welcome_text.strip(), title="Welcome", border_style="blue"))


def display_result(result):
    """Display the workflow result.
    
    Args:
        result: WorkflowResult from ContentWorkflow.
    """
    console.print("\n[bold blue]═══ Generated LinkedIn Post ═══[/bold blue]\n")
    
    # Title
    console.print(f"[bold yellow]Title:[/bold yellow] {result.final_post.title}")
    
    # Content
    console.print(f"\n[bold yellow]Content:[/bold yellow]")
    console.print(result.final_post.content)
    
    # Hashtags
    console.print(f"\n[bold yellow]Hashtags:[/bold yellow] {' '.join(result.final_post.hashtags)}")
    
    # Image
    image_path = getattr(result.final_post, 'image_path', None)
    if image_path:
        console.print(f"\n[bold yellow]Image:[/bold yellow] {image_path}")
    else:
        console.print(f"\n[dim]Image: None (text-only post)[/dim]")
    
    # Research summary
    research_package = result.metadata.get("research_package")
    if research_package:
        console.print(f"\n[bold cyan]Research Summary:[/bold cyan] {research_package.summary}")
    
    # Metrics
    console.print(f"\n[bold green]═══ Metrics ═══[/bold green]")
    console.print(f"Approval Status: {'✅ Approved' if result.approved else '❌ Not Approved'}")
    console.print(f"Iterations: {result.iterations}")
    
    if result.review_scores:
        console.print(f"Review Score: {result.review_scores.overall}/10")
    
    if result.review_feedback:
        console.print(f"Feedback: {result.review_feedback}")


def edit_draft(result):
    """Allow user to edit the draft.
    
    Args:
        result: WorkflowResult with the draft to edit.
        
    Returns:
        Updated WorkflowResult with edited content.
    """
    console.print("\n[bold cyan]═══ Edit Draft ═══[/bold cyan]")
    console.print("[dim]Current content will be displayed. Edit the fields you want to change.[/dim]\n")
    
    # Edit title
    console.print(f"[bold yellow]Current Title:[/bold yellow] {result.final_post.title}")
    new_title = Prompt.ask("[bold cyan]Enter new title (or press Enter to keep current)[/bold cyan]", default=result.final_post.title)
    
    # Edit content
    console.print(f"\n[bold yellow]Current Content:[/bold yellow]")
    console.print(result.final_post.content)
    console.print()
    new_content = Prompt.ask("[bold cyan]Enter new content (or press Enter to keep current)[/bold cyan]", default=result.final_post.content)
    
    # Edit hashtags
    console.print(f"\n[bold yellow]Current Hashtags:[/bold yellow] {' '.join(result.final_post.hashtags)}")
    new_hashtags_str = Prompt.ask("[bold cyan]Enter new hashtags (space-separated, or press Enter to keep current)[/bold cyan]", default=' '.join(result.final_post.hashtags))
    new_hashtags = new_hashtags_str.split() if new_hashtags_str else result.final_post.hashtags
    
    # Update the result
    result.final_post.title = new_title
    result.final_post.content = new_content
    result.final_post.hashtags = new_hashtags
    
    logger.info("Draft edited")
    console.print("\n[green]✓ Draft updated successfully[/green]")
    
    return result


def regenerate_post(topic):
    """Regenerate the post for the same topic.
    
    Args:
        topic: Original topic.
        
    Returns:
        New WorkflowResult.
    """
    logger.info("Draft regenerated")
    console.print(f"\n[bold]Regenerating content for:[/bold] {topic}")
    
    workflow = ContentWorkflow()
    # ``ContentWorkflow.run`` is async now (the underlying graph
    # contains async nodes). The legacy CLI runs in a sync
    # context; use ``asyncio.run`` at this outermost CLI
    # boundary (not inside application/library code).
    import asyncio
    result = asyncio.run(workflow.run(topic))
    
    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")
        return None
    
    return result


def publish_draft(result):
    """Publish the current draft to LinkedIn.
    
    Args:
        result: WorkflowResult with the draft to publish.
    """
    if not result.approved:
        console.print("[yellow]Cannot publish: Post is not approved by reviewer[/yellow]")
        return False
    
    # Check if approval request was created and email sent
    draft_id = result.metadata.get("draft_id") if result.metadata else None
    if not draft_id:
        console.print("[yellow]Cannot publish: No approval request was created[/yellow]")
        console.print("[dim]Please regenerate the post to create an approval request.[/dim]")
        return False
    
    # Check approval status from approval service
    from approval.service import ApprovalService
    from approval.store import ApprovalStore
    
    approval_service = ApprovalService()
    approval_store = ApprovalStore()
    
    # Get the draft to check approval status
    draft = approval_store.get_draft(draft_id)
    if not draft:
        console.print("[yellow]Cannot publish: Draft not found in approval system[/yellow]")
        return False
    
    # Check if draft has been approved
    approval_token = approval_store.get_token_by_draft_id(draft_id)
    if not approval_token:
        console.print("[yellow]Cannot publish: No approval token found[/yellow]")
        console.print("[dim]Please approve the draft via the approval email before publishing.[/dim]")
        return False
    
    if not approval_token.is_approved():
        console.print("[yellow]Cannot publish: Post is not approved[/yellow]")
        console.print(f"[dim]Current status: {approval_token.status.value if approval_token.status else 'Unknown'}[/dim]")
        console.print("[dim]Please approve the draft via the approval email before publishing.[/dim]")
        return False
    
    console.print("\n[bold cyan]═══ Publish to LinkedIn ═══[/bold cyan]")
    
    # Check for image
    image_path = getattr(result.final_post, 'image_path', None)
    if image_path:
        console.print(f"[dim]Image attached: {image_path}[/dim]")
        # Validate image before publishing
        is_valid, error_message = validate_image_path(image_path)
        if not is_valid:
            console.print(f"[red]{error_message}[/red]")
            console.print("[yellow]Would you like to publish without the image?[/yellow]")
            continue_choice = Prompt.ask("[bold cyan]Continue without image?[/bold cyan]", choices=["y", "n"], default="n")
            if continue_choice == "n":
                return False
            image_path = None
    else:
        console.print("[dim]No image attached (text-only post)[/dim]")
    
    linkedin_service = LinkedInService()
    if linkedin_service.authenticate():
        publish_result = linkedin_service.publish_post(
            result.final_post.title,
            result.final_post.content,
            result.final_post.hashtags,
            image_path,
            approval_status=approval_token.status.value,
            approval_token=approval_token.token
        )
        if "error" in publish_result:
            console.print(f"[red]Publishing failed: {publish_result['error']}[/red]")
            logger.error(f"Publishing failed: {publish_result['error']}")
            return False
        else:
            console.print("[green]✓ Successfully published to LinkedIn[/green]")
            logger.info("Draft published")
            return True
    else:
        console.print("[red]Authentication failed. Please check your LinkedIn credentials.[/red]")
        return False


def attach_image(result):
    """Attach an image to the current draft.
    
    Args:
        result: WorkflowResult with the draft to attach image to.
    """
    console.print("\n[bold cyan]═══ Attach Image ═══[/bold cyan]")
    
    # Check if draft already has an image
    current_image = getattr(result.final_post, 'image_path', None)
    if current_image:
        console.print(f"[dim]Current image: {current_image}[/dim]")
        remove_choice = Prompt.ask("[bold cyan]Remove current image?[/bold cyan]", choices=["y", "n"], default="n")
        if remove_choice == "y":
            result.final_post.image_path = None
            console.print("[green]✓ Image removed[/green]")
            return result
    
    # Ask for image path
    image_path = Prompt.ask("[bold cyan]Enter image path (or press Enter to cancel)[/bold cyan]", default="")
    
    if not image_path.strip():
        console.print("[dim]No image attached[/dim]")
        return result
    
    # Validate image path
    is_valid, error_message = validate_image_path(image_path)
    if not is_valid:
        console.print(f"[red]{error_message}[/red]")
        return result
    
    # Attach image
    result.final_post.image_path = image_path
    console.print(f"[green]✓ Image attached: {image_path}[/green]")
    logger.info(f"Image attached: {image_path}")
    
    return result


def schedule_draft(result):
    """Schedule the current draft for future publication.
    
    Args:
        result: WorkflowResult with the draft to schedule.
    """
    if not result.approved:
        console.print("[yellow]Cannot schedule: Post is not approved by reviewer[/yellow]")
        return False
    
    console.print("\n[bold cyan]═══ Schedule Publish ═══[/bold cyan]")
    
    # Ask for scheduling option
    schedule_option = Prompt.ask(
        "[bold cyan]Schedule option[/bold cyan]",
        choices=["minutes", "hours", "specific"],
        default="hours"
    )
    
    try:
        from scheduler.service import SchedulerService
        scheduler_service = SchedulerService()
        
        if schedule_option == "minutes":
            minutes = Prompt.ask("[bold cyan]Minutes from now[/bold cyan]", default="30")
            minutes = int(minutes)
            job_id = scheduler_service.schedule_post_in_minutes(
                result.final_post.title,
                result.final_post.content,
                result.final_post.hashtags,
                minutes,
                getattr(result.final_post, 'image_path', None)
            )
            console.print(f"[green]✓ Post scheduled for {minutes} minutes from now[/green]")
            console.print(f"[dim]Job ID: {job_id}[/dim]")
            
        elif schedule_option == "hours":
            hours = Prompt.ask("[bold cyan]Hours from now[/bold cyan]", default="2")
            hours = int(hours)
            job_id = scheduler_service.schedule_post_in_hours(
                result.final_post.title,
                result.final_post.content,
                result.final_post.hashtags,
                hours,
                getattr(result.final_post, 'image_path', None)
            )
            console.print(f"[green]✓ Post scheduled for {hours} hours from now[/green]")
            console.print(f"[dim]Job ID: {job_id}[/dim]")
            
        else:  # specific time
            console.print("[dim]Enter date and time in format: YYYY-MM-DD HH:MM[/dim]")
            console.print("[dim]Example: 2026-07-28 14:30[/dim]")
            datetime_str = Prompt.ask("[bold cyan]Scheduled time (UTC)[/bold cyan]")
            
            from datetime import datetime
            scheduled_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            
            job_id = scheduler_service.schedule_post(
                result.final_post.title,
                result.final_post.content,
                result.final_post.hashtags,
                scheduled_time,
                getattr(result.final_post, 'image_path', None)
            )
            console.print(f"[green]✓ Post scheduled for {scheduled_time}[/green]")
            console.print(f"[dim]Job ID: {job_id}[/dim]")
        
        logger.info(f"Post scheduled with job ID: {job_id}")
        console.print("\n[dim]Note: The scheduler runner must be running to execute scheduled jobs.[/dim]")
        console.print("[dim]Run: python -m scheduler.runner[/dim]")
        return True
        
    except Exception as e:
        console.print(f"[red]Failed to schedule post: {str(e)}[/red]")
        logger.error(f"Failed to schedule post: {str(e)}")
        return False


def display_menu():
    """Display user choice menu."""
    console.print("\n[bold blue]═══ Options ═══[/bold blue]")
    console.print("1. Regenerate Post")
    console.print("2. Edit Draft")
    console.print("3. Save Draft")
    console.print("4. Attach Image")
    console.print("5. Publish to LinkedIn")
    console.print("6. Schedule Publish")
    console.print("7. Exit")


def main():
    """Main application runner."""
    try:
        display_welcome()
        
        while True:
            # Get topic from user
            topic = Prompt.ask("\n[bold cyan]Enter your LinkedIn topic[/bold cyan]", default="")
            
            if not topic.strip():
                console.print("[yellow]Topic cannot be empty. Please try again.[/yellow]")
                continue
            
            console.print(f"\n[bold]Generating content for:[/bold] {topic}")
            
            try:
                # Run workflow
                result = regenerate_post(topic)
                
                if result is None:
                    continue
                
                # Display result
                display_result(result)
                
                # Menu loop
                while True:
                    display_menu()
                    choice = Prompt.ask("\n[bold cyan]Choose an option[/bold cyan]", choices=["1", "2", "3", "4", "5", "6", "7"], default="7")
                    
                    if choice == "1":
                        # Regenerate Post
                        result = regenerate_post(topic)
                        if result is None:
                            break
                        display_result(result)
                    elif choice == "2":
                        # Edit Draft
                        result = edit_draft(result)
                        display_result(result)
                    elif choice == "3":
                        # Save Draft
                        try:
                            draft_path = save_draft(result)
                            console.print(f"[green]Draft saved to: {draft_path}[/green]")
                            logger.info(f"Draft saved to: {draft_path}")
                        except Exception as e:
                            console.print(f"[red]Failed to save draft: {str(e)}[/red]")
                            logger.error(f"Failed to save draft: {str(e)}")
                    elif choice == "4":
                        # Attach Image
                        result = attach_image(result)
                        display_result(result)
                    elif choice == "5":
                        # Publish to LinkedIn
                        publish_draft(result)
                    elif choice == "6":
                        # Schedule Publish
                        schedule_draft(result)
                    else:
                        # Exit
                        break
                
                # Ask if user wants to continue with new topic
                continue_choice = Prompt.ask("\n[bold cyan]Do you want to create another post?[/bold cyan]", choices=["y", "n"], default="n")
                if continue_choice == "n":
                    break
                    
            except Exception as e:
                console.print(f"[red]An error occurred: {str(e)}[/red]")
                logger.error(f"Workflow error: {str(e)}")
                continue
        
        console.print("\n[bold green]Thank you for using LinkedIn Content Agent![/bold green]")
        
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Fatal error: {str(e)}[/red]")
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
