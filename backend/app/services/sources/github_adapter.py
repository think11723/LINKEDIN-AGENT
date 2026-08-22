"""GitHub source adapter — Phase 8D / P1.

Fetches and analyzes a public GitHub repository via the GitHub REST
API, producing a structured ``SourcePackage`` that flows into the
existing writer/reviewer pipeline (P0).

Security contract:
  * All outbound HTTP goes through ``ssrf.safe_get`` (the P0 SSRF
    guard). No direct ``httpx.`` / ``requests.`` calls.
  * The allowlist ``GITHUB_ALLOWLIST`` (defined in ``ssrf.py``) is
    passed to every call. The P0 IP-pinning, redirect validation,
    and TLS hostname-verification apply automatically.
  * TLS verification is never disabled.
  * No file is fetched unless its path is on a hardcoded whitelist
    of signal-bearing manifest/dependency files. User-supplied URL
    paths are stripped to ``owner/repo`` before any HTTP call — no
    arbitrary subdirectory or file is requested.

URL form (decision 1 — option b, 2026-08-13):
  * ``https://github.com/owner/repo`` and ``.../repo/`` are accepted.
  * ``.../tree/...`` and ``.../blob/...`` subpaths are accepted but
    normalized to the repo root before fetching — the URL's trailing
    path is ignored.
  * ``.../issues/...``, ``.../pull/...``, ``.../actions/...``,
    ``.../discussions/...``, and other non-repo-root paths are
    rejected with ``SourceUnavailableError(code="unsupported_url_form")``.
  * ``.../orgs/...``, ``.../users/...``, ``.../settings/...`` etc. are
    also rejected.
  * URLs without a repo segment (``https://github.com/owner_only``)
    are rejected with ``SourceUnavailableError(code="unsupported_url_form")``.

Error mapping (per plan §9):
  * 200 OK → use response.
  * 404 → ``repository_not_found``.
  * 401 (with token set) → ``github_unauthorized``.
  * 403 + ``X-RateLimit-Remaining: 0`` → ``github_rate_limited``
    (with ``retry_after`` from ``X-RateLimit-Reset`` in ``details``).
  * 403 (other) → ``github_forbidden``.
  * 451 → ``SourceBlockedError(code="dmca")`` (do not leak DMCA reason).
  * 5xx → ``http_5xx``.
  * timeout → ``timeout``.
  * Malformed JSON → ``bad_response``.
  * Archived/disabled (HTTP 200) → succeed with
    ``metadata.archived=True`` / ``metadata.disabled=True``.
  * Empty repo → succeed with ``metadata.minimal=True``.

Authentication (decision not gated):
  * Public repos work without a token.
  * Optional ``GITHUB_TOKEN`` env var (read via
    ``backend.app.core.config.get_settings().github_token``) is sent
    on every call as ``Authorization: Bearer <token>``.

The adapter never makes an LLM call. Analysis is deterministic
(template-driven, evidence-bound) so a draft can never claim a
fact that the source does not contain.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.core.config import get_settings
from backend.app.services.sources.base import (
    BaseSourceAdapter,
    SourceBlockedError,
    SourceFetchError,
    SourcePackage,
    SourceUnavailableError,
)
from backend.app.services.sources.ssrf import (
    GITHUB_ALLOWLIST,
    SafeResponse,
    safe_get,
)

logger = logging.getLogger(__name__)


#: Per-call byte caps (the adapter's own internal budgets, layered
#: on top of the P0 ``source_github_max_bytes`` cumulative cap).
_CALL_CAP_REPO_META = 128 * 1024  # 128 KB
_CALL_CAP_README = 512 * 1024  # 512 KB raw
_README_TEXT_CAP = 40_000  # 40 000 chars of README text after decode
_CALL_CAP_LANGUAGES = 32 * 1024  # 32 KB
_CALL_CAP_CONTENTS = 256 * 1024  # 256 KB
_CALL_CAP_RELEASES = 128 * 1024  # 128 KB
_CALL_CAP_MANIFEST = 32 * 1024  # 32 KB per manifest file
_MAX_MANIFEST_FILES = 5

#: Hard denylist of file names that are NEVER fetched. Mirrors the
#: plan §7. File names that match any of these are skipped.
_DENYLIST_EXACT = frozenset(
    {
        ".env",
        ".envrc",
        ".npmrc",
        ".pypirc",
        "id_rsa",
        "id_rsa.pub",
        "secrets",
        "secrets.txt",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.lock",
        "Gemfile.lock",
        "poetry.lock",
        "Cargo.lock",
        "go.sum",
    }
)
_DENYLIST_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".cer",
    ".crt",
    ".der",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".o",
    ".a",
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".pyc",
    ".pyo",
    ".pyd",
    ".beam",
    ".elc",
)
_DENYLIST_GLOBS = (
    ".env*",  # any file starting with .env
    "*.lock",
    "*.log",
    "*.pid",
    "*.seed",
    "*.swp",
    "*.bak",
    "*.tmp",
    "*.tar",
    "*.tar.gz",
    "*.tgz",
    "*.tar.bz2",
    "*.zip",
    "*.7z",
    "*.rar",
    "*.pdf",
    "*.png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".mp4",
    ".mov",
    ".mp3",
    ".wav",
    ".flac",
    ".ogg",
    ".webm",
    ".wasm",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".o",
    ".a",
    ".class",
    ".jar",
    ".war",
    ".ear",
    ".pyc",
    ".pyo",
    ".pyd",
    ".beam",
    ".elc",
)
_DENYLIST_DIRS = frozenset(
    {
        ".git",
        ".github",
        ".svn",
        ".hg",
        "node_modules",
        "bower_components",
        "jspm_packages",
        "vendor",
        "venv",
        ".venv",
        "env",
        ".env",
        "virtualenv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".nox",
        "build",
        "dist",
        "out",
        "target",
        "bin",
        "obj",
        "coverage",
        "htmlcov",
        ".next",
        ".nuxt",
        ".svelte-kit",
        "node_modules",
        "Pods",
    }
)

#: Signal-bearing whitelist (priority order). Max ``_MAX_MANIFEST_FILES``
#: files are fetched from a repo's top-level listing.
_WHITELIST_PRIORITY = [
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "build.sbt",
    "Gemfile",
    "composer.json",
    "pyrightconfig.json",
    "mypy.ini",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "CHANGELOG.md",
    "CHANGELOG.rst",
    "CONTRIBUTING.md",
    "ARCHITECTURE.md",
    "ROADMAP.md",
]


# ---------------------------------------------------------------------------
# URL recognition
# ---------------------------------------------------------------------------


#: Strict ``github.com`` (or ``www.github.com``) repo path matcher.
#:
#: The regex captures ``owner``, ``repo``, and a trailing ``rest``
#: path. We accept any URL on the github.com host as long as the
#: path begins with ``/{owner}/{repo}`` (with optional trailing
#: slash and optional subpath). Subpaths are accepted (decision 1
#: option b — normalize to repo root) but the trailing path is
#: discarded when fetching.
#
#: Examples:
#:   /owner/repo            → owner, repo, rest=""
#:   /owner/repo/           → owner, repo, rest=""
#:   /owner/repo/tree/main  → owner, repo, rest="tree/main"
#:   /owner/repo/blob/x/y   → owner, repo, rest="blob/x/y"
_REPO_PATH_RE = re.compile(
    r"^/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)/"
    r"(?P<repo>[A-Za-z0-9._-]+)/?(?P<rest>.*)$"
)

#: Path prefixes that indicate a NON-repository-root page. Accepted
#: URL paths must NOT begin with any of these.
_UNSUPPORTED_PREFIXES = (
    "issues/",
    "issue/",
    "pull/",
    "pulls/",
    "discussions/",
    "actions/",
    "security/",
    "wiki/",
    "settings/",
    "pulse/",
    "graphs/",
    "network/",
    "stargazers",
    "watchers",
    "forks",
    "network/members",
    "projects/",
    "milestones/",
    "labels/",
    "compare/",
    "blame/",
    "raw/",
    "commit/",
    "commits/",
    "tags/",
    "releases/tag/",
    "tree/",  # normalized away — must be followed by more
    "blob/",  # normalized away — must be followed by more
    "search?",
    "find/",
    "notifications",
    "invitations",
    "join",
    "contact",
    "about",
    "pricing",
    "features",
    "enterprise",
    "team",
    "customer-stories",
    "security/overview",
    "sponsors/",
    "orgs/",
    "users/",
    "stars/",
    "trending",
    "marketplace",
    "explore",
    "topics/",
    "collections/",
    "events/",
    "login",
    "logout",
    "signup",
    "new/",
    "import/",
    "codespaces/",
    "account/",
    "settings/",
)

#: Reserved top-level paths that are never repository paths.
_RESERVED_TOP_PATHS = frozenset(
    {
        "orgs",
        "users",
        "stars",
        "trending",
        "marketplace",
        "explore",
        "topics",
        "collections",
        "events",
        "login",
        "logout",
        "signup",
        "new",
        "import",
        "codespaces",
        "account",
        "settings",
        "pricing",
        "features",
        "enterprise",
        "team",
        "customer-stories",
        "security",
        "sponsors",
        "about",
        "contact",
        "notifications",
        "dashboard",
        "home",
    }
)


def _normalize_github_path(rest: str) -> Tuple[bool, str]:
    """Validate and normalize a GitHub URL's path tail.

    Returns ``(True, "")`` for an acceptable repository root, or
    ``(True, "tree/main")`` if the path contained a normalized
    subpath (decision 1 — option b). Returns ``(False, reason)`` for
    paths that are explicitly unsupported.
    """
    if not rest:
        return True, ""
    segments = [s for s in rest.split("/") if s]
    if not segments:
        return True, ""
    first = segments[0].lower()
    if first in _RESERVED_TOP_PATHS:
        return False, "reserved_path"
    # Special accepted subpaths that normalise away to the repo root.
    if first in {"tree", "blob"}:
        return True, ""  # any /tree/... or /blob/... collapses to root
    if first in {"raw"}:
        return True, ""  # /raw/... also collapses
    if first.startswith("?"):
        return False, "unsupported_url_form"
    # Same accepted list as can_handle (decision 1, option b).
    if first in {
        "tree",
        "blob",
        "raw",
        "issues",
        "issue",
        "pulls",
        "pull",
        "discussions",
        "actions",
    }:
        return True, ""  # accepted but normalised to root
    return False, "unsupported_url_form"


# ---------------------------------------------------------------------------
# Byte budget
# ---------------------------------------------------------------------------


@dataclass
class _ByteBudget:
    """Cumulative byte counter for the GitHub adapter.

    Threaded through every call; when exhausted, remaining calls are
    skipped (not failed) and the abandonment is recorded.
    """

    limit: int
    used: int = 0
    skipped: List[str] = field(default_factory=list)

    def can_consume(self, n: int) -> bool:
        return self.used + n <= self.limit

    def consume(self, n: int) -> None:
        self.used += n

    def skip(self, name: str) -> None:
        self.skipped.append(name)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class GitHubSourceAdapter(BaseSourceAdapter):
    """Adapter for public GitHub repositories.

    Discovery (``can_handle``) is a strict regex match; no network
    call is made. Fetch (``fetch``) issues up to six
    ``safe_get`` calls (five for the public API + up to five
    manifest files via sparse call 6). All analysis is deterministic.
    """

    name = "github"

    # Root-level pages that are accepted (everything else is rejected).
    _ACCEPTED_ROOT_PAGES = frozenset(
        {
            "tree",  # /tree/...  — normalises to root
            "blob",  # /blob/...  — normalises to root
            "raw",  # /raw/...   — normalises to root
            "issues",
            "issue",
            "pulls",
            "pull",
            "discussions",
            "actions",
        }
    )

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Cheap, sync, no network.

        Accepted (decision 1 — option b):
          * ``https://github.com/owner/repo`` and ``.../repo/`` (repo root).
          * ``/tree/...``, ``/blob/...``, ``/raw/...`` — normalised to
            root before fetching.
          * ``/issues``, ``/issue``, ``/pulls``, ``/pull``,
            ``/discussions``, ``/actions`` — root-level list pages,
            normalised to root.

        Rejected (raise ``unsupported_url_form`` at fetch time):
          * ``/orgs/...``, ``/users/...``, ``/settings/...``,
            ``/marketplace``, ``/trending``, ``/explore``,
            ``/sponsors/...``, ``/notifications``, ``/stars/...``,
            ``/login``, ``/features``, ``/enterprise``, ``/pricing``
            and any other reserved top-level path.
          * Any non-repo subpath that is not in the accepted list
            above (``/wiki``, ``/pulse``, ``/graphs/...``,
            ``/network/...``, ``/projects/...``, ``/compare/...``,
            ``/blame/...``, ``/commits/...``, ``/releases``, ``/tags``,
            ``/security/...``, ``/search?...``, etc.).
        """
        parsed = _safe_parse(url)
        if parsed is None:
            return False
        host, path = parsed
        if host not in {"github.com", "www.github.com"}:
            return False
        m = _REPO_PATH_RE.match(path)
        if not m:
            return False
        owner = (m.group("owner") or "").lower()
        repo = (m.group("repo") or "").lower()
        # Reject reserved top-level ``owner`` segments. The regex is
        # too permissive — ``/orgs/owner`` matches with
        # owner="orgs", repo="owner". The owner segment must be a
        # plausible GitHub username.
        if owner in _RESERVED_TOP_PATHS:
            return False
        if repo in _RESERVED_TOP_PATHS:
            return False
        rest = (m.group("rest") or "").strip("/")
        if not rest:
            return True
        first = rest.split("/", 1)[0].lower()
        if first in _RESERVED_TOP_PATHS:
            return False
        return first in cls._ACCEPTED_ROOT_PAGES

    async def fetch(self, url: str, *, request_id: str) -> SourcePackage:
        owner, repo = _parse_owner_repo(url)
        settings = get_settings()
        budget = _ByteBudget(limit=settings.source_github_max_bytes)

        # The five public API calls plus up to five sparse manifest
        # fetches. Calls 1, 3, 4, 5 are issued in parallel via
        # ``asyncio.gather``; call 2 (README) is awaited sequentially
        # because the analyzer needs its content. Sparse manifest
        # fetches are sequential too — they consume the same budget.
        meta_task = asyncio.create_task(
            self._fetch_repo_meta(owner, repo, budget, request_id)
        )
        languages_task = asyncio.create_task(
            self._fetch_languages(owner, repo, budget, request_id)
        )
        contents_task = asyncio.create_task(
            self._fetch_top_contents(owner, repo, budget, request_id)
        )
        releases_task = asyncio.create_task(
            self._fetch_releases(owner, repo, budget, request_id)
        )
        meta_resp, languages_resp, contents_resp, releases_resp = (
            await asyncio.gather(
                meta_task, languages_task, contents_task, releases_task
            )
        )
        readme_resp = await self._fetch_readme(
            owner, repo, budget, request_id
        )

        # Manifest fetch is driven by the contents listing (so we
        # know which whitelist names are actually present).
        manifest_contents = await self._fetch_manifests(
            owner, repo, contents_resp, budget, request_id
        )

        # Build the SourcePackage deterministically.
        return self._analyze(
            meta=meta_resp,
            readme=readme_resp,
            languages=languages_resp,
            contents=contents_resp,
            releases=releases_resp,
            manifest_contents=manifest_contents,
            source_url=url,
            owner=owner,
            repo=repo,
            request_id=request_id,
            budget=budget,
        )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _headers() -> Dict[str, str]:
        """Build the common GitHub API headers.

        ``Authorization`` is added only when ``GITHUB_TOKEN`` is set.
        The token is read once at call time so tests can monkeypatch
        the settings object.
        """
        h: Dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "linkedin-agent/1.0",
        }
        token = get_settings().github_token
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def _get(
        self,
        url: str,
        *,
        max_bytes: int,
        timeout: float,
        budget: _ByteBudget,
        call_name: str,
    ) -> Optional[SafeResponse]:
        """Single ``safe_get`` with budget enforcement.

        Returns ``None`` if the budget is exhausted (the call is
        skipped — not failed). Raises the standard SSRF error
        hierarchy for protocol-level problems.
        """
        if not budget.can_consume(max_bytes):
            budget.skip(call_name)
            return None
        try:
            response = await safe_get(
                url,
                max_bytes=max_bytes,
                timeout_seconds=timeout,
                allow_hosts=GITHUB_ALLOWLIST,
                extra_headers=self._headers(),
            )
        except SourceBlockedError:
            # Re-raise — SSRF is a security concern, never silenced.
            raise
        except SourceFetchError:
            # Re-raise other source errors (timeout, etc.) — they
            # flow into the runner's error mapping.
            raise
        budget.consume(len(response.body))
        return response

    # ------------------------------------------------------------------
    # Individual API calls
    # ------------------------------------------------------------------

    async def _fetch_repo_meta(
        self, owner: str, repo: str, budget: _ByteBudget, request_id: str
    ) -> Dict[str, Any]:
        """``GET /repos/{o}/{r}`` — repository metadata."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        response = await self._get(
            url,
            max_bytes=_CALL_CAP_REPO_META,
            timeout=20.0,
            budget=budget,
            call_name="repo_meta",
        )
        if response is None:
            return {}
        return _parse_json(response, call_name="repo_meta") or {}

    async def _fetch_readme(
        self, owner: str, repo: str, budget: _ByteBudget, request_id: str
    ) -> Dict[str, Any]:
        """``GET /repos/{o}/{r}/readme`` — base64 README content.

        A 404 here means "this repo has no README" — distinct from
        "the repo does not exist" (which would be a 404 on
        ``/repos/{o}/{r}`` itself). Return empty data instead of
        raising so the fetch can succeed for README-less repos.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        response = await self._get(
            url,
            max_bytes=_CALL_CAP_README,
            timeout=20.0,
            budget=budget,
            call_name="readme",
        )
        if response is None:
            return {}
        if response.status_code == 404:
            return {"text": "", "truncated": False, "name": "", "encoding": ""}
        data = _parse_json(response, call_name="readme")
        if not data:
            return {}
        try:
            encoded = data.get("content", "")
            text = base64.b64decode(encoded).decode(
                "utf-8", errors="replace"
            )
        except (binascii.Error, ValueError, TypeError):
            text = ""
        truncated = False
        # Phase 8 — clean the README (strip badge noise, decorative
        # image lines, link-only lines) BEFORE truncating. The cleaner
        # is deterministic and never rewrites content; it only
        # removes UI noise that adds no semantic value to the LLM.
        from backend.app.services.sources.readme import clean_readme
        cleaned = clean_readme(text, max_chars=_README_TEXT_CAP)
        if cleaned != text:
            truncated = True
            text = cleaned
        else:
            if len(text) > _README_TEXT_CAP:
                text = _truncate_at_paragraph(text, _README_TEXT_CAP)
                truncated = True
        return {
            "text": text,
            "truncated": truncated,
            "name": data.get("name", ""),
            "encoding": "base64",
        }

    async def _fetch_languages(
        self, owner: str, repo: str, budget: _ByteBudget, request_id: str
    ) -> Dict[str, int]:
        """``GET /repos/{o}/{r}/languages`` — language byte counts."""
        url = f"https://api.github.com/repos/{owner}/{repo}/languages"
        response = await self._get(
            url,
            max_bytes=_CALL_CAP_LANGUAGES,
            timeout=20.0,
            budget=budget,
            call_name="languages",
        )
        if response is None:
            return {}
        data = _parse_json(response, call_name="languages")
        if not isinstance(data, dict):
            return {}
        # Each key is a language name; value is bytes-of-code.
        coerced: Dict[str, int] = {}
        for k, v in data.items():
            try:
                coerced[k] = int(v)
            except (TypeError, ValueError):
                continue
        return coerced

    async def _fetch_top_contents(
        self, owner: str, repo: str, budget: _ByteBudget, request_id: str
    ) -> List[Dict[str, Any]]:
        """``GET /repos/{o}/{r}/contents/`` — top-level listing only."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/"
        response = await self._get(
            url,
            max_bytes=_CALL_CAP_CONTENTS,
            timeout=20.0,
            budget=budget,
            call_name="contents",
        )
        if response is None:
            return []
        data = _parse_json(response, call_name="contents")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    async def _fetch_releases(
        self, owner: str, repo: str, budget: _ByteBudget, request_id: str
    ) -> List[Dict[str, Any]]:
        """``GET /repos/{o}/{r}/releases?per_page=5`` — recent releases."""
        url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"
        response = await self._get(
            url,
            max_bytes=_CALL_CAP_RELEASES,
            timeout=20.0,
            budget=budget,
            call_name="releases",
        )
        if response is None:
            return []
        data = _parse_json(response, call_name="releases")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    async def _fetch_manifests(
        self,
        owner: str,
        repo: str,
        contents: List[Dict[str, Any]],
        budget: _ByteBudget,
        request_id: str,
    ) -> Dict[str, str]:
        """Sparse call 6: fetch selected manifest files via the
        contents API. Up to ``_MAX_MANIFEST_FILES`` files, each capped
        at ``_CALL_CAP_MANIFEST`` bytes.
        """
        if not contents:
            return {}

        # Filter to the top-level files (skip dirs, denylisted names).
        eligible: List[Dict[str, Any]] = []
        for item in contents:
            if item.get("type") != "file":
                continue
            name = (item.get("name") or "").strip()
            if not name or not _is_safe_manifest_name(name):
                continue
            eligible.append(item)

        # Sort by whitelist priority, then by name (stable).
        priority_map = {n: i for i, n in enumerate(_WHITELIST_PRIORITY)}

        def _sort_key(item: Dict[str, Any]) -> Tuple[int, str]:
            return (priority_map.get(item.get("name", ""), 9999), item.get("name", ""))

        eligible.sort(key=_sort_key)
        eligible = eligible[:_MAX_MANIFEST_FILES]

        # Fetch each in sequence; abort on budget exhaustion.
        results: Dict[str, str] = {}
        for item in eligible:
            name = item["name"]
            # Path traversal guard: name must be a single segment.
            if "/" in name or "\\" in name or name in {".", ".."}:
                continue
            download_url = item.get("download_url")
            if not download_url:
                # Fall back to the ``html_url`` (no raw content) — the
                # dependency parser cannot use that. Skip.
                continue
            # ``download_url`` may target ``raw.githubusercontent.com``
            # which is in the allowlist.
            response = await self._get(
                download_url,
                max_bytes=_CALL_CAP_MANIFEST,
                timeout=20.0,
                budget=budget,
                call_name=f"manifest:{name}",
            )
            if response is None:
                # Budget exhausted; stop fetching manifests.
                break
            try:
                results[name] = response.body.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
        return results

    # ------------------------------------------------------------------
    # Deterministic analyzer
    # ------------------------------------------------------------------

    def _analyze(
        self,
        *,
        meta: Dict[str, Any],
        readme: Dict[str, Any],
        languages: Dict[str, int],
        contents: List[Dict[str, Any]],
        releases: List[Dict[str, Any]],
        manifest_contents: Dict[str, str],
        source_url: str,
        owner: str,
        repo: str,
        request_id: str,
        budget: _ByteBudget,
    ) -> SourcePackage:
        """Deterministic analyzer — no LLM calls.

        Produces a :class:`SourcePackage` from typed fields only.
        Every claim is anchored to repository evidence (the GitHub
        API response, the README text, or the manifest contents).
        """
        full_name = meta.get("full_name") or f"{owner}/{repo}"
        description = (meta.get("description") or "").strip()
        homepage = (meta.get("homepage") or "").strip() or None
        default_branch = meta.get("default_branch") or "main"
        stars = int(meta.get("stargazers_count") or 0)
        forks = int(meta.get("forks_count") or 0)
        watchers = int(meta.get("subscribers_count") or 0)
        open_issues = int(meta.get("open_issues_count") or 0)
        topics = list(meta.get("topics") or [])
        archived = bool(meta.get("archived"))
        disabled = bool(meta.get("disabled"))
        license_spdx = ((meta.get("license") or {}).get("spdx_id")) or None
        created_at = meta.get("created_at")
        updated_at = meta.get("updated_at")
        pushed_at = meta.get("pushed_at")
        primary_language = meta.get("language") or None
        owner_obj = meta.get("owner") or {}
        owner_login = owner_obj.get("login") or owner
        owner_avatar = owner_obj.get("avatar_url") or None

        # Languages: convert bytes to percentages.
        language_pcts: List[Tuple[str, float]] = []
        if languages:
            total = sum(languages.values()) or 1
            for name, n in sorted(
                languages.items(), key=lambda kv: kv[1], reverse=True
            )[:5]:
                language_pcts.append((name, round(100.0 * n / total, 1)))

        # Contents: top-level directories + the 5 important files.
        top_dirs: List[str] = []
        important_files: List[str] = []
        for item in contents:
            name = item.get("name") or ""
            if not name:
                continue
            t = item.get("type")
            if t == "dir" and name not in _DENYLIST_DIRS:
                top_dirs.append(name)
            elif t == "file" and _is_safe_manifest_name(name):
                important_files.append(name)
        top_dirs = top_dirs[:10]
        important_files = important_files[:_MAX_MANIFEST_FILES]

        # Days-since-last-push string for the summary.
        days_since_push: Optional[int] = None
        if pushed_at:
            try:
                pushed_dt = _parse_iso8601(pushed_at)
                if pushed_dt is not None:
                    delta = datetime.now(timezone.utc) - pushed_dt
                    days_since_push = max(0, delta.days)
            except Exception:  # noqa: BLE001
                days_since_push = None

        # Releases — newest first; cap at 5.
        release_summaries: List[Dict[str, Any]] = []
        for r in releases[:5]:
            release_summaries.append(
                {
                    "tag": r.get("tag_name") or "",
                    "name": r.get("name") or "",
                    "published_at": r.get("published_at"),
                    "body": (r.get("body") or "")[:500],
                }
            )

        # README: sections + first substantive paragraph.
        readme_text: str = readme.get("text", "")
        readme_sections: List[str] = _extract_markdown_headings(readme_text)
        readme_first_para: str = _extract_first_paragraph(readme_text)

        # Dependencies from manifests.
        dependencies = _parse_all_dependencies(manifest_contents)

        # Key facts — drawn from typed fields, never invented.
        key_facts: List[str] = []
        if stars or forks:
            key_facts.append(
                f"{stars:,} stars and {forks:,} forks on GitHub"
            )
        if primary_language and language_pcts:
            top = language_pcts[0]
            other = (
                f", {language_pcts[1][1]}% {language_pcts[1][0]}"
                if len(language_pcts) > 1
                else ""
            )
            key_facts.append(
                f"Top language: {top[0]} at {top[1]}%{other}"
            )
        if license_spdx and license_spdx != "NOASSERTION":
            key_facts.append(f"Licensed under {license_spdx}")
        if topics:
            key_facts.append(
                f"GitHub topics: {', '.join(topics[:3])}"
            )
        if release_summaries and release_summaries[0].get("tag"):
            rel = release_summaries[0]
            key_facts.append(
                f"Latest release: {rel['tag']}"
                + (
                    f" ({rel['published_at'][:10]})"
                    if rel.get("published_at")
                    else ""
                )
            )
        if days_since_push is not None:
            if archived and disabled:
                key_facts.append("Archived and disabled — not maintained")
            elif archived:
                key_facts.append("Archived — no longer maintained")
            elif disabled:
                key_facts.append("Disabled — not maintained")
            elif days_since_push <= 30:
                key_facts.append(
                    f"Actively maintained — last push {days_since_push} "
                    f"day{'s' if days_since_push != 1 else ''} ago"
                )
            else:
                key_facts.append(
                    f"Last push was {days_since_push} days ago"
                )
        elif archived:
            key_facts.append("Archived — no longer maintained")
        elif disabled:
            key_facts.append("Disabled — not maintained")
        # Detect an empty repository from the raw inputs (before
        # the key_facts list is built). When the repo has nothing
        # meaningful to describe, replace any tentative key facts
        # with the single empty-repo indicator so the post is honest.
        is_minimal = not (description or languages or contents or readme_text)
        if is_minimal:
            key_facts = ["An empty GitHub repository."]
        # Cap at 7 facts, each <= 25 words.
        key_facts = _cap_facts(key_facts, max_count=7, max_words=25)

        # Summary — templated.
        summary = _build_summary(
            description=description,
            primary_language=primary_language,
            language_pcts=language_pcts,
            stars=stars,
            forks=forks,
            license_spdx=license_spdx,
            days_since_push=days_since_push,
            archived=archived,
            disabled=disabled,
            is_minimal=is_minimal,
        )

        # raw_results ordering — first 3 are the writer contract.
        raw_results: List[Dict[str, str]] = []
        overview_snippet = _truncate(
            f"{description}. {language_pcts[0][0] if language_pcts else '—'}: "
            f"{language_pcts[0][1] if language_pcts else 0}%. {stars:,} stars.",
            200,
        )
        raw_results.append(
            {
                "title": full_name,
                "url": source_url,
                "snippet": overview_snippet,
            }
        )
        facts_snippet = _truncate(
            " • ".join(key_facts[:5]) if key_facts else "No facts.",
            200,
        )
        raw_results.append(
            {
                "title": "Key facts",
                "url": source_url,
                "snippet": facts_snippet,
            }
        )
        arch_parts: List[str] = []
        if top_dirs:
            arch_parts.append(f"Top-level: {', '.join(top_dirs)}")
        if important_files:
            arch_parts.append(
                f"Key files: {', '.join(important_files[:3])}"
            )
        arch_snippet = _truncate(
            ". ".join(arch_parts) if arch_parts else "Standard repo layout.",
            200,
        )
        raw_results.append(
            {
                "title": "Architecture",
                "url": source_url,
                "snippet": arch_snippet,
            }
        )
        if readme_first_para:
            raw_results.append(
                {
                    "title": "README excerpt",
                    "url": source_url,
                    "snippet": _truncate(readme_first_para, 200),
                }
            )
        if release_summaries and release_summaries[0].get("tag"):
            rel = release_summaries[0]
            rel_snippet = (
                f"{rel['tag']}"
                + (f" — {rel.get('name', '')}" if rel.get("name") else "")
            )
            raw_results.append(
                {
                    "title": "Latest release",
                    "url": source_url,
                    "snippet": _truncate(rel_snippet, 200),
                }
            )
        # Append dependencies summary if any.
        if dependencies:
            dep_summary = _format_dependencies_summary(dependencies)
            if dep_summary:
                raw_results.append(
                    {
                        "title": "Dependencies",
                        "url": source_url,
                        "snippet": _truncate(dep_summary, 200),
                    }
                )

        # Title: prefer a short ``owner/repo: tag``.
        title = full_name
        if description:
            short = _truncate(description, 60).rstrip(".")
            if short:
                title = f"{full_name}: {short}"

        metadata: Dict[str, Any] = {
            "url": source_url,
            "canonical_url": f"https://github.com/{owner}/{repo}",
            "adapter": "github",
            "owner": owner_login,
            "repo": repo,
            "full_name": full_name,
            "description": description,
            "homepage": homepage,
            "default_branch": default_branch,
            "primary_language": primary_language,
            "languages": {lang: pct for lang, pct in language_pcts},
            "topics": topics,
            "stars": stars,
            "forks": forks,
            "watchers": watchers,
            "open_issues": open_issues,
            "license": license_spdx,
            "created_at": created_at,
            "updated_at": updated_at,
            "pushed_at": pushed_at,
            "days_since_push": days_since_push,
            "archived": archived,
            "disabled": disabled,
            "important_files": important_files,
            "important_file_contents": manifest_contents,
            "dependencies": dependencies,
            "readme_summary": readme_first_para,
            "readme_sections": readme_sections,
            "releases": release_summaries,
            "truncated": bool(readme.get("truncated", False)),
            "analyzer": "deterministic",
            "bytes_fetched": budget.used,
            "skipped_calls": list(budget.skipped),
            "request_id": request_id,
            "owner_avatar_url": owner_avatar,
            # True when the repository has nothing meaningful to describe
            # (no description, no languages, no contents, no README).
            "minimal": is_minimal,
        }
        # Topic hint for the writer.
        if description:
            metadata["topic_hint"] = (
                f"GitHub repository {full_name}: {description[:120]}"
            )
        else:
            metadata["topic_hint"] = f"GitHub repository {full_name}"

        package = SourcePackage(
            title=title,
            summary=summary,
            key_facts=key_facts,
            raw_results=raw_results,
            metadata=metadata,
        )
        # Phase 8 — quality gate. A minimal GitHub repository
        # (no description, no language, no README, no topics) is
        # ``WEAK`` and the API layer will refuse to generate against
        # it. We still return the package so the preview can show
        # the user what was extracted.
        from backend.app.services.sources.quality import (
            SourceQuality,
            evaluate_source_quality,
        )
        quality, reason = evaluate_source_quality(package)
        package.metadata["quality"] = quality.value
        package.metadata["quality_reason"] = reason
        # Surface README section headings so the Writer can build a
        # more useful source context.
        from backend.app.services.sources.readme import (
            clean_readme as _clean_for_ctx,
            extract_headings,
        )
        readme_text = (readme_resp or {}).get("text", "")
        # ``clean_readme`` was already applied to the persisted
        # README; do it again here only to surface a stable list of
        # headings. The cost is negligible (it is a deterministic
        # text-munging pass).
        headings = extract_headings(_clean_for_ctx(readme_text, max_chars=200_000))
        if headings:
            package.metadata["readme_headings"] = headings
        return package

    # ------------------------------------------------------------------
    # ResearchPackage projection (override)
    # ------------------------------------------------------------------

    def to_research_package(self, package: SourcePackage) -> "ResearchPackage":
        # Local import keeps the adapter import-surface flat — we don't
        # need services.research at module load.
        from services.research.models import ResearchPackage

        rp = super().to_research_package(package)
        # Replace the topic with the GitHub-specific hint so the
        # writer's plan step sees a precise, evidence-grounded topic.
        rp.topic = package.metadata.get("topic_hint") or package.title
        return rp


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _safe_parse(url: str) -> Optional[Tuple[str, str]]:
    """Return ``(host, path)`` if the URL parses cleanly, else ``None``.

    Uses :mod:`urllib.parse` only — the SSRF guard does the real
    validation. This is just a fast pre-filter for ``can_handle``.
    Only ``http`` and ``https`` schemes are accepted: file://,
    ftp://, gopher://, ws://, javascript:, data:, and other
    credential-grabbers are rejected here so the adapter never even
    considers them.
    """
    if not isinstance(url, str) or not url:
        return None
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc or not parsed.path:
        return None
    host = (parsed.hostname or "").lower()
    return (host, parsed.path)


def _parse_owner_repo(url: str) -> Tuple[str, str]:
    """Parse ``owner`` and ``repo`` from a github.com URL.

    Raises :class:`SourceUnavailableError` with
    ``code="unsupported_url_form"`` if the URL is not a repository
    root.

    Implements decision 1 (option b): subpaths like ``/tree/...`` are
    accepted but normalised away to the repo root before fetching.
    """
    parsed = _safe_parse(url)
    if parsed is None:
        raise SourceUnavailableError(
            "URL is not parseable.",
            code="unsupported_url_form",
        )
    host, path = parsed
    if host not in {"github.com", "www.github.com"}:
        raise SourceUnavailableError(
            "URL is not on github.com.",
            code="unsupported_url_form",
            details={"host": host},
        )
    m = _REPO_PATH_RE.match(path)
    if not m:
        raise SourceUnavailableError(
            "URL is not a GitHub repository.",
            code="unsupported_url_form",
        )
    owner = m.group("owner")
    repo = m.group("repo")
    rest = (m.group("rest") or "").strip("/")
    ok, reason = _normalize_github_path(rest)
    if not ok:
        raise SourceUnavailableError(
            f"URL form not supported ({reason}).",
            code="unsupported_url_form",
            details={"rest": rest, "reason": reason},
        )
    # Discard the subpath (option b). The canonical repo URL is
    # built from owner/repo alone.
    return owner, repo


def _parse_json(response: SafeResponse, *, call_name: str) -> Any:
    """Parse a ``SafeResponse`` body as JSON, mapping errors to
    ``SourceUnavailableError``.
    """
    if response.status_code == 404:
        raise SourceUnavailableError(
            "Repository not found.",
            code="repository_not_found",
            details={"call": call_name, "status": 404},
        )
    if response.status_code == 401:
        raise SourceUnavailableError(
            "GitHub credentials are invalid.",
            code="github_unauthorized",
            details={"call": call_name, "status": 401},
        )
    if response.status_code == 403:
        # Detect rate-limit: ``X-RateLimit-Remaining: 0``.
        remaining = response.headers.get("x-ratelimit-remaining") or response.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            reset = response.headers.get("x-ratelimit-reset") or response.headers.get("X-RateLimit-Reset")
            details: Dict[str, Any] = {
                "call": call_name,
                "status": 403,
            }
            if reset:
                try:
                    details["retry_after"] = int(reset)
                except (TypeError, ValueError):
                    pass
            raise SourceUnavailableError(
                "GitHub rate limit reached.",
                code="github_rate_limited",
                details=details,
            )
        raise SourceUnavailableError(
            "Access to this repository is forbidden.",
            code="github_forbidden",
            details={"call": call_name, "status": 403},
        )
    if response.status_code == 451:
        raise SourceBlockedError(
            "This URL is not allowed for security reasons.",
            code="dmca",
        )
    if response.status_code >= 500:
        raise SourceUnavailableError(
            f"GitHub server error {response.status_code}.",
            code="http_5xx",
            details={"call": call_name, "status": response.status_code},
        )
    if response.status_code >= 400:
        raise SourceUnavailableError(
            f"GitHub client error {response.status_code}.",
            code="http_4xx_unexpected",
            details={"call": call_name, "status": response.status_code},
        )
    try:
        return json.loads(response.body.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise SourceUnavailableError(
            "GitHub returned an unexpected response.",
            code="bad_response",
            details={"call": call_name, "error": str(exc)},
        ) from exc


def _is_safe_manifest_name(name: str) -> bool:
    """Path-traversal guard + denylist enforcement for top-level files."""
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        return False
    if name in _DENYLIST_EXACT:
        return False
    lower = name.lower()
    for suf in _DENYLIST_SUFFIXES:
        if lower.endswith(suf):
            return False
    for pat in _DENYLIST_GLOBS:
        # Tiny fnmatch-ish: only ``*`` supported.
        if _glob_match(pat, lower):
            return False
    return True


def _glob_match(pattern: str, name: str) -> bool:
    """Minimal glob matcher for patterns like ``*.lock`` or ``.env*``.

    Only ``*`` wildcards are supported.
    """
    if "*" not in pattern:
        return pattern == name
    parts = pattern.split("*")
    # Match prefix.
    if not name.startswith(parts[0]):
        return False
    # Match suffix.
    if not name.endswith(parts[-1]):
        return False
    # The middle (if any) must appear in order.
    middle = parts[1:-1]
    pos = len(parts[0])
    for m in middle:
        idx = name.find(m, pos)
        if idx < 0:
            return False
        pos = idx + len(m)
    return True


def _truncate(s: str, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def _truncate_at_paragraph(text: str, max_chars: int) -> str:
    """Truncate ``text`` at the last paragraph boundary before ``max_chars``."""
    if len(text) <= max_chars:
        return text
    head = text[:max_chars]
    # Last paragraph break (double newline) within the head.
    idx = head.rfind("\n\n")
    if idx > max_chars // 2:
        return head[:idx].rstrip() + "\n\n…"
    # Fall back to last single newline.
    idx = head.rfind("\n")
    if idx > max_chars // 2:
        return head[:idx].rstrip() + "\n…"
    return head.rstrip() + "…"


def _extract_markdown_headings(text: str) -> List[str]:
    """Return a list of H1-H3 markdown headings found in ``text``."""
    if not text:
        return []
    out: List[str] = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,3})\s+(.+?)\s*#*\s*$", line)
        if m:
            out.append(m.group(2).strip())
    return out[:20]


def _extract_first_paragraph(text: str) -> str:
    """First non-heading, non-empty paragraph from ``text``."""
    if not text:
        return ""
    lines = text.splitlines()
    paragraph: List[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            if paragraph:
                break
            continue
        if s.startswith("#"):
            continue
        if s.startswith("```"):
            continue
        paragraph.append(s)
        if len(" ".join(paragraph)) > 400:
            break
    return _truncate(" ".join(paragraph), 400)


def _parse_iso8601(s: str) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        # ``datetime.fromisoformat`` accepts ``+00:00`` but not ``Z``.
        normalized = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _build_summary(
    *,
    description: str,
    primary_language: Optional[str],
    language_pcts: List[Tuple[str, float]],
    stars: int,
    forks: int,
    license_spdx: Optional[str],
    days_since_push: Optional[int],
    archived: bool,
    disabled: bool,
    is_minimal: bool,
) -> str:
    """Templated summary, ≤60 words."""
    if is_minimal:
        return "An empty GitHub repository."
    parts: List[str] = []
    if description:
        parts.append(description.rstrip("."))
    else:
        parts.append(
            f"A {'archived ' if archived else ''}{primary_language or 'GitHub'} "
            f"project"
        )
    if primary_language and language_pcts:
        top = language_pcts[0]
        parts.append(
            f"primarily {top[0]} ({top[1]}%)"
        )
    if stars or forks:
        parts.append(f"{stars:,} stars, {forks:,} forks")
    if license_spdx and license_spdx != "NOASSERTION":
        parts.append(f"licensed under {license_spdx}")
    if archived:
        parts.append("archived")
    elif disabled:
        parts.append("disabled")
    elif days_since_push is not None:
        parts.append(f"last push {days_since_push}d ago")
    summary = "; ".join(parts) + "."
    return _cap_words(summary, 60)


def _cap_words(s: str, max_words: int) -> str:
    words = s.split()
    if len(words) <= max_words:
        return s
    return " ".join(words[:max_words]) + "…"


def _cap_facts(facts: List[str], *, max_count: int, max_words: int) -> List[str]:
    out: List[str] = []
    for f in facts:
        capped = _cap_words(f.strip(), max_words)
        if capped:
            out.append(capped)
        if len(out) >= max_count:
            break
    return out


# ---------------------------------------------------------------------------
# Dependency parsing (small, stdlib-only, best-effort)
# ---------------------------------------------------------------------------


def _parse_all_dependencies(
    manifest_contents: Dict[str, str],
) -> Dict[str, Any]:
    """Run the per-format dependency parsers.

    Returns a dict-of-lists, keyed by ecosystem:
    ``{"python": [...], "node": [...], "rust": [...], ...}``.
    """
    out: Dict[str, List[str]] = {}
    for name, text in manifest_contents.items():
        parser = _PARSERS.get(name)
        if not parser:
            continue
        try:
            deps = parser(text)
        except Exception:  # noqa: BLE001
            continue
        if deps:
            eco = _MANIFEST_ECOSYSTEM.get(name, name)
            out.setdefault(eco, []).extend(deps)
    return out


def _parse_pyproject_toml(text: str) -> List[str]:
    """Parse ``pyproject.toml`` dependencies from the most common layouts.

    Supports ``[tool.poetry.dependencies]`` and
    ``[project.dependencies]`` (PEP 621). Best-effort; malformed files
    return ``[]``.
    """
    deps: List[str] = []
    # ``[tool.poetry.dependencies]`` and ``[project.dependencies]`` —
    # both are simple table-like mappings under a single section.
    in_target = False
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            in_target = (
                s == "[tool.poetry.dependencies]"
                or s == "[tool.poetry.group.*.dependencies]"
                or s == "[project.dependencies]"
                or s.startswith("[project.optional-dependencies")
            )
            continue
        if not in_target:
            continue
        # Key/value: ``key = "value"`` or ``key = {version = "...", ...}``.
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*=", s)
        if m:
            name = m.group(1).strip()
            # Filter out Python stdlib and special entries.
            if name.lower() in {"python", "setuptools"}:
                continue
            deps.append(name)
    return deps


def _parse_requirements_txt(text: str) -> List[str]:
    deps: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        if line.startswith("git+") or line.startswith("http"):
            continue
        # Strip environment markers and version specifiers.
        name = re.split(r"[<>=!~;\[ ]", line, maxsplit=1)[0].strip()
        if name:
            deps.append(name)
    return deps


def _parse_pipfile(text: str) -> List[str]:
    """Very small ``Pipfile`` parser — only the ``[packages]`` table."""
    deps: List[str] = []
    in_packages = False
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            in_packages = s == "[packages]"
            continue
        if not in_packages:
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)\s*=", s)
        if m:
            deps.append(m.group(1))
    return deps


def _parse_setup_py(text: str) -> List[str]:
    """Parse ``install_requires=[...]`` from ``setup.py``.

    Crude; only handles a single ``install_requires`` list at module
    top level. Malformed files return ``[]``.
    """
    deps: List[str] = []
    if "install_requires" not in text:
        return deps
    m = re.search(
        r"install_requires\s*=\s*\[([^\]]*)\]", text, re.DOTALL
    )
    if not m:
        return deps
    body = m.group(1)
    for raw in re.findall(r"""['"]([^'"]+)['"]""", body):
        name = re.split(r"[<>=!~;\[ ]", raw, maxsplit=1)[0].strip()
        if name:
            deps.append(name)
    return deps


def _parse_setup_cfg(text: str) -> List[str]:
    deps: List[str] = []
    in_options = False
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(";"):
            continue
        if s.startswith("["):
            in_options = s == "[options]"
            continue
        if not in_options:
            continue
        m = re.match(r"^install_requires\s*=\s*(.+)$", s)
        if not m:
            continue
        body = m.group(1)
        for raw in body.split(","):
            raw = raw.strip()
            if not raw:
                continue
            name = re.split(r"[<>=!~;\[ ]", raw, maxsplit=1)[0].strip()
            if name:
                deps.append(name)
    return deps


def _parse_package_json(text: str) -> List[str]:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    out: List[str] = []
    for key in ("dependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            out.extend(section.keys())
        elif isinstance(section, list):
            for entry in section:
                if isinstance(entry, str):
                    out.append(re.split(r"[<>=!~; ]", entry, maxsplit=1)[0])
                elif isinstance(entry, dict) and "name" in entry:
                    out.append(str(entry["name"]))
    if "devDependencies" in data and isinstance(data["devDependencies"], dict):
        # Include dev deps under a separate key.
        out.extend(d for d in data["devDependencies"].keys())
    return out


def _parse_cargo_toml(text: str) -> List[str]:
    deps: List[str] = []
    in_deps = False
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            in_deps = s in (
                "[dependencies]",
                "[dev-dependencies]",
                "[build-dependencies]",
            )
            continue
        if not in_deps:
            continue
        m = re.match(r'^([A-Za-z0-9_.\-]+)\s*=', s)
        if m:
            deps.append(m.group(1))
    return deps


def _parse_go_mod(text: str) -> List[str]:
    """Parse ``require (...)`` blocks in ``go.mod``."""
    deps: List[str] = []
    in_require = False
    paren_depth = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        if not in_require:
            if s == "require (":
                in_require = True
                paren_depth = 1
                continue
            if s.startswith("require "):
                # Single-line: ``require foo v1.0.0``
                parts = s.split()
                if len(parts) >= 2 and parts[0] == "require":
                    deps.append(parts[1])
            continue
        # In require block.
        for ch in s:
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
        if paren_depth <= 0:
            in_require = False
            continue
        parts = s.split()
        if parts and not s.startswith("//"):
            deps.append(parts[0])
    return deps


def _parse_gemfile(text: str) -> List[str]:
    deps: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if not s.startswith("gem "):
            continue
        # ``gem '<name>'`` or ``gem "<name>"`` or ``gem <name>``.
        parts = s.split()
        if len(parts) < 2:
            continue
        # Strip surrounding quotes, trailing version constraints
        # (e.g. ``, '~> 7.0'``), and trailing comments.
        name = parts[1].strip().strip("'\"")
        name = name.split(",", 1)[0].strip().strip("'\"")
        if name:
            deps.append(name)
    return deps


def _parse_composer_json(text: str) -> List[str]:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    out: List[str] = []
    req = data.get("require")
    if isinstance(req, dict):
        # Strip version constraints.
        out.extend(req.keys())
    dev = data.get("require-dev")
    if isinstance(dev, dict):
        out.extend(f"{k} (dev)" for k in dev.keys())
    return out


_PARSERS = {
    "pyproject.toml": _parse_pyproject_toml,
    "requirements.txt": _parse_requirements_txt,
    "Pipfile": _parse_pipfile,
    "setup.py": _parse_setup_py,
    "setup.cfg": _parse_setup_cfg,
    "package.json": _parse_package_json,
    "Cargo.toml": _parse_cargo_toml,
    "go.mod": _parse_go_mod,
    "Gemfile": _parse_gemfile,
    "composer.json": _parse_composer_json,
}

_MANIFEST_ECOSYSTEM = {
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "package.json": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "Gemfile": "ruby",
    "composer.json": "php",
}


def _format_dependencies_summary(deps: Dict[str, Any]) -> str:
    """Short text summary of dependencies for a ``raw_results`` snippet."""
    parts: List[str] = []
    for eco, names in deps.items():
        if not names:
            continue
        uniq = []
        seen = set()
        for n in names:
            if n in seen:
                continue
            seen.add(n)
            uniq.append(n)
        parts.append(f"{eco}: {', '.join(uniq[:6])}")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Registration — call ``register_adapter`` at import time so
# ``resolve_adapter`` finds the GitHub adapter before the stub.
# ---------------------------------------------------------------------------

from backend.app.services.sources.registry import register_adapter

register_adapter(GitHubSourceAdapter)


__all__ = ["GitHubSourceAdapter"]
