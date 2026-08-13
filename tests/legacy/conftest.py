"""Quarantine conftest for pre-SaaS CLI-era tests.

Phase 8D / P3-6: the three files in this directory target CLI-only modules
(``utils.draft_saver``, ``utils.profile_manager``, ``utils.logger``,
``memory.service``, and the root ``app.py`` CLI) that have been superseded
by the FastAPI + MongoDB SaaS backend. The LLM provider and workflow tests
that DO exercise active code paths remain in the parent ``tests/`` directory
even though their mock fixtures pre-date Pydantic v2.

The active SaaS suite (``backend/app/main.py`` + ``tests/test_*.py``) does
not depend on any module imported here, but pytest collection would still
attempt to import these files and could surface confusing import-time errors.
``collect_ignore_glob`` prevents collection entirely; the files are preserved
on disk for historical reference and so they can be reactivated under a
properly isolated conftest in the future if the legacy CLI is revived.
"""

collect_ignore_glob = ["*.py"]