"""Web-article source adapter — Phase 8D / P2 (the catch-all for URL→LinkedIn).

Fetches a public HTML page, extracts the readable article text using
stdlib only (no new dependencies — no ``trafilatura``, no ``beautifulsoup4``,
no ``readability-lxml``). Strips nav / ads / scripts / styles / footers
via simple structural heuristics.

Security:
  * Every outbound HTTP fetch goes through ``ssrf.safe_get`` (the same
    SSRF guard used by the GitHub adapter). Direct ``httpx.`` calls are
    forbidden by ``tests/test_security_ssrf_grep.py`` which greps the
    entire ``services/sources/`` directory.
  * Only ``http`` and ``https`` are accepted.
  * Only ports 80 / 443 are accepted.
  * IP-family vetting blocks loopback / private / link-local / multicast
    / reserved / unspecified / cloud-metadata addresses.
  * Manual redirect loop with the same SSRF re-validation per hop.
  * TLS verification is always on.

Source-type classification — we keep this deterministic and cheap:

  * ``github_*`` is handled by the existing GitHub adapter (registered
    BEFORE this module so first-match-wins resolves to it).
  * Every other accepted HTTP/HTTPS URL falls through to this adapter.
  * The adapter tags the package with ``source_type`` in metadata so the
    downstream Writer prompt can branch on it. ``webpage`` is the
    default; ``docs_site`` is set when the URL host matches a small
    static docs-host allowlist.

HTML extraction — stdlib only:

  1. Strip ``<script>`` / ``<style>`` / ``<noscript>`` / ``<svg>``.
  2. Drop obvious non-content blocks: ``<nav>``, ``<header>``,
     ``<footer>``, ``<aside>``, ``<form>``, ``<button>``, ``<iframe>``,
     ``<noscript>``.
  3. Prefer ``<article>`` → ``<main>`` → ``<body>`` as the content root.
  4. Within the root: keep ``<h1>``–``<h6>``, ``<p>``, ``<li>``, ``<blockquote>``.
  5. Convert ``<li>`` to ``• item`` (matches the LinkedIn-native
     bullet style the Writer already prefers).
  6. Collapse runs of whitespace.
  7. Stop at a hard byte cap (~25 KB) so we never ship a giant page
     to the LLM.

This is intentionally simple — the project already has the
trafilatura / bs4 escape hatches documented in the spec; we chose stdlib
to keep Phase 3 zero-dependency.
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from backend.app.services.sources.base import (
    BaseSourceAdapter,
    SourcePackage,
    SourceUnavailableError,
)
from backend.app.services.sources.metadata import (
    extract_html_metadata,
    merged_publish_date,
)
from backend.app.services.sources.quality import (
    SourceQuality,
    evaluate_source_quality,
    is_weak_or_failed,
    weak_source_user_message,
)
from backend.app.services.sources.registry import register_adapter
from backend.app.services.sources.ssrf import safe_get

logger = logging.getLogger(__name__)


# Hard cap on extracted text passed downstream (the writer LLM should
# never see a 200 KB page). Roughly ~25 KB which is enough for the
# first dozen paragraphs + headings of any reasonable article.
_MAX_TEXT_BYTES = 25 * 1024

# Domains that are likely documentation sites (helps the writer pick
# the right angle). Keep this list small and stable; the goal is not
# exhaustive classification.
_DOCS_HOSTS = frozenset(
    {
        "docs.python.org",
        "docs.djangoproject.com",
        "fastapi.tiangolo.com",
        "react.dev",
        "vuejs.org",
        "angular.io",
        "kubernetes.io",
        "docker.com",
        "redis.io",
        "postgresdocs.com",
    }
)


# Block-level tags that we want to skip entirely (nav / ads / chrome).
# These are stripped during extraction.
_DROP_TAGS = frozenset(
    {"script", "style", "noscript", "svg", "iframe"}
)
_SKIP_TAGS = frozenset(
    {"nav", "header", "footer", "aside", "form", "button"}
)
# Block-level content tags we keep as plain text.
_KEEP_BLOCK_TAGS = frozenset({"p", "li", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6"})
# Inline tags we drop without a newline.
_DROP_INLINE_TAGS = frozenset({"span", "b", "i", "u", "em", "strong", "em", "code", "a"})


class _WebArticleExtractor(HTMLParser):
    """Single-pass HTML → plain-text extractor.

    No external dependency. Emits tagged block separators so the writer
    sees clear paragraph boundaries.
    """

    _SEP = "\n\n"

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buf: List[str] = []
        self._depth_in_skip: int = 0
        self._depth_in_drop: int = 0
        self._capture_li: bool = False
        self._li_buf: List[str] = []

    def _emit(self, text: str) -> None:
        if not text:
            return
        if self._capture_li:
            self._li_buf.append(text)
        else:
            self._buf.append(text)

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in _DROP_TAGS:
            self._depth_in_drop += 1
            return
        if tag in _SKIP_TAGS:
            self._depth_in_skip += 1
            return
        if tag == "li":
            self._capture_li = True
            self._li_buf = []
            return
        if tag in ("br", "hr"):
            self._emit("\n")
            return
        if tag in _KEEP_BLOCK_TAGS:
            self._emit("\n\n")
        if tag in _DROP_INLINE_TAGS:
            pass

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _DROP_TAGS:
            if self._depth_in_drop > 0:
                self._depth_in_drop -= 1
            return
        if tag in _SKIP_TAGS:
            if self._depth_in_skip > 0:
                self._depth_in_skip -= 1
            return
        if tag == "li":
            if self._li_buf:
                bullet = " ".join(s.strip() for s in self._li_buf if s.strip())
                if bullet:
                    self._buf.append("• " + bullet + "\n")
            self._capture_li = False
            return
        if tag in ("p", "blockquote", "pre"):
            self._buf.append("\n\n")
        if tag in _KEEP_BLOCK_TAGS:
            self._buf.append("\n\n")

    def handle_data(self, data: str) -> None:
        if self._depth_in_drop > 0 or self._depth_in_skip > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._capture_li:
            self._li_buf.append(text)
            return
        self._buf.append(text + " ")

    def render(self) -> str:
        raw = "".join(self._buf)
        # Collapse whitespace runs.
        cleaned = re.sub(r"[ \t]+", " ", raw)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


class _HtmlTitleFinder(HTMLParser):
    """Tiny parser used only to read ``<title>`` and ``<meta name=description>``."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str = ""
        self.description: str = ""
        self._in_title: bool = False
        self._in_meta: bool = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
            return
        if tag == "meta":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            content = attr_map.get("content", "")
            if name == "description" or prop == "og:description":
                self.description = content
        if tag == "body":
            self._in_meta = False

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title = (self.title + " " + data).strip()


def extract_article(
    html: str,
    *,
    max_bytes: int = _MAX_TEXT_BYTES,
) -> Tuple[str, str, str]:
    """Return ``(title, description, plain_text)`` from raw ``html``.

    The ``plain_text`` is paragraph-broken plain text, capped at
    ``max_bytes``. Suitable to feed directly into the Writer prompt.
    """
    title_finder = _HtmlTitleFinder()
    try:
        title_finder.feed(html)
    except Exception:  # noqa: BLE001
        # Malformed HTML — ignore; fall back to empty title.
        pass
    title = (title_finder.title or "").strip()
    description = (title_finder.description or "").strip()

    extractor = _WebArticleExtractor()
    try:
        extractor.feed(html)
    except Exception as exc:  # noqa: BLE001
        raise SourceUnavailableError(
            f"HTML parse failed: {exc}",
            code="bad_response",
        ) from exc
    text = extractor.render()

    # Hard cap to keep the Writer prompt sane.
    if len(text.encode("utf-8")) > max_bytes:
        # Truncate at a paragraph boundary if possible.
        truncated = text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
        last_para = truncated.rfind("\n\n")
        if last_para > max_bytes // 2:
            text = truncated[:last_para]
        else:
            text = truncated
        text += "\n\n[… content truncated for brevity …]"

    return title, description, text


def _looks_like_docs_site(host: str) -> bool:
    return host.lower() in _DOCS_HOSTS


def _first_sentences(text: str, *, max_sentences: int = 2, max_chars: int = 400) -> str:
    """Return the first ``max_sentences`` sentences of ``text``
    that are not just structural noise. Used as a high-signal
    overview key fact when the page has no bullet items.
    """
    if not text:
        return ""
    out: list[str] = []
    # Walk the text in chunks bounded by sentence-ending
    # punctuation. We're not parsing — just splitting on
    # '. ' / '! ' / '? ' followed by an uppercase letter.
    buf = ""
    words = text.split()
    for word in words:
        buf = (buf + " " + word).strip() if buf else word
        if len(buf) >= max_chars and len(out) >= 1:
            break
        if buf.endswith((".", "!", "?")) and len(out) < max_sentences:
            out.append(buf)
            buf = ""
        if sum(len(s) for s in out) >= max_chars:
            break
    if buf and len(out) < max_sentences and len(buf) < max_chars:
        out.append(buf)
    return " ".join(s.strip() for s in out)[:max_chars].strip()


class WebArticleAdapter(BaseSourceAdapter):
    """Catch-all web-page adapter. Registered AFTER GitHub so
    GitHub-shaped URLs still resolve to :class:`GithubAdapter`."""

    name = "webpage"

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Accept any HTTP/HTTPS URL. The GitHub adapter registers
        earlier and wins for GitHub-shaped URLs."""
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)

    async def fetch(self, url: str, *, request_id: str) -> SourcePackage:
        # 1. Safe HTTP fetch (SSRF / DNS / redirect / size guarded).
        # 2.5 MB cap on HTML — bigger than any sane article.
        safe_response = await safe_get(
            url,
            max_bytes=2_500_000,
            timeout_seconds=15.0,
        )

        # 2. Content-type guard — bail if not HTML.
        ct = safe_response.headers.get("content-type", "").lower()
        if ct and not (
            "html" in ct
            or "xml" in ct
            or "text/plain" in ct
        ):
            raise SourceUnavailableError(
                f"Unsupported content-type: {ct}",
                code="not_html",
                details={"content_type": ct},
            )

        # 3. Decode bytes → str safely.
        encoding = "utf-8"
        try:
            html = safe_response.body.decode(encoding)
        except UnicodeDecodeError:
            encoding = "iso-8859-1"
            html = safe_response.body.decode(encoding, errors="replace")

        # 4. Extract title + description + clean plain text.
        title, description, text = extract_article(html)

        # 4b. Phase 8 — extract full metadata (canonical URL, author,
        # publish date, site name) in a single pass. Empty fields
        # are omitted; we never invent values.
        from urllib.parse import urlparse

        final_url = safe_response.final_url or url
        meta = extract_html_metadata(html, base_url=final_url)
        # ``extract_article`` may have found a more accurate
        # description in <meta> already; the metadata helper
        # filled the same key, so the union is consistent.
        if description and not meta.get("description"):
            meta["description"] = description
        if title and not meta.get("title"):
            meta["title"] = title
        # URL-path date fallback.
        if not meta.get("published_at"):
            meta["published_at"] = merged_publish_date(meta, final_url)

        if not text.strip():
            raise SourceUnavailableError(
                "Empty article body after extraction.",
                code="thin_content",
            )

        # 5. Build raw_results in the same shape the Writer expects:
        # raw_results[0] = overview, [1] = key facts, [2] = main
        # detail block.
        host = (urlparse(final_url).hostname or "").lower()
        source_type = "docs_site" if _looks_like_docs_site(host) else "webpage"

        # Pull a small set of key facts by scanning headings + first
        # paragraph. Cheap deterministic heuristics — no LLM call.
        key_facts: List[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("•"):
                key_facts.append(stripped)
            if len(key_facts) >= 5:
                break
        if not key_facts:
            # Fall back to first non-empty paragraph.
            for line in text.splitlines():
                stripped = line.strip()
                if stripped and len(stripped) > 40:
                    key_facts = [stripped[:200]]
                    break

        # Phase 8 — also harvest the first 1-3 sentences of the
        # body as an "overview" key fact if the heuristic didn't
        # find any bullet items. This gives the Writer a
        # higher-signal first key fact than the raw body.
        if not key_facts:
            overview = _first_sentences(text, max_sentences=2, max_chars=400)
            if overview:
                key_facts = [overview]

        raw_results: List[dict] = [
            {
                "title": title or source_type.title(),
                "url": final_url,
                "snippet": (description or text[:280]).strip(),
            },
            {
                "title": "Key facts",
                "url": final_url,
                "snippet": "\n".join(key_facts) if key_facts else text[:280],
            },
            {
                "title": "Detail block",
                "url": final_url,
                "snippet": text[:1200],
            },
        ]

        # Phase 8 — quality gate. A WEAK package is still returned
        # (so the preview can show the user what was extracted),
        # but the metadata carries ``quality`` + ``quality_reason``
        # so the API layer can refuse to generate against a WEAK
        # source.
        package = SourcePackage(
            title=title or "Web Article",
            summary=description or text[:600],
            key_facts=key_facts,
            raw_results=raw_results,
            metadata={
                "url": final_url,
                "adapter": self.name,
                "request_id": request_id,
                "topic_hint": title or source_type,
                "source_type": source_type,
                "host": host,
                # Project the discovered metadata so the source
                # context for the Writer / Draft attribution card
                # has it.
                **meta,
            },
        )
        quality, reason = evaluate_source_quality(package)
        package.metadata["quality"] = quality.value
        package.metadata["quality_reason"] = reason
        package.metadata["body_char_count"] = len(text)
        # If the source is WEAK or FAILED, we still return the
        # package so the preview can render it — but the API layer
        # should refuse to generate against it. The downstream
        # check is in ``_generate_from_source`` / source preview
        # endpoint.
        return package


# Register at import time. WebArticleAdapter must be registered
# BEFORE StubSourceAdapter (which catches everything). The github
# adapter registers BEFORE this one so GitHub URLs still go there.
register_adapter(WebArticleAdapter)


__all__ = ["WebArticleAdapter", "extract_article"]
