"""Publisher Agent for LinkedIn Content Agent.

This agent handles the final publishing workflow, displaying the preview
and managing user confirmation for publishing.
"""

from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from utils.models import LinkedInPost
from utils.config import config


console = Console()


class PublisherAgent:
    """Agent that manages the publishing workflow."""
    
    def __init__(self) -> None:
        """Initialize the Publisher Agent."""
        pass
    
    def preview(
        self,
        post: LinkedInPost,
        image_path: Optional[Path] = None,
        regeneration_count: int = 0,
        max_regenerations: int = 5
    ) -> str:
        """Display preview and ask for publishing confirmation.
        
        Args:
            post: LinkedInPost to publish.
            image_path: Optional path to generated image.
            regeneration_count: Current regeneration count.
            max_regenerations: Maximum allowed regenerations.
            
        Returns:
            str: User choice - 'publish', 'regenerate', 'edit', or 'cancel'.
        """
        self._display_preview(post, image_path)
        
        # Ask for confirmation
        console.print("\n[bold]Do you want to publish this?[/bold]\n")
        console.print("[cyan][Y][/cyan] Publish")
        
        # Show regenerate option if under limit
        if regeneration_count < max_regenerations:
            console.print(f"[cyan][R][/cyan] Regenerate [dim]({regeneration_count}/{max_regenerations})[/dim]")
        else:
            console.print(f"[dim][R] Regenerate (limit reached)[/dim]")
        
        console.print("[cyan][E][/cyan] Edit")
        console.print("[cyan][N][/cyan] Cancel\n")
        
        choice = console.input("[bold cyan]➜ [/bold cyan]").strip().upper()
        
        if choice == "Y":
            return "publish"
        elif choice == "R" and regeneration_count < max_regenerations:
            return "regenerate"
        elif choice == "E":
            return "edit"
        elif choice == "R":
            console.print("\n[yellow]⚠[/yellow] [dim]Regeneration limit reached.[/dim]\n")
            return "cancel"
        else:
            console.print("\n[dim]✓ Cancelled.[/dim]\n")
            return "cancel"
    
    def publish(self, post: LinkedInPost, image_path: Optional[Path] = None) -> None:
        """Publish the LinkedIn post.
        
        For V1, this saves the post for manual publishing.
        In future versions, this will integrate with LinkedIn API.
        
        Args:
            post: LinkedInPost to publish.
            image_path: Optional path to generated image.
        """
        # Check if LinkedIn API is configured
        if not self._is_linkedin_configured():
            self._save_for_manual_publishing(post, image_path)
        else:
            self._publish_via_api(post, image_path)
    
    def _is_linkedin_configured(self) -> bool:
        """Check if LinkedIn API credentials are configured.
        
        Returns:
            bool: True if LinkedIn API is configured, False otherwise.
        """
        return bool(
            config.linkedin_access_token and
            config.linkedin_client_id and
            config.linkedin_client_secret
        )
    
    def _save_for_manual_publishing(
        self,
        post: LinkedInPost,
        image_path: Optional[Path]
    ) -> None:
        """Save post for manual LinkedIn publishing.
        
        Args:
            post: LinkedInPost to save.
            image_path: Optional path to generated image.
        """
        # Save as markdown
        save_markdown(post)
        
        # If image exists, mention it
        if image_path and image_path.exists():
            console.print(f"\n[green]✓[/green] [dim]Image saved to:[/dim] [cyan]{image_path}[/cyan]")
        
        console.print("\n")
        console.print(Panel(
            "[bold green]✓ Ready for manual LinkedIn posting[/bold green]",
            border_style="green",
            padding=(0, 2)
        ))
        console.print(f"[dim]Post saved to: {config.output_dir / 'latest_post.md'}[/dim]")
        console.print("\n")
    
    def _publish_via_api(
        self,
        post: LinkedInPost,
        image_path: Optional[Path]
    ) -> None:
        """Publish via LinkedIn API (placeholder for future implementation).
        
        Args:
            post: LinkedInPost to publish.
            image_path: Optional path to generated image.
        """
        console.print("[yellow]LinkedIn API publishing coming soon![/yellow]")
        console.print("[dim]Falling back to manual publishing...[/dim]")
        self._save_for_manual_publishing(post, image_path)
    
    def _display_preview(
        self,
        post: LinkedInPost,
        image_path: Optional[Path]
    ) -> None:
        """Display a beautiful preview of the post.
        
        Args:
            post: LinkedInPost to display.
            image_path: Optional path to generated image.
        """
        console.print("\n")
        
        # Header
        console.print(Panel(
            "[bold cyan]LinkedIn Post Preview[/bold cyan]",
            border_style="cyan",
            padding=(0, 2)
        ))
        
        # Post content
        console.print(f"\n[bold]{post.title}[/bold]")
        console.print(f"{post.content}\n")
        
        # Hashtags
        console.print(f"[dim]{', '.join(post.hashtags)}[/dim]\n")
        
        # Image info
        if image_path and image_path.exists():
            console.print(Panel(
                f"[green]✓ Image generated[/green]\n[dim]Path: {image_path}[/dim]",
                title="[bold]Image[/bold]",
                border_style="green",
                padding=(0, 2)
            ))
        else:
            console.print(Panel(
                "[dim]✗ No image generated[/dim]",
                title="[bold]Image[/bold]",
                border_style="dim",
                padding=(0, 2)
            ))


if __name__ == "__main__":
    # Test the Publisher Agent
    console.print("[bold]Testing Publisher Agent[/bold]\n")
    
    # Create sample LinkedInPost
    sample_post = LinkedInPost(
        title="The Future of AI Agents",
        content="AI agents are transforming how we work. From automating repetitive tasks to providing intelligent assistance, these systems are becoming indispensable. The future looks promising with more sophisticated agents emerging.",
        hashtags=["#AI", "#Agents", "#Technology", "#Future"]
    )
    
    # Test preview
    publisher = PublisherAgent()
    publisher.preview(sample_post)
