"""Source-adapter package — Phase 8D / URL-to-LinkedIn feature.

Public surface (used by ``backend/app/services/source_job_runner.py``):

* :class:`BaseSourceAdapter` and :class:`SourcePackage` (``base``).
* :class:`SourceFetchError` and subclasses (``base``).
* :func:`resolve_adapter` (``registry``).
* :func:`validate_url`, :func:`check_ip_family`, :func:`resolve_safely`,
  :func:`safe_get` (``ssrf``).

Adapter modules are imported below in the order they should be tried
against a URL. ``resolve_adapter`` does first-match-wins, so the
most-specific adapter (GitHub) MUST register before the catch-all
adapter (Stub).

* ``github_adapter`` — public GitHub repositories (P1).
* ``stub_adapter``   — deterministic stub for P0 testing; **must be
  imported last** so the more-specific GitHub adapter wins.
* Web-article adapter is added in P2.
"""

from __future__ import annotations

# Import order is significant: GitHub must register before Stub.
# ``resolve_adapter`` does first-match-wins on the ``ADAPTERS`` list.
# The ``register_adapter`` call in each module's import body appends to
# the list in this order:
from backend.app.services.sources.base import (
    BaseSourceAdapter,
    SourceBlockedError,
    SourceFetchError,
    SourcePackage,
    SourceTooLargeError,
    SourceUnavailableError,
)
from backend.app.services.sources.registry import ADAPTERS, resolve_adapter
from backend.app.services.sources.ssrf import (
    ALLOWED_SCHEMES,
    GITHUB_ALLOWLIST,
    ResolvedTarget,
    check_ip_family,
    resolve_safely,
    safe_get,
    validate_url,
)

# Most-specific first; catch-all last.
from backend.app.services.sources import github_adapter  # noqa: F401  (registers GitHub)
from backend.app.services.sources import web_adapter  # noqa: F401  (registers WebArticle — fall-through)
from backend.app.services.sources import stub_adapter  # noqa: F401  (registers Stub — last-resort fallback)


__all__ = [
    "ADAPTERS",
    "ALLOWED_SCHEMES",
    "BaseSourceAdapter",
    "GITHUB_ALLOWLIST",
    "ResolvedTarget",
    "SourceBlockedError",
    "SourceFetchError",
    "SourcePackage",
    "SourceTooLargeError",
    "SourceUnavailableError",
    "check_ip_family",
    "resolve_adapter",
    "resolve_safely",
    "safe_get",
    "validate_url",
]