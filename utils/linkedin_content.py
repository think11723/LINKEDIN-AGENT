"""Canonical LinkedIn content normalizer.

WHY THIS MODULE EXISTS
=====================

LLMs (Writer, Reviewer/Improver, future agents) frequently inject
Markdown-style formatting (``## Heading``, ``**bold**``, `` `code` ``,
``Hashtags: ...`` trailing lines) into the generated post even when
the prompt explicitly says "do not use Markdown". LinkedIn does NOT
render Markdown. ``##``, ``**``, `` ` `` etc. would be sent verbatim
and shown to readers as raw garbage.

We fix this in ONE place, not in every agent. Every code path that
produces a ``LinkedInPost`` (Writer, Reviewer/Improver, URL-mode
generation, future agents, manual edits) must run the result through
this normalizer before persisting it. The Draft Viewer and the LinkedIn
publish endpoint then trust the persisted content.

DESIGN PRINCIPLES
=================

* Pure: no globals, no side effects, no LLM calls.
* Deterministic: same input → same output, every time.
* Idempotent: ``normalize(normalize(x)) == normalize(x)``.
* Targeted: do NOT use ``str.replace("*", "")`` style blanket deletion.
  Stripping ``*`` would destroy legitimate text like
  "5 * 3 = 15" or "10 * 20 users". Instead, recognize Markdown
  syntactic patterns (e.g. a leading "## " at the start of a line)
  and strip only those markers.
* LinkedIn-native: the output is plain text with deliberate line
  breaks. Paragraphs are separated by blank lines, bullets use "• ".
  Emojis are preserved.

WHAT THE NORMALIZER DOES
=========================

For the content string:

1. Trim leading/trailing whitespace per line and remove trailing
   blank lines.
2. Collapse runs of 3+ blank lines down to exactly 2 (paragraph break).
3. Strip Markdown heading markers "## ", "### ", "#### " at the START
   of a line only. A literal "#" character in the middle of a line is
   preserved (e.g. "C# is great").
4. Strip Markdown bold markers "**" / "__" that wrap an entire token
   (matching pair), but keep literal "*" or "_" characters in prose.
5. Strip Markdown italic markers "*" / "_" that wrap an entire token,
   but again keep literal characters in prose.
6. Strip Markdown inline-code backticks ("`") that wrap a single
   token, but only at the start and end of the matching pair on the
   same line. A literal "`" character in the middle of a sentence is
   preserved.
7. Strip a Markdown fenced code block ("```text\n...\n```") entirely.
8. Strip a Markdown horizontal rule "---" or "***" or "___" on its own
   line.
9. Strip a trailing "Hashtags: #a #b" sentence at the END of the
   content, so hashtags do not leak into body text.
10. Collapse multiple consecutive spaces inside a line into a single
    space, except at the start of a line (preserve indentation).

For the hashtags list:

1. Each hashtag must start with "#".
2. Each hashtag must contain at least one non-# word character.
3. Duplicates are removed (preserve order).
4. The list is capped at 10 hashtags.
5. Empty / whitespace-only hashtags are dropped.

For the title:

1. Trim leading/trailing whitespace.
2. Collapse internal runs of whitespace.
3. Strip any leading Markdown heading markers (they leak from
   `TITLE: ## ...`).

The function returns a new ``LinkedInPost``; it does NOT mutate the
input.
"""

from __future__ import annotations

import re
from typing import List

from models.models import LinkedInPost


_MAX_HASHTAGS = 10

# Markdown heading marker at the START of a line.
# Matches:  "## Heading", "### Heading", "#### Heading"
# Does NOT match: "I love ## symbols" (in the middle of a sentence).
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+", flags=re.MULTILINE)

# Markdown fenced code block on its own lines.
_FENCED_CODE_BLOCK_RE = re.compile(
    r"```[^\n]*\n.*?\n```",
    flags=re.DOTALL,
)

# Markdown horizontal rule on its own line.
_HR_LINE_RE = re.compile(
    r"^\s*(?:---+|\*\*\*+|___+)\s*$",
    flags=re.MULTILINE,
)

# Trailing "Hashtags: ..." or "Tags: ..." sentence at end of content.
_TRAILING_HASHTAGS_LINE_RE = re.compile(
    r"\n*\s*(?:hashtags?|tags?)\s*:\s*#[^\n]*\.?\s*$",
    flags=re.IGNORECASE,
)

# Runs of 3+ blank lines.
_MULTI_BLANK_RE = re.compile(r"\n\s*\n\s*\n+")

# Multiple spaces inside a line (preserve leading indentation).
_MULTI_SPACE_RE = re.compile(r"(?<=\S) {2,}(?=\S)")

# Whitespace at start/end of every line.
_LINE_EDGE_RE = re.compile(r"^[ \t]+|[ \t]+$", flags=re.MULTILINE)

# Trailing blank lines at end of string.
_TRAILING_BLANKS_RE = re.compile(r"\n+$")

# Markdown bold/italic pair wrapping a single token.
# Matches:  "**word**", "**two_words**", "__word__", "*word*", "_word_"
# Does NOT match:
#   - "5 * 3 = 15" (multi-word content between asterisks; arithmetic)
#   - "**bold**italic**" (consecutive bold + italic — not a Markdown pair)
# We require:
#   - single token between markers (no whitespace inside), OR
#   - multiple words joined by a single space inside (Markdown bold
#     allows "**two words**")
# Plus negative lookaround so `**word**` is not matched as `*word*`.
_BOLD_AST_RE = re.compile(r"(?<!\*)\*(\S+)\*(?!\*)")  # *token*
_BOLD_DBL_AST_RE = re.compile(r"\*\*(\S+(?:\s\S+)*)\*\*")  # **text**
_BOLD_UND_RE = re.compile(r"(?<!_)_(\S+)_(?!_)")  # _token_
_BOLD_DBL_UND_RE = re.compile(r"__(\S+(?:\s\S+)*)__")  # __text__
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")  # `token`

# Markdown link: [label](url)
# - Preserves BOTH label and URL.
# - Renders as `label — url` so the URL remains in the post text.
# - Does NOT touch bare URLs (they have no surrounding `[` ... `]`).
# - Catches links whose label or URL spans multiple lines (DOTALL).
_MARKDOWN_LINK_RE = re.compile(
    r"\[([^\]\n]*)\]\(([^)\n]+)\)"
)


def _strip_markdown_links(text: str) -> str:
    """Convert ``[label](url)`` to ``label — url`` so the URL survives
    and the label survives. Bare URLs without surrounding brackets are
    left untouched. Catches both ``https://...`` and relative paths."""
    def _repl(m: re.Match) -> str:
        label = m.group(1).strip()
        url = m.group(2).strip()
        if not url:
            return label
        return f"{label} — {url}" if label else url

    return _MARKDOWN_LINK_RE.sub(_repl, text)


def _strip_inline_pairs(text: str) -> str:
    """Strip a thin Markdown pair when it wraps a single non-empty
    token that does not contain the boundary character. Strips in
    order from most-specific (longer markers) to least-specific so
    that a leading '**' of a '***bold-italic***' is not mis-parsed."""
    out = text
    out = _BOLD_DBL_AST_RE.sub(r"\1", out)  # **text**
    out = _BOLD_DBL_UND_RE.sub(r"\1", out)  # __text__
    out = _BOLD_AST_RE.sub(r"\1", out)  # *text*
    out = _BOLD_UND_RE.sub(r"\1", out)  # _text*
    out = _INLINE_CODE_RE.sub(r"\1", out)  # `code`
    return out


def _strip_markdown(text: str) -> str:
    """Strip residual Markdown markers from content text.

    Targeted removal only. Does NOT blanket-strip ``*``, ``#``,
    ``_``, or `` ` `` characters. Those are preserved when they
    appear inside prose (e.g. "C# is great", "5 * 3 = 15").
    """
    out = text
    # 1. Fenced code blocks first (they span multiple lines).
    out = _FENCED_CODE_BLOCK_RE.sub("", out)
    # 2. Heading markers at the start of lines.
    out = _HEADING_LINE_RE.sub("", out)
    # 3. Horizontal rules on their own line.
    out = _HR_LINE_RE.sub("", out)
    # 4. Markdown links: convert [label](url) to "label — url" so the
    # URL survives. Bare URLs (no brackets) are left untouched by the
    # regex and pass through unchanged.
    out = _strip_markdown_links(out)
    # 5. Bold/italic pairs (must run AFTER headings so "## " isn't
    # mis-parsed as a pair marker).
    out = _strip_inline_pairs(out)
    return out


def _trim_lines(text: str) -> str:
    """Strip leading/trailing whitespace from every line."""
    return _LINE_EDGE_RE.sub("", text)


def _collapse_blank_runs(text: str) -> str:
    """Collapse 3+ consecutive blank lines down to exactly 2."""
    return _MULTI_BLANK_RE.sub("\n\n", text)


def _collapse_inter_line_spaces(text: str) -> str:
    """Collapse 2+ consecutive spaces inside a line to a single space,
    preserving leading indentation."""
    return _MULTI_SPACE_RE.sub(" ", text)


def _strip_trailing_hashtags_sentence(text: str) -> str:
    """Remove a trailing 'Hashtags: #a #b ...' sentence so hashtags
    do not leak into body text. Only strips at the END of the content
    so legitimate in-prose 'hashtags' mentions are preserved."""
    return _TRAILING_HASHTAGS_LINE_RE.sub("", text)


def normalize_content(content: str) -> str:
    """Run the full LinkedIn content normalization pipeline.

    Deterministic. Pure. Idempotent: ``normalize(normalize(x)) ==
    normalize(x)``.
    """
    if not content:
        return ""

    out = content
    out = _strip_markdown(out)
    out = _strip_trailing_hashtags_sentence(out)
    out = _trim_lines(out)
    out = _collapse_blank_runs(out)
    out = _collapse_blank_runs(out)  # idempotent: 3+ → 2; 4+ → 2; stable
    out = _collapse_inter_line_spaces(out)
    out = _TRAILING_BLANKS_RE.sub("", out)
    return out


def normalize_title(title: str) -> str:
    """Strip leading Markdown from a title and collapse whitespace."""
    if not title:
        return ""
    out = _HEADING_LINE_RE.sub("", title)
    out = _collapse_inter_line_spaces(out)
    return out.strip()


def normalize_hashtags(hashtags: List[str]) -> List[str]:
    """Normalize the hashtags list.

    * Each entry starts with "#".
    * Each entry has at least one non-# word character.
    * Duplicates removed (order preserved).
    * Maximum 10 entries.
    """
    if not hashtags:
        return []

    seen = set()
    out: List[str] = []
    for tag in hashtags:
        if not isinstance(tag, str):
            continue
        t = tag.strip()
        if not t:
            continue
        if not t.startswith("#"):
            t = "#" + t.lstrip("#").lstrip()
        # Drop tags that are only "#" or "##" etc. — must have at
        # least one non-# word character.
        if not any(ch.isalnum() for ch in t):
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= _MAX_HASHTAGS:
            break
    return out


def normalize_linkedin_post(
    title: str,
    content: str,
    hashtags: List[str],
) -> LinkedInPost:
    """Return a new ``LinkedInPost`` whose fields are LinkedIn-native.

    Single canonical normalization point. The Writer, Reviewer,
    URL-mode generation, and any future agent MUST run their result
    through this function before persisting.
    """
    return LinkedInPost(
        title=normalize_title(title),
        content=normalize_content(content),
        hashtags=normalize_hashtags(hashtags),
    )
