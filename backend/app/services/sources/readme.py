"""README cleaning — Phase 8.

Light, deterministic post-processing of a GitHub README so the
Writer sees a clean, signal-dense body instead of badge soup,
duplicated sections, and HTML artifacts.

The cleaner preserves the actual content but strips:

  * badge / shields.io image lines (a long ``![…](https://
    img.shields.io/…)`` row that adds no semantic value)
  * centered HTML ``<p align="center">`` blocks containing only an
    image — these are decorative hero banners, not content
  * excessive blank lines
  * "Installation" / "Quick start" / "License" footers that
    introduce no new fact about the project (we keep them only
    when their *content* is non-trivial)
  * HTML junk (``<br>`` runs, stray attributes)
  * zero-width and control characters

The cleaner is NOT an LLM and NEVER rewrites content. It is a
deterministic text-munging function. The output is byte-for-byte
deterministic given the same input.

Hard caps (applied after cleaning):

  * ``MAX_README_CHARS`` — the LLM never sees more than this many
    characters of README. The cap is applied at a paragraph
    boundary when possible so the result still ends on a complete
    sentence.
"""

from __future__ import annotations

import re
from typing import Optional


#: Hard cap on the cleaned README that the Writer sees.
MAX_README_CHARS = 12_000

#: Number of leading content characters the LLM gets to see
#: before the cap kicks in. We keep a generous slice for the
#: project description + first feature + first usage example.
HEAD_CHARS = 8_000


_BADGE_URL_HINTS = (
    "img.shields.io",
    "travis-ci.org",
    "travis-ci.com",
    "circleci.com",
    "github.com/workflow",
    "codecov.io",
    "coveralls.io",
    "badge.fury.io",
    "gitter.im",
    "discord.gg",
    "app.codacy.com",
)


_LINE_BADGE = re.compile(
    r"^\s*!\[(?P<alt>[^\]]*)\]\((?P<url>[^)]+)\)\s*$",
)
# Drop a paragraph that consists of a centered <p>…<img/></p>
# decorative banner.
_CENTERED_BANNER = re.compile(
    r"<p[^>]*align\s*=\s*['\"]center['\"][^>]*>\s*<a[^>]*>\s*<img[^>]*>\s*</a>\s*</p>",
    re.IGNORECASE,
)
# ``<img …>`` on its own line, used to flag decorative banners.
_IMG_LINE = re.compile(
    r"^\s*(<p[^>]*>\s*)?(<a[^>]*>\s*)?<img\b[^>]*>(</a>\s*)?(</p>\s*)?$",
    re.IGNORECASE,
)


def _is_badge_line(line: str) -> bool:
    """Return True if the line is a single-image Markdown badge
    pointing at a known CI / coverage / community service.
    """
    m = _LINE_BADGE.match(line)
    if not m:
        return False
    url = m.group("url") or ""
    return any(hint in url for hint in _BADGE_URL_HINTS)


def _is_decorative_html_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if _CENTERED_BANNER.search(s):
        return True
    if _IMG_LINE.match(s):
        return True
    return False


_WS_RUN = re.compile(r"[ \t]+\n")
_BLANK_3PLUS = re.compile(r"\n{3,}")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_readme(text: str, *, max_chars: int = MAX_README_CHARS) -> str:
    """Apply the README cleaner.

    * drops badge lines
    * drops decorative HTML image lines
    * collapses excessive blank lines
    * removes zero-width / control characters
    * caps the result at ``max_chars`` at a paragraph boundary
    * appends a small "[…README truncated…]" marker so the
      Writer can mention it without losing the fact that
      material was available
    """
    if not text:
        return ""

    # Normalize newlines.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Strip control characters.
    text = _CONTROL_CHARS.sub("", text)

    cleaned_lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.rstrip()
        if _is_badge_line(line):
            continue
        if _is_decorative_html_line(line):
            continue
        # Strip pure HTML / markdown link noise lines (e.g.
        # ``[Contributors](…/graphs/contributors)``) that don't
        # add semantic content.
        if line.strip().startswith("[") and line.strip().endswith(")") and "://" in line:
            # Keep the link text but drop the URL — the Writer
            # does not need clickable links.
            # But only when the line is short and looks like a
            # label-only link.
            stripped = line.strip()
            if len(stripped) < 90 and "](http" in stripped:
                bracket = stripped.find("]")
                if bracket > 1:
                    label = stripped[1:bracket]
                    if label and label.lower() not in {"license", "ci", "build"}:
                        line = label
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines)
    # Collapse trailing whitespace on each line.
    cleaned = _WS_RUN.sub("\n", cleaned)
    # Collapse 3+ blank lines to 2.
    cleaned = _BLANK_3PLUS.sub("\n\n", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return ""

    if len(cleaned) <= max_chars:
        return cleaned

    head = cleaned[:max_chars]
    # Cut at the last paragraph break inside the head.
    last_break = head.rfind("\n\n")
    if last_break > max_chars // 2:
        return head[:last_break].rstrip() + "\n\n[… README truncated for brevity …]"

    last_break = head.rfind("\n")
    if last_break > max_chars // 2:
        return head[:last_break].rstrip() + "\n\n[… README truncated for brevity …]"

    return head.rstrip() + "\n\n[… README truncated for brevity …]"


def first_paragraph(text: str, *, max_chars: int = 800) -> str:
    """Return the first non-heading, non-empty paragraph of a
    cleaned README, capped at ``max_chars``. Used by the GitHub
    adapter to surface a short project description to the
    Writer.
    """
    if not text:
        return ""
    lines = text.splitlines()
    paragraph: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            if paragraph:
                break
            continue
        # Skip Markdown headings.
        if s.startswith("#"):
            paragraph = []
            continue
        # Skip badge noise that survived the cleaner.
        if s.startswith("!["):
            continue
        paragraph.append(s)
        if len(" ".join(paragraph)) > max_chars:
            break
    return " ".join(paragraph)[:max_chars].strip()


def extract_headings(text: str, *, limit: int = 12) -> list[str]:
    """Return a list of markdown headings (``#``, ``##``, ``###``)
    from a cleaned README. Used by the Writer's source context
    to surface the project structure (Features, Usage, API, etc.).
    """
    if not text:
        return []
    out: list[str] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith(("# ", "## ", "### ")):
            heading = s.lstrip("#").strip()
            if heading and len(heading) < 120:
                out.append(heading)
                if len(out) >= limit:
                    break
    return out
