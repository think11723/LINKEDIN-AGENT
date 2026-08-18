"""Stub source adapter — P0 verification only.

The plan requires P0 to be end-to-end provable *before* any real
adapter exists, so the runner can be exercised against a canned
``SourcePackage``. This stub is registered FIRST in the adapter list
and accepts any URL; once real adapters (GitHub / web) are added in
P1 and P2 the registration order is updated so the more-specific
adapters win.

The stub never makes a network call.
"""

from __future__ import annotations

from backend.app.services.sources.base import BaseSourceAdapter, SourcePackage
from backend.app.services.sources.registry import register_adapter


class StubSourceAdapter(BaseSourceAdapter):
    """Always-accepts adapter used for P0 pipeline verification."""

    name = "stub"

    @classmethod
    def can_handle(cls, url: str) -> bool:  # noqa: D401
        return bool(url)

    async def fetch(self, url: str, *, request_id: str) -> SourcePackage:
        # Deterministic canned package. No network call.
        return SourcePackage(
            title="Stub Source",
            summary=(
                "Stub summary produced by the StubSourceAdapter. The real "
                "GitHub / web adapters are added in P1 / P2."
            ),
            key_facts=[
                "This is a stub adapter used during P0.",
                "It is intentionally deterministic and offline.",
                f"Request id was {request_id}.",
            ],
            raw_results=[
                {
                    "title": "Stub overview",
                    "url": url,
                    "snippet": (
                        "Stub overview snippet for the writer to consume as "
                        "raw_results[0]."
                    ),
                },
                {
                    "title": "Stub key facts",
                    "url": url,
                    "snippet": (
                        "• Stub fact A • Stub fact B • Stub fact C"
                    ),
                },
                {
                    "title": "Stub detail",
                    "url": url,
                    "snippet": (
                        "Stub detail block — this is the third snippet the "
                        "writer reads from raw_results."
                    ),
                },
            ],
            metadata={
                "url": url,
                "adapter": "stub",
                "request_id": request_id,
                "topic_hint": "stub topic",
            },
        )


# Register at import time so :func:`resolve_adapter` finds us.
register_adapter(StubSourceAdapter)


__all__ = ["StubSourceAdapter"]