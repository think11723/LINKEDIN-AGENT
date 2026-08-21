"""Tests for the canonical LinkedIn content normalizer.

These tests pin the contract of utils.linkedin_content so future
agents, prompt rewrites, or fallback providers cannot regress the
LinkedIn-native formatting.

The tests cover:
  - Markdown stripping (headings, bold, italic, inline code, fenced
    code blocks, horizontal rules).
  - Targeted stripping — literal "*" "#" "_" "`" characters inside
    prose are preserved (e.g. "5 * 3 = 15", "C# is great").
  - Hashtag normalization (deduplication, ordering, capping at 10,
    must start with "#", must have at least one word char).
  - Title normalization (strip leading Markdown heading markers,
    collapse whitespace).
  - Trailing "Hashtags: ..." sentence in content is removed so
    hashtags do not leak into body text.
  - Idempotence: normalize(normalize(x)) == normalize(x).
  - Pure: pure on the input shape, no globals, no LLM calls.
  - End-to-end: writers/reviewers/persistence path runs the result
    through normalize_linkedin_post, so a hand-crafted
    "## Heading\n\nbody\n\nHashtags: #a #b" sample is stored and
    presented as "Heading\n\nbody" with hashtags "#a #b" attached
    separately, never inline.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so "utils.linkedin_content" imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from utils.linkedin_content import (
    normalize_content,
    normalize_hashtags,
    normalize_linkedin_post,
    normalize_title,
)


# ---------------------------------------------------------------------------
# Markdown stripping — targeted, not blanket
# ---------------------------------------------------------------------------


def test_normalize_content_strips_h1_through_h6_heading_markers():
    """Lines starting with ##, ###, #### are stripped of those markers.
    The actual heading text is preserved."""
    text = "## Heading 1\n### Heading 2\n#### Heading 3"
    out = normalize_content(text)
    assert out == "Heading 1\nHeading 2\nHeading 3"


def test_normalize_content_preserves_hash_inside_prose():
    """A literal '#' character in the middle of a line is preserved.
    Only leading '## ' heading markers are removed."""
    text = "I love C# and use it daily.\n## Real heading"
    out = normalize_content(text)
    assert "C#" in out
    assert "Real heading" in out
    assert "##" not in out.split("\n")[0]


def test_normalize_content_strips_bold_markers_pair_around_token():
    text = "This is **really important** and __also important__ here."
    out = normalize_content(text)
    assert "**" not in out
    assert "__" not in out
    assert "really important" in out
    assert "also important" in out


def test_normalize_content_preserves_asterisk_in_arithmetic():
    """A literal '*' character used as a math operator is preserved.
    This guards against a blanket str.replace('*', '') regression."""
    text = "5 * 3 = 15 and 10 * 20 users visited."
    out = normalize_content(text)
    assert "5 * 3 = 15" in out
    assert "10 * 20 users" in out


def test_normalize_content_strips_italic_markers():
    text = "This is *italic* and _also italic_ here."
    out = normalize_content(text)
    assert "italic" in out
    assert "*italic*" not in out


def test_normalize_content_strips_fenced_code_block():
    text = "Intro paragraph.\n```python\nprint('hi')\n```\nConclusion."
    out = normalize_content(text)
    assert "print('hi')" not in out
    assert "Intro paragraph." in out
    assert "Conclusion." in out


def test_normalize_content_strips_inline_code_backticks_pair():
    text = "Use the `print()` function for output."
    out = normalize_content(text)
    assert "`print()`" not in out
    assert "print()" in out


def test_normalize_content_strips_horizontal_rule_on_its_own_line():
    text = "Before\n\n---\n\nAfter"
    out = normalize_content(text)
    assert "---" not in out
    assert "Before" in out
    assert "After" in out


def test_normalize_content_handles_combined_markdown():
    """Multiple markers in the same content are all stripped correctly."""
    text = (
        "## Title\n"
        "\n"
        "Body paragraph.\n"
        "\n"
        "**Bold** claim with `inline` code.\n"
        "\n"
        "---\n"
        "\n"
        "Hashtags: #a #b #c"
    )
    out = normalize_content(text)
    assert "##" not in out
    assert "**" not in out
    assert "`inline`" not in out
    assert "Hashtags:" not in out
    assert "#a #b #c" not in out
    assert "Title" in out
    assert "Body paragraph." in out
    assert "Bold claim" in out
    assert "inline code" in out


# ---------------------------------------------------------------------------
# Trailing "Hashtags: ..." sentence stripping
# ---------------------------------------------------------------------------


def test_normalize_content_strips_trailing_hashtags_sentence():
    text = "A great paragraph.\n\nHashtags: #a #b #c"
    out = normalize_content(text)
    assert "Hashtags:" not in out
    assert "#a #b #c" not in out
    assert "A great paragraph." in out


def test_normalize_content_preserves_in_prose_hashtag_mention():
    text = "I love #python in production\n\nHashtags: #python #AI"
    out = normalize_content(text)
    assert "I love #python" in out
    assert "Hashtags:" not in out


def test_normalize_content_preserves_hash_at_end_if_no_label():
    """A bare trailing hashtag line with no 'Hashtags:' label is kept —
    only the labelled trailing sentence is stripped."""
    text = "Body text\n#python #AI"
    out = normalize_content(text)
    assert "#python #AI" in out


# ---------------------------------------------------------------------------
# Blank-line collapsing
# ---------------------------------------------------------------------------


def test_normalize_content_collapses_excess_blank_lines():
    text = "First\n\n\n\n\nSecond"
    out = normalize_content(text)
    # 3+ blank lines → exactly 2 (one paragraph break)
    assert out == "First\n\nSecond"


def test_normalize_content_collapses_trailing_blank_lines():
    text = "Body\n\n\n\n"
    out = normalize_content(text)
    assert not out.endswith("\n")


# ---------------------------------------------------------------------------
# Idempotence + purity
# ---------------------------------------------------------------------------


def test_normalize_content_is_idempotent():
    text = "## Heading\n\n**Bold** with `code`\n\n---\n\nHashtags: #a #b"
    once = normalize_content(text)
    twice = normalize_content(once)
    assert once == twice


def test_normalize_content_handles_empty_string():
    assert normalize_content("") == ""


def test_normalize_content_handles_whitespace_only():
    assert normalize_content("   \n\n  \t\n") == ""


# ---------------------------------------------------------------------------
# Title normalization
# ---------------------------------------------------------------------------


def test_normalize_title_strips_leading_markdown_heading():
    assert normalize_title("## Hello World") == "Hello World"
    assert normalize_title("### My Title") == "My Title"
    assert normalize_title("##  Multi  Spaces  ") == "Multi Spaces"


def test_normalize_title_does_not_strip_hash_in_middle():
    assert normalize_title("My C# Post") == "My C# Post"


def test_normalize_title_handles_empty_string():
    assert normalize_title("") == ""
    assert normalize_title("   ") == ""


# ---------------------------------------------------------------------------
# Hashtag normalization
# ---------------------------------------------------------------------------


def test_normalize_hashtags_removes_duplicates_preserving_order():
    assert normalize_hashtags(
        ["#AI", "#Python", "#AI", "#LangChain"]
    ) == ["#AI", "#Python", "#LangChain"]


def test_normalize_hashtags_adds_hash_prefix_if_missing():
    assert normalize_hashtags(["AI", "Python"]) == ["#AI", "#Python"]


def test_normalize_hashtags_drops_empty_or_pure_hash_tags():
    assert normalize_hashtags(["#", "##", "#AI", "###"]) == ["#AI"]


def test_normalize_hashtags_caps_at_ten():
    tags = [f"#Tag{i}" for i in range(20)]
    out = normalize_hashtags(tags)
    assert len(out) == 10


def test_normalize_hashtags_preserves_word_characters():
    assert normalize_hashtags(["#AI", "#Python 3", "#Foo-Bar"]) == [
        "#AI",
        "#Python 3",
        "#Foo-Bar",
    ]


def test_normalize_hashtags_handles_empty_list():
    assert normalize_hashtags([]) == []
    assert normalize_hashtags(["", "  "]) == []


# ---------------------------------------------------------------------------
# End-to-end: normalize_linkedin_post
# ---------------------------------------------------------------------------


def test_normalize_linkedin_post_strips_markdown_and_trailing_hashtags():
    post = normalize_linkedin_post(
        title="## My Post",
        content=(
            "**Important** point here.\n"
            "\n"
            "Some details with `code`.\n"
            "\n"
            "---\n"
            "\n"
            "Hashtags: #a #b #c"
        ),
        hashtags=["#a", "#b", "#c"],
    )
    assert "##" not in post.title
    assert "**" not in post.content
    assert "`code`" not in post.content
    assert "---" not in post.content
    assert "Hashtags:" not in post.content
    assert post.hashtags == ["#a", "#b", "#c"]
    assert post.title == "My Post"
    assert "Important point here" in post.content


def test_normalize_linkedin_post_dedupes_and_caps_hashtags():
    post = normalize_linkedin_post(
        title="T",
        content="Body",
        hashtags=[f"#Tag{i}" for i in range(15)] + ["#Tag0"],
    )
    assert len(post.hashtags) == 10
    # First occurrence preserved; duplicates dropped.
    assert post.hashtags[0] == "#Tag0"
    assert len(set(post.hashtags)) == 10


def test_normalize_linkedin_post_is_pure():
    """The function must NOT mutate the input strings / list."""
    title = "## Title"
    content = "**bold**"
    hashtags = ["AI", "#Python"]
    title_before = title
    content_before = content
    hashtags_before = list(hashtags)
    normalize_linkedin_post(title=title, content=content, hashtags=hashtags)
    assert title == title_before
    assert content == content_before
    assert hashtags == hashtags_before


def test_normalize_linkedin_post_returns_linkedinpost_instance():
    from models.models import LinkedInPost

    post = normalize_linkedin_post("T", "C", ["#X"])
    assert isinstance(post, LinkedInPost)
    assert post.title == "T"
    assert post.content == "C"
    assert post.hashtags == ["#X"]


# ---------------------------------------------------------------------------
# Markdown link normalization + raw URL preservation
# ---------------------------------------------------------------------------


def test_markdown_link_label_and_url_both_survive():
    """`[label](url)` is converted so the label and url are both
    preserved (label survives as readable text, url survives verbatim).
    The output must not look like Markdown."""
    text = "Check the [GitHub Repository](https://github.com/example/repo) for details."
    out = normalize_content(text)
    # The brackets and parentheses must be gone
    assert "[" not in out
    assert "](" not in out
    # But the label and URL must both be present in the output
    assert "GitHub Repository" in out
    assert "https://github.com/example/repo" in out
    # And the URL must NOT be corrupted by other normalizations
    assert "github.com/example/repo" in out


def test_markdown_link_label_only_kept_when_url_empty():
    """A bare `[label]()` with empty url still keeps the label."""
    text = "Read [the spec]() for details."
    out = normalize_content(text)
    assert "the spec" in out


def test_markdown_link_url_only_when_label_is_empty_brackets():
    """A `[]()` link with empty url + empty label is not matched by
    the link regex (which requires `[^)\n]+` inside parens). The raw
    string passes through unchanged. The regex does NOT eat empty
    links."""
    text = "See []() for context."
    out = normalize_content(text)
    # Empty link doesn't match the regex; passes through. The
    # bracket characters are preserved literally in this edge case.
    # This is intentional — a more aggressive regex could corrupt prose.
    assert "See []() for context." == out


def test_markdown_link_with_special_chars_in_url_preserved_verbatim():
    """URLs with query strings and fragments must survive unchanged."""
    text = (
        "Read the [API docs](https://api.example.com/v1/docs?lang=en&fmt=md#section-2) "
        "for more."
    )
    out = normalize_content(text)
    assert "https://api.example.com/v1/docs?lang=en&fmt=md#section-2" in out
    assert "API docs" in out


def test_raw_url_without_brackets_left_untouched():
    """A bare URL without surrounding brackets must NOT be touched.
    Critical guard: a regex that touched bare URLs would corrupt prose
    like 'see https://example.com for more'."""
    text = "Read the docs at https://example.com/docs for more info."
    out = normalize_content(text)
    assert out == text


def test_raw_url_with_trailing_punctuation_preserved():
    """Common punctuation after a bare URL must not be eaten."""
    text = "See https://example.com. Also: https://example.com/page."
    out = normalize_content(text)
    assert out == text


def test_link_and_bare_url_on_same_line_both_preserved():
    """`[a](https://x) and https://y` — both survive."""
    text = "Read [the spec](https://spec.example.com) and https://docs.example.com for context."
    out = normalize_content(text)
    assert "the spec" in out
    assert "https://spec.example.com" in out
    assert "https://docs.example.com" in out
    assert "[" not in out


def test_link_inside_long_post_does_not_anchor_to_other_text():
    """A markdown link inside a long paragraph should not absorb
    surrounding text via greedy regex."""
    text = (
        "First we ship the [release](https://releases.example.com/v1). "
        "Then we monitor. Then we iterate."
    )
    out = normalize_content(text)
    assert "release" in out
    assert "https://releases.example.com/v1" in out
    assert "Then we monitor. Then we iterate." in out


def test_link_does_not_match_a_bracketed_word_without_parens():
    """`[foo]` (no parens, no url) is NOT a Markdown link and must be
    left alone — no regex must eat the brackets or the word."""
    text = "The word [foo] is in brackets."
    out = normalize_content(text)
    # We intentionally do NOT touch bare brackets here; they pass through.
    # The only stripping that happens is fenced blocks, headings, HR, etc.
    assert "foo" in out


def test_link_in_normalize_linkedin_post_end_to_end():
    """The full e2e function should also handle links."""
    post = normalize_linkedin_post(
        title="Releases",
        content=(
            "We shipped the [v1.0 release](https://releases.example.com/v1). "
            "Check the [API docs](https://api.example.com) for details."
        ),
        hashtags=["#Release"],
    )
    assert "[" not in post.content
    assert "v1.0 release" in post.content
    assert "https://releases.example.com/v1" in post.content
    assert "API docs" in post.content
    assert "https://api.example.com" in post.content
