"""Adapter registry — URL → adapter dispatch.

Adapters are discovered via a hardcoded list (no plugin system —
adding a new one is a one-line PR). ``resolve_adapter`` returns the
first adapter whose :meth:`BaseSourceAdapter.can_handle` returns True.
"""

from __future__ import annotations

from typing import List, Type

from backend.app.services.sources.base import BaseSourceAdapter

#: Adapter discovery list. Order matters: the first ``can_handle`` wins.
#: GitHub is checked first so ``https://github.com/user/repo`` does not
#: fall through to the web-page catch-all.
ADAPTERS: List[Type[BaseSourceAdapter]] = []


def register_adapter(cls: Type[BaseSourceAdapter]) -> Type[BaseSourceAdapter]:
    """Register an adapter class. Idempotent: re-registering is a no-op."""
    if cls not in ADAPTERS:
        ADAPTERS.append(cls)
    return cls


def resolve_adapter(url: str) -> BaseSourceAdapter:
    """Return an instance of the first adapter that handles ``url``.

    Raises ``ValueError`` if no adapter matches. Adapters are expected
    to be registered at import time (the stub / github / webpage
    adapters each call :func:`register_adapter` from their module body).
    """
    for cls in ADAPTERS:
        if cls.can_handle(url):
            return cls()
    raise ValueError(f"No adapter registered for URL: {url!r}")


__all__ = ["ADAPTERS", "register_adapter", "resolve_adapter"]