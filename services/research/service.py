"""Research service for LinkedIn Content Agent.

This module provides a unified research service that orchestrates
question generation, search, and result organization.
"""

from typing import List, Dict
from services.research.models import ResearchPackage
from services.research.planner import ResearchQuestionPlanner
from services.search import search_web
from utils.logger import logger


class ResearchService:
    """Service for conducting research on topics."""
    
    def __init__(self) -> None:
        """Initialize the Research Service."""
        self.question_planner = ResearchQuestionPlanner()
    
    def research(self, topic: str) -> ResearchPackage:
        """Conduct research on a given topic.
        
        Args:
            topic: Topic to research.
            
        Returns:
            ResearchPackage with questions, results, and summary.
        """
        logger.info(f"Research started for topic: {topic}")
        
        try:
            # Generate research questions
            logger.info("Generating research questions")
            questions = self.question_planner.generate_questions(topic)
            logger.info(f"Generated {len(questions)} research questions")
            
            # Search for each question
            logger.info("Starting search")
            raw_results = []
            sources = []
            
            for question in questions:
                try:
                    results = search_web(question, max_results=2)
                    raw_results.extend(results)
                    sources.extend([r.get("url", "") for r in results if r.get("url")])
                except Exception as e:
                    logger.warning(f"Search failed for question '{question}': {str(e)}")
                    continue
            
            logger.info(f"Search completed with {len(raw_results)} results")
            
            # Create summary
            summary = self._create_summary(raw_results, topic)
            
            # Create research package
            research_package = ResearchPackage(
                topic=topic,
                questions=questions,
                raw_results=raw_results,
                summary=summary,
                sources=list(set(sources))  # Deduplicate sources
            )
            
            logger.info("Research package created successfully")
            return research_package
            
        except Exception as e:
            logger.error(f"Research failed: {str(e)}")
            # Return empty package on failure
            return ResearchPackage(
                topic=topic,
                questions=[],
                raw_results=[],
                summary=None,
                sources=[]
            )
    
    def _create_summary(self, results: List[Dict[str, str]], topic: str) -> str:
        """Create a summary from search results.
        
        Args:
            results: Raw search results.
            topic: Research topic.
            
        Returns:
            Summary string.
        """
        if not results:
            return f"No research results found for {topic}."
        
        # Extract snippets from results
        snippets = [r.get("snippet", "") for r in results if r.get("snippet")]
        
        if not snippets:
            return f"Search completed but no content available for {topic}."
        
        # Combine snippets into a brief summary
        combined = " ".join(snippets[:3])  # Use first 3 snippets
        if len(combined) > 300:
            combined = combined[:300] + "..."
        
        return f"Research summary for {topic}: {combined}"
