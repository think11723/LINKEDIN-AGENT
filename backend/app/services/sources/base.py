"""Base source adapter and ``SourcePackage`` contract.

The URL-to-LinkedIn feature accepts arbitrary user-supplied URLs and
produces a structured payload that is fed directly into the existing
``WriterAgent`` / ``ReviewerAgent`` pipeline. The payload shape — the
``SourcePackage`` — is defined here so every adapter implements the same
interface and the existing writer contract
(``agents/writer.py:259-262``) consumes ``raw_results[0..2]`` unchanged.

Adapter responsibility:

1. Detect (``can_handle``): cheap, sync, **no network**. Pure host/path
   matching against the URL string.
2. Fetch (``fetch``): async, network. Returns a :class:`SourcePackage`
   populated from the underlying source. Raises one of the
   :class:`SourceFetchError` subclasses on failure.
3. Project (``to_research_package``): adapter-agnostic default in the
   base class — turns :class:`SourcePackage` into the project's existing
   :class:`services.research.models.ResearchPackage` so the writer's
   contract holds byte-identically. Subclasses rarely override.

The error hierarchy is rooted at :class:`SourceFetchError` (carries a
machine-readable ``code`` and a user-safe ``message``). The router layer
maps these to HTTP envelopes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    from services.research.models import ResearchPackage


class SourcePackage(BaseModel):
    """Adapter output. Shaped so it slots directly into ``ResearchPackage``.

    The contract for ``raw_results`` is documented in
    ``workflows/graph_workflow.py:_writer_node`` and ``agents/writer.py:259-262``
    — the writer consumes the first three entries only.
    """

    title: str
    summary: str
    key_facts: List[str] = Field(default_factory=list)
    raw_results: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def empty(cls, *, url: str, adapter: str, error_code: str) -> "SourcePackage":
        """Build a placeholder package for failure paths.

        Used by the runner when an adapter fails after the URL has been
        validated but before the analysis step completes. Never written
        to Mongo — the runner turns a failed adapter into a
        ``failed`` job instead.
        """
        return cls(
            title="",
            summary="",
            key_facts=[],
            raw_results=[],
            metadata={
                "url": url,
                "adapter": adapter,
                "error_code": error_code,
            },
        )


class SourceFetchError(Exception):
    """Base for all source-adapter failures.

    Carries a stable ``code`` (machine) and a user-safe ``message``.
    Subclasses exist purely so callers / audit can discriminate without
    parsing the code string.
    """

    def __init__(self, message: str, *, code: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class SourceBlockedError(SourceFetchError):
    """The URL or its resolution is rejected by the SSRF guard.

    Codes: ``private_ip``, ``loopback``, ``link_local``, ``multicast``,
    ``reserved``, ``bad_scheme``, ``userinfo``, ``bad_port``,
    ``redirect_to_private``, ``too_many_redirects``, ``not_allowlisted``,
    ``binary_content``, ``dmca``.
    """

    pass


class SourceTooLargeError(SourceFetchError):
    """The response, the stripped HTML, or the GitHub cumulative fetch exceeded its cap.

    Codes: ``response_too_large``, ``html_too_large``,
    ``github_cumulative_too_large``.
    """

    pass


class SourceUnavailableError(SourceFetchError):
    """The source could not be fetched for non-Security, non-Size reasons.

    Codes: ``repository_not_found``, ``github_rate_limited``,
    ``tls_invalid``, ``paywall``, ``thin_content``, ``binary_content_pdf``,
    ``not_html``, ``timeout``, ``http_5xx``, ``http_4xx_unexpected``,
    ``content_unavailable_or_paywalled``.
    """

    pass


class BaseSourceAdapter(ABC):
    """Adapter contract.

    Concrete adapters subclass this, declare a unique ``name``, and
    implement :meth:`can_handle` (sync, no network) and :meth:`fetch`
    (async, network). The :meth:`to_research_package` projection has a
    sensible default — adapters rarely override.
    """

    #: Stable lowercase identifier (``"github"``, ``"webpage"``, ``"stub"``).
    name: str = ""

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool:
        """Cheap, sync, no network. Pure host/path matching."""

    @abstractmethod
    async def fetch(self, url: str, *, request_id: str) -> SourcePackage:
        """Fetch + normalize + analyze. Raises :class:`SourceFetchError` subclasses."""

    def to_research_package(self, package: SourcePackage) -> "ResearchPackage":
        """Project a :class:`SourcePackage` into the project's existing
        :class:`ResearchPackage` so the writer's contract holds.

        Writer reads the first three ``raw_results`` entries. Adapters
        should populate ``raw_results`` as:
          * ``[0]`` — overview / summary snippet (``title``, ``url``, ``snippet=summary``)
          * ``[1]`` — key facts joined (``title="key facts"``, ``url``, ``snippet="• f1 • f2 • f3"``)
          * ``[2]`` — most important detail block (typically the README
            first paragraph or the article's first substantive paragraph)
        Any entries beyond are best-effort context.
        """
        # Local import keeps the package import-surface flat — adapters
        # do not need to know about services.research at module scope.
        from services.research.models import ResearchPackage

        summary = package.summary or package.title or ""
        facts_block = "\n".join(f"• {fact}" for fact in package.key_facts)
        raw_results: List[Dict[str, str]] = list(package.raw_results)

        # Guarantee the writer sees at least the overview as raw_results[0].
        if not raw_results:
            raw_results = [
                {
                    "title": package.title or "Source",
                    "url": str(package.metadata.get("url") or ""),
                    "snippet": summary,
                }
            ]
        else:
            # The writer's first snippet is the overview. If the adapter
            # left it empty, fill it from the summary.
            if not raw_results[0].get("snippet"):
                raw_results[0] = {**raw_results[0], "snippet": summary}

        # If only one raw_results row, append a facts-only row so the
        # writer's "research snippet" line carries the key facts.
        if len(raw_results) == 1 and facts_block:
            raw_results.append(
                {
                    "title": "Key facts",
                    "url": str(package.metadata.get("url") or ""),
                    "snippet": facts_block,
                }
            )

        topic_hint = str(package.metadata.get("topic_hint") or package.title or "")

        return ResearchPackage(
            topic=topic_hint,
            questions=[],
            raw_results=raw_results,
            summary=summary,
            sources=[str(package.metadata.get("url") or "")] if package.metadata.get("url") else [],
        )