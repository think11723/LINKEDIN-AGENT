"""Phase 8D / P0 — Vercel + Railway deployment-readiness checks.

A focused, minimal suite that proves the codebase is safe to ship under the
new deployment topology:

    Vercel  ─── frontend (React + Vite + React Router)
    Railway ─── backend (FastAPI + uvicorn + SourceJobRunner + SchedulerRunner)
    Atlas   ─── MongoDB
    Firebase ─── auth (frontend Web SDK + backend Admin SDK)

What this covers (and deliberately does NOT cover — the suite stays small):

  * Frontend API base URL is configurable (VITE_API_BASE_URL) and falls
    back to ``http://localhost:8000`` when unset.
  * Backend CORS is configurable and *not* wildcarded by default.
  * SPA fallback rewrite is declared in ``frontend/vercel.json``.
  * ``/live``, ``/ready``, ``/health`` exist and respond.
  * Backend app imports without raising (startup smoke test).
  * Firebase Admin SDK accepts the ``FIREBASE_CREDENTIALS_JSON`` env path.
  * Frontend env example ships NO backend secrets.
  * LinkedIn redirect URI is environment-driven.
  * SourceJobRunner and SchedulerRunner import cleanly (workers wired).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1. Frontend API base URL behaviour
# ---------------------------------------------------------------------------


def test_frontend_client_defaults_to_localhost() -> None:
    """With no VITE_API_BASE_URL the client falls back to localhost:8000."""
    # The frontend builds the URL at runtime via ``import.meta.env``. We
    # cannot import the .js module from a Python test, but we can read
    # the file and assert the default constant is wired in.
    client_js = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "src"
        / "services"
        / "api"
        / "client.js"
    )
    text = client_js.read_text(encoding="utf-8")
    assert "VITE_API_BASE_URL" in text
    assert "DEFAULT_BASE_URL = 'http://localhost:8000'" in text


def test_frontend_env_example_uses_vite_api_base_url() -> None:
    """The frontend env example declares VITE_API_BASE_URL."""
    env_example = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / ".env.example"
    )
    text = env_example.read_text(encoding="utf-8")
    assert "VITE_API_BASE_URL" in text


# ---------------------------------------------------------------------------
# 2. SPA fallback (Vercel rewrites)
# ---------------------------------------------------------------------------


def test_vercel_json_declares_spa_fallback() -> None:
    """``frontend/vercel.json`` rewrites all routes to ``/index.html``.

    Without this, direct browser refreshes on /drafts/:id etc. return 404
    from the Vercel CDN instead of falling through to React Router.
    """
    vercel_json = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "vercel.json"
    )
    assert vercel_json.exists(), (
        "frontend/vercel.json must exist for Vercel SPA fallback."
    )
    import json

    cfg = json.loads(vercel_json.read_text(encoding="utf-8"))
    rewrites = cfg.get("rewrites", [])
    assert {"source": "/(.*)", "destination": "/index.html"} in rewrites
    # Vite output contract.
    assert cfg.get("outputDirectory") == "dist"
    assert cfg.get("buildCommand") == "npm run build"


# ---------------------------------------------------------------------------
# 3. CORS configuration
# ---------------------------------------------------------------------------


def test_cors_default_is_localhost_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an env override CORS stays locked to the dev origins.

    Production must set ``CORS_ALLOWED_ORIGINS`` explicitly — there is no
    wildcard default that would leak the API to arbitrary origins.
    """
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    from backend.app.core.config import Settings

    settings = Settings()
    assert "*" not in settings.cors_allowed_origins
    # Dev origins are present; production deployers override via env.
    assert "http://localhost:5173" in settings.cors_allowed_origins


def test_cors_allowed_origins_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """``CORS_ALLOWED_ORIGINS`` is honoured when set."""
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://app.vercel.app,https://staging.vercel.app",
    )
    from backend.app.core.config import Settings

    settings = Settings()
    assert settings.cors_allowed_origins == [
        "https://app.vercel.app",
        "https://staging.vercel.app",
    ]


# ---------------------------------------------------------------------------
# 4. Health endpoints
# ---------------------------------------------------------------------------


def test_health_endpoints_registered(client_anon) -> None:
    """``/live``, ``/ready``, ``/health`` are all reachable."""
    # /live and /health have no dependencies — they pass even without
    # real Mongo because the conftest fixtures stub them.
    assert client_anon.get("/live").status_code == 200
    assert client_anon.get("/health").status_code == 200
    # /ready is exercised in test_p0_error_health.py with deeper checks.
    assert client_anon.get("/ready").status_code in {200, 503}


# ---------------------------------------------------------------------------
# 5. Backend startup smoke
# ---------------------------------------------------------------------------


def test_backend_app_imports_cleanly() -> None:
    """Importing the app object does not raise.

    Catches the "wrong sys.path / missing dependency / typo in module
    name" class of deployment failures before they hit Railway.
    """
    from backend.app.main import app  # noqa: F401

    assert app.title.startswith("LinkedIn")


# ---------------------------------------------------------------------------
# 6. Firebase production configuration path
# ---------------------------------------------------------------------------


def test_firebase_credentials_json_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``FIREBASE_CREDENTIALS_JSON`` (raw JSON env, not a file path) is the
    production-friendly path used on Railway. ``init_firebase`` must accept
    it without trying to read a file off disk.
    """
    monkeypatch.delenv("FIREBASE_CREDENTIALS_PATH", raising=False)
    monkeypatch.setenv(
        "FIREBASE_CREDENTIALS_JSON",
        '{"type":"service_account","project_id":"test","private_key":"","client_email":"x"}',
    )
    # We only need to confirm the JSON path is wired — the actual
    # ``credentials.Certificate`` call needs a real key. Patch it to a
    # no-op so the test stays hermetic.
    import backend.app.core.security as sec

    class _FakeCredential:
        project_id = "test"

    monkeypatch.setattr(
        sec.credentials, "Certificate", lambda _d: _FakeCredential()
    )
    # Reset the lru_cache for Settings (each call returns a fresh
    # Settings object inside ``init_firebase`` via ``get_settings`` which
    # IS cached, but the settings instance is read here too).
    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    try:
        # Reset the module-level cached app too.
        sec._firebase_app = None  # type: ignore[attr-defined]
        app = sec.init_firebase(get_settings())
        assert app is not None
    finally:
        get_settings.cache_clear()


def test_firebase_service_account_json_is_gitignored() -> None:
    """Service-account JSON files must never be committed."""
    gitignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(
        encoding="utf-8"
    )
    assert "firebase-service-account.json" in gitignore


# ---------------------------------------------------------------------------
# 7. No backend secrets in the frontend
# ---------------------------------------------------------------------------


_FORBIDDEN_FRONTEND_VARS = (
    "VITE_MONGODB_URI",
    "VITE_GROQ_API_KEY",
    "VITE_OPENROUTER_API_KEY",
    "VITE_HF_API_KEY",
    "VITE_LINKEDIN_CLIENT_SECRET",
    "VITE_LINKEDIN_TOKEN_ENCRYPTION_KEY",
    "VITE_FIREBASE_CREDENTIALS_JSON",
    "VITE_FIREBASE_CREDENTIALS_PATH",
    "VITE_GITHUB_TOKEN",
)


def test_frontend_env_files_have_no_backend_secrets() -> None:
    """No VITE_* variable leaks a backend secret into the browser bundle."""
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    offenders: list[str] = []
    for env_file in (frontend / ".env", frontend / ".env.example"):
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            if key in _FORBIDDEN_FRONTEND_VARS:
                offenders.append(f"{env_file}: {key}")
    assert not offenders, f"Backend secret leaked to frontend env: {offenders}"


def test_frontend_source_has_no_backend_secret_literal() -> None:
    """Defence-in-depth: no committed key/secret literals in the frontend src."""
    src = Path(__file__).resolve().parents[1] / "frontend" / "src"
    # The Firebase Web SDK apiKey is *expected* to live in the SPA — the
    # pattern below is broader on purpose and only catches obvious leaks
    # such as committed MongoDB URIs or LLM API keys.
    suspicious = re.compile(
        r"(mongodb(?:\+srv)?://[^\s'\"]+|"
        r"sk-[A-Za-z0-9]{20,}|"
        r"gho_[A-Za-z0-9]{20,}|"
        r"github_pat_[A-Za-z0-9_]{20,}|"
        r"ghp_[A-Za-z0-9]{20,})"
    )
    hits: list[str] = []
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in suspicious.finditer(text):
            hits.append(f"{path}: {m.group(0)[:24]}…")
    assert not hits, f"Suspicious literal in frontend src: {hits}"


# ---------------------------------------------------------------------------
# 8. LinkedIn redirect URI is configurable
# ---------------------------------------------------------------------------


def test_linkedin_redirect_uri_is_env_driven(monkeypatch: pytest.MonkeyPatch) -> None:
    """The LinkedIn callback URI is sourced from the env, not hardcoded."""
    monkeypatch.setenv(
        "LINKEDIN_REDIRECT_URI",
        "https://example.up.railway.app/api/v1/linkedin/callback",
    )
    from backend.app.core.config import Settings

    settings = Settings()
    assert settings.linkedin_redirect_uri == (
        "https://example.up.railway.app/api/v1/linkedin/callback"
    )


def test_linkedin_frontend_url_is_env_driven(monkeypatch: pytest.MonkeyPatch) -> None:
    """``FRONTEND_URL`` is used for the post-OAuth redirect target."""
    monkeypatch.setenv("FRONTEND_URL", "https://app.vercel.app")
    from backend.app.core.config import Settings

    settings = Settings()
    assert settings.frontend_url == "https://app.vercel.app"


# ---------------------------------------------------------------------------
# 9. Background workers import / initialise
# ---------------------------------------------------------------------------


def test_source_job_runner_imports_and_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    """``SourceJobRunner`` can be constructed and ``start()`` is a no-op
    when no Mongo is available. We mock the recovery path so the test
    stays hermetic.
    """
    import asyncio

    from backend.app.services.source_job_runner import SourceJobRunner

    async def _noop_recover(self, _timeout: float) -> None:  # noqa: D401
        return None

    monkeypatch.setattr(SourceJobRunner, "_recover_stale", _noop_recover)

    async def _exercise() -> None:
        runner = SourceJobRunner(poll_interval=2.0)
        runner.start()
        await asyncio.sleep(0)
        assert runner._task is not None
        await runner.stop()
        assert runner._task is None

    asyncio.run(_exercise())


def test_scheduler_runner_imports_and_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    """``SchedulerRunner`` can be constructed and started without a real Mongo."""
    import asyncio

    from backend.app.services.scheduler_runner import SchedulerRunner

    async def _exercise() -> None:
        runner = SchedulerRunner(poll_interval=5.0)
        runner.start()
        await asyncio.sleep(0)
        assert runner._task is not None
        await runner.stop()
        assert runner._task is None

    asyncio.run(_exercise())


# ---------------------------------------------------------------------------
# 10. Railway start command contract
# ---------------------------------------------------------------------------


def test_procfile_declares_railway_start_command() -> None:
    """The Procfile uses the Railway-native ``$PORT`` env var."""
    procfile = Path(__file__).resolve().parents[1] / "Procfile"
    assert procfile.exists(), "Procfile must exist for Railway deployment."
    text = procfile.read_text(encoding="utf-8").strip()
    assert text.startswith("web:")
    assert "0.0.0.0" in text
    assert "$PORT" in text
    assert "backend.app.main:app" in text
