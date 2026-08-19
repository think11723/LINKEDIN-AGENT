"""Research service for LinkedIn Content Agent.

This module provides a unified research service that orchestrates
question generation, search, and result organization.

The search layer is the multi-provider fallback chain in
:mod:`services.search` (SearXNG → Wikipedia → Hacker News Algolia).
A search that returns no results from every provider is reflected
in the returned :class:`ResearchPackage` as ``raw_results=[]``,
``summary=None``, and ``sources=[]`` — the writer can still produce
a draft from its own knowledge, but the persisted draft carries
``research_summary=None`` to make it visible to operators that
no live research backed the post.
"""

from typing import List, Dict, Any
from services.research.models import ResearchPackage
from services.research.planner import ResearchQuestionPlanner
from services.search import search_web
from services.search.errors import SearchUnavailableError
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
            On full chain failure, ``raw_results``, ``summary`` and
            ``sources`` are all empty/None so the workflow layer
            can distinguish "search returned no results" from
            "search was unavailable".
        """
        logger.info(f"Research started for topic: {topic}")

        # Generate research questions
        logger.info("Generating research questions")
        questions = self.question_planner.generate_questions(topic)
        logger.info(f"Generated {len(questions)} research questions")

        # Search for each question
        logger.info("Starting search")
        raw_results: List[Dict[str, str]] = []
        sources: List[str] = []
        search_unavailable = False

        for question in questions:
            try:
                results = search_web(question, max_results=2)
            except SearchUnavailableError as exc:
                # The whole multi-provider chain failed for this
                # question. Stop trying further questions; the
                # downstream layer will see summary=None.
                logger.warning(
                    "Search chain failed for question %r: %s",
                    question, exc,
                )
                search_unavailable = True
                break
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Search failed for question %r: %s",
                    question, e,
                )
                continue
            raw_results.extend(results)
            sources.extend([r.get("url", "") for r in results if r.get("url")])

        logger.info(f"Search completed with {len(raw_results)} results")

        # Build the package. If the chain failed, summary is None
        # so the workflow layer can render a clear "live research
        # unavailable" message to the operator. The writer still
        # receives the post-construction state and can produce a
        # draft from its own knowledge; the persisted draft's
        # ``research_summary`` will be None.
        if search_unavailable:
            logger.info(
                "Research package: search chain unavailable; "
                "continuing with model-knowledge-only draft",
            )
            return ResearchPackage(
                topic=topic,
                questions=questions,
                raw_results=[],
                summary=None,
                sources=[],
            )

        # Create summary
        summary = self._create_summary(raw_results, topic)

        # Create research package
        research_package = ResearchPackage(
            topic=topic,
            questions=questions,
            raw_results=raw_results,
            summary=summary,
            sources=list(set(sources)),  # Deduplicate sources
        )

        logger.info("Research package created successfully")
        return research_package

    def _create_summary(self, results: List[Dict[str, str]], topic: str) -> str:
        """Create a summary from search results.

        Args:
            results: Raw search results.
            topic: Research topic.

        Returns:
            Summary string. Returns ``None`` when there are no
            results so the downstream can distinguish a successful
            zero-result search from a search chain failure.
        """
        if not results:
            # Caller distinguishes: the research node should not
            # fabricate a summary when there were no real results.
            return None

        # Extract snippets from results
        snippets = [r.get("snippet", "") for r in results if r.get("snippet")]

        if not snippets:
            return None

        # Combine snippets into a brief summary
        combined = " ".join(snippets[:3])  # Use first 3 snippets
        if len(combined) > 300:
            combined = combined[:300] + "..."

        return f"Research summary for {topic}: {combined}"
