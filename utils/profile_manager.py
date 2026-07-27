"""Profile Manager for LinkedIn Content Agent.

This module handles loading, saving, and validating user profiles.
It also generates concise profile summaries for AI agents.
"""

import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from models.profile_models import Profile

console = Console()


PROFILE_PATH = Path(__file__).parent.parent / "database" / "profile.json"
TEMPLATE_PATH = Path(__file__).parent.parent / "database" / "profile.template.json"


def load_profile() -> Optional[Profile]:
    """Load user profile from profile.json.
    
    Returns:
        Profile object if file exists and is valid, None otherwise.
    """
    if not PROFILE_PATH.exists():
        return None
    
    try:
        with open(PROFILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        profile = Profile(**data)
        return profile
        
    except Exception as e:
        console.print(f"[yellow]⚠[/yellow] [dim]Failed to load profile: {str(e)}[/dim]")
        return None


def save_profile(profile: Profile) -> bool:
    """Save user profile to profile.json.
    
    Args:
        profile: Profile object to save.
        
    Returns:
        True if save was successful, False otherwise.
    """
    try:
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(profile.model_dump(mode='json'), f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✓[/green] [dim]Profile saved to:[/dim] [cyan]{PROFILE_PATH}[/cyan]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] [dim]Failed to save profile: {str(e)}[/dim]")
        return False


def validate_profile(data: dict) -> tuple[bool, str]:
    """Validate profile data structure.
    
    Args:
        data: Dictionary containing profile data.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    try:
        Profile(**data)
        return True, ""
    except Exception as e:
        return False, str(e)


def get_profile_summary(profile: Profile) -> str:
    """Generate a concise profile summary for AI agents.
    
    This creates a natural language summary that captures the essential
    information about the user without overwhelming the AI with details.
    
    Args:
        profile: Profile object to summarize.
        
    Returns:
        Concise profile summary string.
    """
    # Build summary components
    components = []
    
    # Basic info
    basic = profile.basic_info
    if basic.current_role and basic.organisation:
        components.append(f"{basic.preferred_name} is a {basic.current_role} at {basic.organisation}")
    else:
        components.append(f"{basic.preferred_name} is a {basic.current_role or 'professional'}")
    
    # Current learning
    if profile.professional_summary.current_learning:
        components.append(f"currently learning {profile.professional_summary.current_learning}")
    
    # Experience
    if profile.experience:
        exp_count = len(profile.experience)
        components.append(f"with {exp_count} year{'s' if exp_count > 1 else ''} of experience")
    
    # Key skills (top 3-5)
    all_skills = (
        profile.skills.technical_skills[:3] +
        profile.skills.frameworks[:2] +
        profile.skills.ai_stack[:2]
    )
    if all_skills:
        skills_str = ", ".join(all_skills[:5])
        components.append(f"skilled in {skills_str}")
    
    # Projects
    if profile.projects:
        project_count = len(profile.projects)
        components.append(f"having built {project_count} project{'s' if project_count > 1 else ''}")
    
    # Writing style
    writing = profile.writing_preferences
    components.append(f"with a {writing.preferred_tone} writing style")
    
    # Target audience and niche
    branding = profile.personal_branding
    if branding.target_audience and branding.niche:
        components.append(f"targeting {branding.target_audience} interested in {branding.niche}")
    
    # Combine into natural summary
    summary = ". ".join(components) + "."
    
    return summary


def profile_exists() -> bool:
    """Check if profile.json exists.
    
    Returns:
        True if profile.json exists, False otherwise.
    """
    return PROFILE_PATH.exists()


def create_profile_from_template() -> bool:
    """Create profile.json from template.
    
    Returns:
        True if successful, False otherwise.
    """
    if not TEMPLATE_PATH.exists():
        console.print(f"[red]✗[/red] [dim]Template not found: {TEMPLATE_PATH}[/dim]")
        return False
    
    try:
        with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
        
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with open(PROFILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=2, ensure_ascii=False)
        
        console.print(f"[green]✓[/green] [dim]Profile created from template:[/dim] [cyan]{PROFILE_PATH}[/dim]")
        console.print("[yellow]⚠[/yellow] [dim]Please edit profile.json with your actual information.[/dim]")
        return True
        
    except Exception as e:
        console.print(f"[red]✗[/red] [dim]Failed to create profile from template: {str(e)}[/dim]")
        return False


if __name__ == "__main__":
    # Test profile manager
    console.print("[bold]Testing Profile Manager[/bold]\n")
    
    # Check if profile exists
    if profile_exists():
        console.print("[green]✓[/green] [dim]Profile exists[/dim]\n")
        
        # Load profile
        profile = load_profile()
        if profile:
            console.print("[green]✓[/green] [dim]Profile loaded successfully[/dim]\n")
            
            # Generate summary
            summary = get_profile_summary(profile)
            console.print("[bold]Profile Summary:[/bold]")
            console.print(f"{summary}\n")
        else:
            console.print("[red]✗[/red] [dim]Failed to load profile[/dim]\n")
    else:
        console.print("[yellow]⚠[/yellow] [dim]No profile found[/dim]\n")
        console.print("[dim]Run: python -m utils.profile_manager --create-template[/dim]\n")
