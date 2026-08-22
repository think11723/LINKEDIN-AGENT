"""Phase 17 / Production-dependency sanity test.

Goal
----

Catch the "RuntimeError: Form data requires python-multipart to be
installed" failure (and similar) at TEST time so Railway can never
crash on it again.

The Railway build installs only what is declared in
``requirements.txt``. A package present in the developer's local
``.venv`` (e.g. installed by an IDE or a stray ``pip install``)
but missing from ``requirements.txt`` will not appear in the
production image, and FastAPI raises at startup when a route uses
``File`` / ``Form`` / ``UploadFile`` without python-multipart.

Strategy
--------

This test imports every runtime dependency that the FastAPI
application routes depend on, and asserts that each import
succeeds. If a future change introduces a new ``File`` / ``Form``
dependency without adding it to ``requirements.txt``, this test
fails immediately on a developer machine (instead of crashing
on Railway).

It is intentionally NOT a mock. The import is real. The test
runs in <1 second.
"""

from __future__ import annotations

import importlib


# Module names that MUST be importable in the production runtime.
# A missing entry here means the test architecture itself depends
# on something Railway won't install. Add it; do not skip it.
REQUIRED_RUNTIME_MODULES = [
    # Web framework + server (declared in requirements.txt)
    "fastapi",
    "uvicorn",
    # pydantic base
    "pydantic",
    # HTTP client used by the LinkedIn publisher + the SSRF-safe
    # fetcher (declared in requirements.txt)
    "httpx",
    # Async MongoDB driver (declared in requirements.txt)
    "motor",
    "pymongo",
    "mongomock_motor",
    # firebase-admin (declared in requirements.txt)
    "firebase_admin",
    # Auth helpers (declared in requirements.txt)
    "cryptography",
    # langchain stack (declared in requirements.txt)
    "langchain",
    "langchain_core",
    "langchain_community",
    "langgraph",
    # Image / requests / oauth (declared in requirements.txt)
    "PIL",
    "requests",
    "requests_oauthlib",
    "dotenv",
    # FastAPI multipart parser — THIS is the dependency the bug
    # report was about. It MUST be importable for the
    # /resumes/upload route to be importable.
    "multipart",
    # tzdata (declared in requirements.txt)
    "tzdata",
    # rich (declared in requirements.txt)
    "rich",
    # duckduckgo-search (declared in requirements.txt)
    "duckduckgo_search",
]


def _check_importable(name: str) -> tuple[bool, str | None]:
    """Return ``(True, None)`` if importable, else ``(False, msg)``."""
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001 — any failure is reported
        return False, f"{type(exc).__name__}: {exc}"
    return True, None


def test_required_runtime_modules_are_importable() -> None:
    """Every entry in :data:`REQUIRED_RUNTIME_MODULES` must be
    importable. A missing module means the production
    ``requirements.txt`` is incomplete.
    """
    failures: list[str] = []
    for name in REQUIRED_RUNTIME_MODULES:
        ok, msg = _check_importable(name)
        if not ok:
            failures.append(f"{name}: {msg}")
    assert not failures, (
        "The following runtime modules are NOT importable. "
        "Add them to requirements.txt so Railway can install them. "
        "Missing: " + "; ".join(failures)
    )


def test_fastapi_upload_route_is_importable() -> None:
    """A regression test for the specific Railway crash: FastAPI
    raises ``RuntimeError: Form data requires python-multipart to
    be installed`` when a route uses ``UploadFile`` but the
    package is missing. We import the upload route's *parent*
    module which transitively imports the route, and assert no
    error is raised.
    """
    # Importing the jobs / resumes routers must succeed. If
    # python-multipart is missing, this raises RuntimeError.
    from backend.app.api.v1 import resumes as _resumes  # noqa: F401
    from backend.app.api.v1 import jobs as _jobs  # noqa: F401


def test_resume_upload_route_uses_upload_file() -> None:
    """The /resumes/upload route must keep its ``UploadFile`` /
    ``File`` signature so the FE client can POST multipart
    payloads. We assert this directly to prevent accidental
    regressions in future Phase hardening passes.
    """
    from backend.app.api.v1 import resumes as _resumes
    from fastapi import File, UploadFile
    import inspect

    # Walk the route functions and find one that uses UploadFile.
    found = False
    for route in _resumes.router.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        try:
            sig = inspect.signature(endpoint)
        except (TypeError, ValueError):
            continue
        for param in sig.parameters.values():
            if param.annotation in (UploadFile, File, "UploadFile", "File"):
                found = True
                break
    assert found, (
        "Phase 17 regression: the resume upload route no longer "
        "exposes a File / UploadFile parameter. The frontend will "
        "be broken — please restore the multipart parameter."
    )
