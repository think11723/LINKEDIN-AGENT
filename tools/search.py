"""Search Tool for LinkedIn Content Agent.

This module provides web search functionality using DuckDuckGo Search.
It returns clean, structured search results with error handling.
"""

from typing import List, Dict, Any
from duckduckgo_search import DDGS
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn


console = Console()


def search_web(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Perform a web search using DuckDuckGo.
    
    Args:
        query: Search query string.
        max_results: Maximum number of results to return (default: 5).
        
    Returns:
        List of dictionaries containing 'title', 'url', and 'snippet'.
        Returns empty list if search fails or no results found.
    """
    try:
        with Progress(
            SpinnerColumn("dots"),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
            refresh_per_second=10
        ) as progress:
            task = progress.add_task("[cyan]Searching the web...[/cyan]", total=None)
            
            # Perform search
            ddgs = DDGS()
            results = list(ddgs.text(query, max_results=max_results * 2))  # Get more for filtering
        
        # Clean and filter results
        cleaned_results = _clean_results(results)
        
        # Limit to max_results
        final_results = cleaned_results[:max_results]
        
        if final_results:
            console.print(f"[green]✓[/green] [dim]Found[/dim] [bold]{len(final_results)}[/bold] [dim]relevant results[/dim]")
        else:
            console.print("[yellow]⚠[/yellow] [dim]No results found[/dim]")
        
        console.print("")
        return final_results
        
    except Exception as e:
        console.print(f"[red]✗[/red] [dim]Search failed:[/dim] [bold]{str(e)}[/bold]")
        console.print("")
        return []


def _clean_results(results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Clean and filter search results.
    
    Args:
        results: Raw search results from DuckDuckGo.
        
    Returns:
        Cleaned list of results with duplicates, empty snippets, and malformed URLs removed.
    """
    cleaned = []
    seen_urls = set()
    
    for result in results:
        # Skip if missing required fields
        if not all(key in result for key in ['title', 'url', 'body']):
            continue
        
        # Skip empty snippets
        if not result.get('body') or not result['body'].strip():
            continue
        
        # Skip malformed URLs
        url = result.get('url', '')
        if not url or not url.startswith(('http://', 'https://')):
            continue
        
        # Skip duplicates
        if url in seen_urls:
            continue
        
        seen_urls.add(url)
        
        # Add cleaned result
        cleaned.append({
            'title': result['title'],
            'url': url,
            'snippet': result['body']
        })
    
    return cleaned


if __name__ == "__main__":
    # Test the search tool
    console.print("[bold]Testing Search Tool[/bold]\n")
    
    test_query = "AI Agents 2026"
    results = search_web(test_query, max_results=5)
    
    console.print(f"\n[bold]Search Results ({len(results)}):[/bold]\n")
    for i, result in enumerate(results, 1):
        console.print(f"[bold cyan]{i}.[/bold cyan] [bold]{result['title']}[/bold]")
        console.print(f"   [dim]{result['url']}[/dim]")
        console.print(f"   {result['snippet'][:150]}...\n")
