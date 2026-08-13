"""Quarantine conftest for the pre-SaaS manual integration scripts.

Phase 8D / P3-6: this directory contains standalone Python scripts (see
``README.md``) that are invoked directly via
``python tests/manual/run_all_tests.py`` or ``python tests/manual/test_*.py``.
They pre-date the FastAPI + MongoDB SaaS backend and import modules that no
longer exist (e.g. ``services.scheduler``, ``memory.service``).

Preventing pytest from collecting them keeps the SaaS suite green; the
scripts themselves remain runnable from the command line exactly as before.
"""

collect_ignore_glob = ["*.py"]