"""HTML metadata extraction — Phase 8.

Stdlib-only HTML metadata extractor that surfaces the fields the
Writer needs to ground a post:

* ``title`` (already in the existing web adapter, but lifted out
  for reuse by future adapters)
* ``description`` (already)
* ``canonical_url`` — from ``<link rel="canonical">`` or the
  ``og:url`` meta
* ``author`` — from ``<meta name="author">`` or
  ``<meta property="article:author">``
* ``published_at`` — from the standard
  ``<meta property="article:published_time">``,
  ``og:article:published_time``, or
  ``<meta name="pubdate">`` tags
* ``site_name`` — from ``<meta property="og:site_name">``
* ``image`` — from ``<meta property="og:image">`` (not yet used by
  the Writer, but useful metadata)

The extractor is single-pass, uses only the standard library, and
NEVER throws. Malformed HTML is silently ignored. The output is
the set of metadata fields actually found — the Writer only sees
what the page legitimately declares.

The writer and reviewer NEVER use ``author`` to invent claims
about a "first-person experience" — author is a context field
for narrative angle, not an identity claim.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Optional


def _normalize_iso8601(value: str) -> Optional[str]:
    """Best-effort ISO-8601 normalization. The Writer and audit
    log only ever see the normalized value; a malformed date is
    silently dropped (we return None and the metadata is left
    empty)."""
    s = (value or "").strip()
    if not s:
        return None
    # ``Z`` suffix → ``+00:00`` for ``fromisoformat``.
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # The Writer only needs the date portion for "this article
    # was published on…". We keep the full ISO string for the
    # audit log.
    return dt.isoformat()


def _normalize_url(href: str, base: str) -> Optional[str]:
    """Resolve a relative href against the base URL, return
    ``None`` on parse failure or empty."""
    if not href:
        return None
    href = href.strip()
    if not href:
        return None
    from urllib.parse import urljoin, urlparse

    resolved = urljoin(base, href)
    parsed = urlparse(resolved)
    if parsed.scheme not in ("http", "https"):
        return None
    return resolved


class _MetadataExtractor(HTMLParser):
    """Single-pass metadata extractor. Writes the discovered
    fields onto a small mutable dict.

    The dict is passed in by the caller so multiple ``Metadata``
    objects can be merged if the caller wants to chain
    extractors.
    """

    def __init__(self, *, base_url: str, target: dict) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._target = target
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        if tag == "title":
            self._in_title = True
            return
        if tag == "meta":
            name = (attr_map.get("name") or "").lower()
            prop = (attr_map.get("property") or "").lower()
            content = (attr_map.get("content") or "").strip()
            if not content:
                return
            if name == "description" and not self._target.get("description"):
                self._target["description"] = content
            elif name == "author" and not self._target.get("author"):
                self._target["author"] = content
            elif name == "pubdate" and not self._target.get("published_at"):
                norm = _normalize_iso8601(content)
                if norm:
                    self._target["published_at"] = norm
            elif prop == "og:description" and not self._target.get("description"):
                self._target["description"] = content
            elif prop == "og:url" and not self._target.get("canonical_url"):
                norm = _normalize_url(content, self._base_url)
                if norm:
                    self._target["canonical_url"] = norm
            elif prop == "og:site_name" and not self._target.get("site_name"):
                self._target["site_name"] = content
            elif prop == "og:image" and not self._target.get("image"):
                norm = _normalize_url(content, self._base_url)
                if norm:
                    self._target["image"] = norm
            elif prop == "article:author" and not self._target.get("author"):
                self._target["author"] = content
            elif prop == "article:published_time" and not self._target.get("published_at"):
                norm = _normalize_iso8601(content)
                if norm:
                    self._target["published_at"] = norm
            return
        if tag == "link":
            rel = (attr_map.get("rel") or "").lower().split()
            href = attr_map.get("href") or ""
            if "canonical" in rel and href and not self._target.get("canonical_url"):
                norm = _normalize_url(href, self._base_url)
                if norm:
                    self._target["canonical_url"] = norm

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and not self._target.get("title"):
            existing = self._target.get("title") or ""
            self._target["title"] = (existing + " " + data).strip()


def extract_html_metadata(html: str, base_url: str) -> dict:
    """Run a single-pass metadata extraction over ``html``,
    returning a dict with the keys actually found.

    The returned dict never contains empty strings — only fields
    that the page legitimately declared.
    """
    target: dict = {}
    parser = _MetadataExtractor(base_url=base_url, target=target)
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — malformed HTML is silent
        pass
    # Drop empty values (defensive — should not happen).
    return {k: v for k, v in target.items() if v}


# Date the article was last modified, if visible in the URL
# (e.g. ``/2024/08/22/some-slug/``). This is a URL-pattern
# fallback when the page doesn't declare a date in <meta>.
_DATE_IN_PATH = re.compile(r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$)")


def date_in_path(url: str) -> Optional[str]:
    """Return an ISO-8601 date if the URL has a ``/YYYY/MM/DD/``
    segment, else ``None``. Used as a last-resort fallback for
    blogs whose HTML doesn't declare a publish date.
    """
    m = _DATE_IN_PATH.search(url or "")
    if not m:
        return None
    try:
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return dt.isoformat()


def merged_publish_date(metadata: dict, final_url: str) -> Optional[str]:
    """Return the best available publication date.

    Priority: ``published_at`` from the page meta → date in URL path
    → ``None`` (the page does not declare a date).
    """
    pa = metadata.get("published_at")
    if pa:
        return pa
    return date_in_path(final_url)
