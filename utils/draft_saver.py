"""Draft saver utility for LinkedIn Content Agent.

This module handles saving generated drafts to JSON files.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from utils.logger import logger


DRAFTS_DIR = Path(__file__).parent.parent / "output" / "drafts"


def save_draft(result: Any) -> str:
    """Save a workflow result as a JSON draft file.
    
    Args:
        result: WorkflowResult from ContentWorkflow.
        
    Returns:
        Path to the saved draft file.
    """
    # Ensure drafts directory exists
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamp filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.json"
    filepath = DRAFTS_DIR / filename
    
    # Prepare draft data
    draft_data = {
        "timestamp": datetime.now().isoformat(),
        "topic": result.topic,
        "post": {
            "title": result.final_post.title if result.final_post else None,
            "content": result.final_post.content if result.final_post else None,
            "hashtags": result.final_post.hashtags if result.final_post else []
        },
        "metrics": {
            "approved": result.approved,
            "iterations": result.iterations,
            "review_score": result.review_scores.overall if result.review_scores else None,
            "review_feedback": result.review_feedback
        },
        "research": {
            "summary": result.metadata.get("research_package").summary if result.metadata.get("research_package") else None,
            "questions": result.metadata.get("research_package").questions if result.metadata.get("research_package") else []
        } if result.metadata.get("research_package") else None
    }
    
    # Save to file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(draft_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Draft saved to {filepath}")
        return str(filepath)
        
    except Exception as e:
        logger.error(f"Failed to save draft: {str(e)}")
        raise
