"""Image Generator Tool for LinkedIn Content Agent.

This module generates AI images using a free provider.
The provider logic is isolated to allow easy replacement in the future.
"""

from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import requests
import urllib.parse
from config.config import config

# Import ImagePrompt locally to avoid circular import
def _get_image_prompt_model():
    from agents.image_prompt import ImagePrompt
    return ImagePrompt


console = Console()


def generate_image(image_prompt: ImagePrompt) -> Optional[Path]:
    """Generate an AI image based on the image prompt.
    
    Args:
        image_prompt: ImagePrompt object containing prompt and filename.
        
    Returns:
        Path to the generated image, or None if generation failed.
    """
    try:
        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
            refresh_per_second=10
        ) as progress:
            task = progress.add_task("[cyan]Generating image...[/cyan]", total=None)
            
            # Generate image using free provider
            image_path = _generate_with_pollinations(image_prompt)
        
        if image_path:
            console.print(f"[green]✓[/green] [dim]Image generated successfully[/dim]")
            console.print(f"[dim]  Saved to:[/dim] [cyan]{image_path}[/cyan]")
            console.print("")
            return image_path
        else:
            console.print("[red]✗[/red] [dim]Image generation failed[/dim]")
            console.print("")
            return None
            
    except Exception as e:
        console.print(f"[red]✗[/red] [dim]Image generation failed:[/dim] [bold]{str(e)}[/bold]")
        console.print("")
        return None


def _generate_with_pollinations(image_prompt: ImagePrompt) -> Optional[Path]:
    """Generate image using Pollinations.ai (free provider).
    
    Args:
        image_prompt: ImagePrompt object containing prompt and filename.
        
    Returns:
        Path to the generated image, or None if generation failed.
    """
    try:
        # Pollinations.ai URL
        base_url = "https://image.pollinations.ai/prompt/"
        
        # Encode the prompt for URL
        encoded_prompt = urllib.parse.quote(image_prompt.prompt)
        
        # Build full URL with parameters
        url = f"{base_url}{encoded_prompt}"
        url += f"?width=1200&height=675&nologo=true&seed={hash(image_prompt.prompt)}"
        
        # Download the image
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # Save to output/images/
        output_path = config.images_dir / image_prompt.filename
        
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        return output_path
        
    except requests.RequestException as e:
        console.print(f"[red]Network error during image generation: {str(e)}[/red]")
        return None
    except IOError as e:
        console.print(f"[red]Failed to save image: {str(e)}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Unexpected error during image generation: {str(e)}[/red]")
        return None


if __name__ == "__main__":
    # Test the Image Generator
    console.print("[bold]Testing Image Generator[/bold]\n")
    
    # Create a hardcoded ImagePrompt
    test_prompt = ImagePrompt(
        prompt="A futuristic digital illustration showing AI agents working together in a clean, modern workspace with abstract technology elements and a professional color palette",
        style="futuristic abstract technology, digital illustration",
        aspect_ratio="16:9",
        filename="test_ai_agents.png"
    )
    
    # Generate image
    result = generate_image(test_prompt)
    
    if result:
        console.print(f"\n[green]Test successful! Image saved to: {result}[/green]")
    else:
        console.print("\n[red]Test failed.[/red]")
