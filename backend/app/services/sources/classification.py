"""Source classification — Phase 3.

A small, deterministic helper that maps a fetched ``SourcePackage`` to
one of the canonical source types used by the Writer prompt, the
frontend "source preview" card, and the Draft Viewer attribution.

The labels are intentionally coarse — they are about *framing* the
post, not about exhaustive classification. The Writer uses the label
to pick a narrative angle (e.g. "Worth checking out" for a GitHub
repo, "Just came across" for a blog article).

Source types (Phase 3 / Part 7):

* ``github_repository`` — public GitHub repos (the GitHub adapter).
* ``github_readme`` — a single ``/blob/main/README.md`` style URL.
  Falls through to the GitHub adapter but is tagged separately so
  the Writer knows the focus is a single document, not the project
  as a whole.
* ``blog_article`` — a generic public article / blog post.
* ``documentation`` — a docs site on a known documentation host.
* ``product_page`` — a launch / product-announcement style URL.
* ``generic_webpage`` — fallback for anything else accepted by the
  web-article adapter.

The classifier is:

* Pure (no I/O, no globals).
* Deterministic.
* Cheap (one regex + a frozenset lookup).

The classifier is called *after* the adapter has already produced a
``SourcePackage``. Adapters carry the most authoritative signal
(adapter name, GitHub repository fields, docs-host allowlist); the
classifier just projects that signal into a single ``source_type``
string and writes it back into ``package.metadata`` so the Writer
can read it without a second hop.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


#: Canonical source-type labels used across the system.
SOURCE_TYPE_GITHUB_REPOSITORY = "github_repository"
SOURCE_TYPE_GITHUB_README = "github_readme"
SOURCE_TYPE_BLOG_ARTICLE = "blog_article"
SOURCE_TYPE_DOCUMENTATION = "documentation"
SOURCE_TYPE_PRODUCT_PAGE = "product_page"
SOURCE_TYPE_GENERIC_WEBPAGE = "generic_webpage"

#: Frozen set of all known labels (for tests + validation).
KNOWN_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        SOURCE_TYPE_GITHUB_REPOSITORY,
        SOURCE_TYPE_GITHUB_README,
        SOURCE_TYPE_BLOG_ARTICLE,
        SOURCE_TYPE_DOCUMENTATION,
        SOURCE_TYPE_PRODUCT_PAGE,
        SOURCE_TYPE_GENERIC_WEBPAGE,
    }
)

#: Hosts that almost always serve product / launch announcements.
_PRODUCT_HOSTS: frozenset[str] = frozenset(
    {
        "producthunt.com",
        "news.ycombinator.com",
        "techcrunch.com",
        "theverge.com",
        "arstechnica.com",
        "venturebeat.com",
        "wired.com",
        "engadget.com",
    }
)

#: Path / title keywords that indicate a launch / announcement post.
_PRODUCT_KEYWORDS: tuple[str, ...] = (
    "launch",
    "launches",
    "launching",
    "introducing",
    "announce",
    "announcement",
    "announcing",
    "now available",
    "now in beta",
    "now in public",
    "general availability",
    "release notes",
    "shipping",
    "released",
)

#: Hosts that are documentation sites (smaller list than the
#: web-adapter's because the source_type is more conservative here).
_DOCS_HOSTS: frozenset[str] = frozenset(
    {
        "docs.python.org",
        "docs.djangoproject.com",
        "fastapi.tiangolo.com",
        "react.dev",
        "vuejs.org",
        "angular.io",
        "kubernetes.io",
        "redis.io",
        "flask.palletsprojects.com",
        "expressjs.com",
        "nodejs.org",
        "go.dev",
        "rust-lang.org",
        "typescriptlang.org",
        "developer.mozilla.org",
        "learn.microsoft.com",
        "cloud.google.com",
        "docs.aws.amazon.com",
        "learn.microsoft.com",
        "platform.openai.com",
    }
)

#: Hosts that are personal / corporate blogs (not documentation).
_BLOG_HOSTS: frozenset[str] = frozenset(
    {
        "medium.com",
        "dev.to",
        "hashnode.com",
        "substack.com",
        "wordpress.com",
        "blogger.com",
        "ghost.io",
        "towardsdatascience.com",
        "freecodecamp.org",
        "smashingmagazine.com",
    }
)

#: Detect a single-file GitHub README URL. The GitHub adapter
#: normalizes these to the repo root, but the *user intent* is to
#: extract a single document, so the source type is different.
_README_PATH_RE = re.compile(
    r"/blob/[^/]+/[^/]*README(?:\.[A-Za-z0-9]+)?$",
    re.IGNORECASE,
)


def classify(
    *,
    url: str,
    adapter: str,
    title: str = "",
    description: str = "",
    metadata: Optional[dict] = None,
) -> str:
    """Return the canonical source type for a URL.

    Pure function. Order of signals (most specific first):

    1. ``adapter == "github"`` (set by the GitHub adapter) →
       ``github_repository`` (or ``github_readme`` if the URL pointed
       at a single ``/blob/.../README.*`` file).
    2. Documentation hosts → ``documentation``.
    3. Product / launch pages → ``product_page``.
    4. Blog hosts → ``blog_article``.
    5. Otherwise → ``generic_webpage``.

    Parameters
    ----------
    url:
        The original (or final) URL the user submitted.
    adapter:
        The adapter that produced the package (``"github"``,
        ``"webpage"``, ``"stub"``).
    title, description:
        Optional title / description extracted by the adapter. Used
        to detect product / launch announcements by their content.
    metadata:
        The package's metadata dict, if any. Carries ``source_type``
        hints that the adapter may have already populated
        (``"docs_site"``, ``"webpage"``).
    """
    metadata = metadata or {}

    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()

    # 1. GitHub repository. The adapter name is the most reliable
    # signal — the GitHub adapter always sets ``metadata["adapter"]
    # == "github"`` regardless of the URL form.
    if adapter == "github":
        if _README_PATH_RE.search(path):
            return SOURCE_TYPE_GITHUB_README
        return SOURCE_TYPE_GITHUB_REPOSITORY

    # The web adapter stamps ``source_type`` in metadata. Trust it
    # for the docs-site branch it already understands.
    candidate = metadata.get("source_type")
    if candidate in KNOWN_SOURCE_TYPES:
        return str(candidate)

    # 2. Documentation hosts.
    if host in _DOCS_HOSTS:
        return SOURCE_TYPE_DOCUMENTATION

    # 3. Product / launch pages — by host or by title keyword.
    haystack = f"{title} {description}".lower()
    if host in _PRODUCT_HOSTS:
        return SOURCE_TYPE_PRODUCT_PAGE
    if any(kw in haystack for kw in _PRODUCT_KEYWORDS):
        return SOURCE_TYPE_PRODUCT_PAGE

    # 4. Blog hosts.
    if host in _BLOG_HOSTS:
        return SOURCE_TYPE_BLOG_ARTICLE

    # 5. Fallback.
    return SOURCE_TYPE_GENERIC_WEBPAGE


def get_narrative_angle(source_type: str) -> str:
    """Return a short writer-facing instruction for the source type.

    Used by the Writer prompt builder. Not user-facing — the frontend
    renders its own preview. Pure / side-effect-free.
    """
    angles = {
        SOURCE_TYPE_GITHUB_REPOSITORY: (
            "Worth checking out if you're working with this kind of "
            "tooling — interesting implementation, technical idea, "
            "developer value."
        ),
        SOURCE_TYPE_GITHUB_README: (
            "Came across a README that explains this project clearly — "
            "the strongest technical takeaway is the architecture or "
            "design decision."
        ),
        SOURCE_TYPE_BLOG_ARTICLE: (
            "Just came across an interesting article — central insight, "
            "useful takeaway, why it matters to a working professional."
        ),
        SOURCE_TYPE_DOCUMENTATION: (
            "This documentation highlights a practical capability — "
            "explain the concept, the use case, and the developer takeaway."
        ),
        SOURCE_TYPE_PRODUCT_PAGE: (
            "What changed, why it matters, and who benefits — keep it "
            "factual and useful, not promotional."
        ),
        SOURCE_TYPE_GENERIC_WEBPAGE: (
            "Strongest insight, useful interpretation, meaningful takeaway — "
            "frame the source as something worth reading."
        ),
    }
    return angles.get(source_type, angles[SOURCE_TYPE_GENERIC_WEBPAGE])


def get_source_label(source_type: str) -> str:
    """Return a human-readable label for the source-type card UI."""
    labels = {
        SOURCE_TYPE_GITHUB_REPOSITORY: "GitHub Repository",
        SOURCE_TYPE_GITHUB_README: "GitHub README",
        SOURCE_TYPE_BLOG_ARTICLE: "Blog Article",
        SOURCE_TYPE_DOCUMENTATION: "Documentation",
        SOURCE_TYPE_PRODUCT_PAGE: "Product Announcement",
        SOURCE_TYPE_GENERIC_WEBPAGE: "Web Article",
    }
    return labels.get(source_type, "Web Article")


__all__ = [
    "KNOWN_SOURCE_TYPES",
    "SOURCE_TYPE_BLOG_ARTICLE",
    "SOURCE_TYPE_DOCUMENTATION",
    "SOURCE_TYPE_GENERIC_WEBPAGE",
    "SOURCE_TYPE_GITHUB_README",
    "SOURCE_TYPE_GITHUB_REPOSITORY",
    "SOURCE_TYPE_PRODUCT_PAGE",
    "classify",
    "get_narrative_angle",
    "get_source_label",
]
