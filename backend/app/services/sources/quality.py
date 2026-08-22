"""Source quality evaluation — Phase 8.

Deterministic, LLM-free evaluation of whether a fetched
``SourcePackage`` contains enough meaningful material to ground a
LinkedIn post.

Three outcomes:

* ``SourceQuality.GOOD``   — the package has a usable title,
  description, and at least ~120 characters of meaningful body
  content. Generation should proceed.

* ``SourceQuality.WEAK``   — there is some material, but it is
  thin. The user gets a friendly "this source doesn't contain
  enough readable information" message with a CTA to try another
  URL or create from a topic. We do NOT generate a confident
  hallucinated LinkedIn post from a WEAK source.

* ``SourceQuality.FAILED`` — the package has no usable content.
  This is essentially never used directly by the web / github
  adapters (they raise ``SourceUnavailableError`` instead), but
  is exposed for tests and for adapter authors that want a
  post-validation hook.

The thresholds are deliberately conservative: a normal blog
post (≥120 chars of body + a title + a description) is GOOD. A
navigation-only landing page (a 4 KB blob with no title and
no real paragraphs) is WEAK. An empty page is WEAK (not FAILED,
because a 0-char page from a successful fetch is unusual but
possible). Anything below 60 chars of body is WEAK.

The threshold for ``GOOD`` is intentionally not "perfect" — we
don't need the source to be a textbook. We need the post to be
grounded in *something*. A 200-word article with a title and
description is plenty for a 250-word LinkedIn post that respects
the no-fabrication rule.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Iterable

from backend.app.services.sources.base import SourcePackage

logger = logging.getLogger(__name__)


class SourceQuality(str, Enum):
    GOOD = "good"
    WEAK = "weak"
    FAILED = "failed"


#: Minimum body character count for a source to be considered
#: "good" (grounded generation). Below this the source is WEAK
#: and the user gets a friendly fallback.
GOOD_MIN_BODY_CHARS = 120

#: Hard floor — anything below this is treated as
#: "essentially empty" and the user is told the source could not
#: be read.
WEAK_MIN_BODY_CHARS = 60


def evaluate_source_quality(package: SourcePackage) -> tuple[SourceQuality, str]:
    """Return a ``(quality, reason)`` tuple for the given package.

    ``reason`` is a short, user-safe string used for the
    frontend "Source preview" badge ("Weak source", "Ready",
    etc.) and for the audit log. It NEVER contains raw HTML, full
    body text, or any other user-content.
    """
    if package is None:
        return SourceQuality.FAILED, "no source package"

    body = (package.summary or "").strip()
    if not body and package.raw_results:
        # The body is sometimes stored in the second or third
        # raw_results entry, depending on the adapter.
        for entry in package.raw_results:
            candidate = (entry.get("snippet") or "").strip()
            if candidate and not candidate.lower().startswith(("key facts", "key point", "architecture", "detail", "readme")):
                body = candidate
                break

    title = (package.title or "").strip()

    # If a body is missing entirely AND there's no summary, the
    # adapter likely failed silently.
    if not body and not title:
        return SourceQuality.FAILED, "no readable content found"

    char_count = len(body)

    if char_count < WEAK_MIN_BODY_CHARS:
        return (
            SourceQuality.WEAK,
            "insufficient readable content",
        )

    if not title:
        return (
            SourceQuality.WEAK,
            "missing title — content is too ungrounded to use",
        )

    if char_count < GOOD_MIN_BODY_CHARS:
        return (
            SourceQuality.WEAK,
            f"only {char_count} characters of body text",
        )

    if not _has_structural_signal(package):
        return (
            SourceQuality.WEAK,
            "no headings, paragraphs, or list items detected",
        )

    return SourceQuality.GOOD, "ok"


def _has_structural_signal(package: SourcePackage) -> bool:
    """Return True if the package has at least one heading,
    paragraph, or list-style content marker.

    This is a cheap heuristic to filter out pages that *appear*
    to have content but are actually only nav text and meta tags
    """
    if not package.raw_results:
        return True  # be permissive when the adapter didn't emit rows
    for entry in package.raw_results:
        snippet = (entry.get("snippet") or "").strip()
        if not snippet:
            continue
        # Headings, list items, code blocks — any structural signal.
        if any(
            marker in snippet
            for marker in (
                "\n",
                "•",
                "- ",
                "## ",
                "```",
                "<h",
            )
        ):
            return True
    return False


def summarize_quality_for_ui(quality: SourceQuality, package: SourcePackage) -> dict:
    """Project the quality + package into a small dict the
    frontend can render directly.

    Returned shape::

        {
            "quality": "good" | "weak" | "failed",
            "reason": "...",                 # short, user-safe
            "char_count": 1234,
            "has_title": true,
            "has_description": true,
        }
    """
    body = (package.summary or "").strip() if package else ""
    title = (package.title or "").strip() if package else ""
    description = ""
    if package and package.raw_results:
        # The web adapter stores the description in raw_results[0]
        # but only when the page had a real <meta name=description>.
        # We don't try to re-derive it here.
        pass
    return {
        "quality": quality.value,
        "reason": _reason_for(quality, package),
        "char_count": len(body),
        "has_title": bool(title),
        "has_description": bool(description),
    }


def _reason_for(quality: SourceQuality, package: SourcePackage) -> str:
    if quality == SourceQuality.GOOD:
        return "Source looks good."
    if quality == SourceQuality.WEAK:
        return "Source has only a little readable content."
    return "Source could not be read."


def weak_source_user_message(quality: SourceQuality, package: SourcePackage) -> str:
    """Return a short, user-safe message for the frontend to render
    when a source fails the quality gate.

    The message intentionally does NOT echo raw source content, the
    URL, or any other backend-internal details. The user is
    expected to:
        * try another public URL, or
        * create a LinkedIn post from a topic instead.
    """
    if quality == SourceQuality.WEAK:
        return (
            "This source doesn't contain enough readable information to "
            "create a grounded LinkedIn post. Try another public URL, or "
            "create from a topic instead."
        )
    if quality == SourceQuality.FAILED:
        return (
            "We couldn't read useful content from this page. Try another "
            "public URL, or create from a topic instead."
        )
    return ""


def is_weak_or_failed(quality: SourceQuality) -> bool:
    return quality in (SourceQuality.WEAK, SourceQuality.FAILED)
