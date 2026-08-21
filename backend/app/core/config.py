"""Backend settings sourced from environment variables.

The legacy ``config/config.py`` keeps Gemini-flavoured legacy variables.
This module owns the SaaS-side environment (Mongo, Firebase, CORS, Fernet)
and is the single source of truth for new code.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: Optional[str], default: Optional[List[str]] = None) -> List[str]:
    if value is None or value == "":
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings:
    """SaaS-side runtime settings."""

    # MongoDB ---------------------------------------------------------------
    mongodb_uri: str
    mongodb_db_name: str

    # Firebase Admin -------------------------------------------------------
    firebase_credentials_path: Optional[str]
    firebase_credentials_json: Optional[str]
    firebase_project_id: Optional[str]

    # CORS ------------------------------------------------------------------
    cors_allowed_origins: List[str]

    # Frontend URL (for OAuth redirects) -----------------------------------
    frontend_url: str

    # LinkedIn OAuth + encryption -------------------------------------------
    linkedin_token_encryption_key: Optional[str]
    linkedin_client_id: Optional[str]
    linkedin_client_secret: Optional[str]
    linkedin_redirect_uri: str

    # Email (SMTP) for approval notifications -------------------------------
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_use_tls: bool = True

    # Image generation passthrough ------------------------------------------
    image_provider: str
    image_model: str

    def __init__(self) -> None:
        self.mongodb_uri = os.getenv("MONGODB_URI", "").strip()
        self.mongodb_db_name = os.getenv("MONGODB_DB_NAME", "linkedin_agent").strip()

        self.firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        self.firebase_credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
        self.firebase_project_id = os.getenv("FIREBASE_PROJECT_ID")

        default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
        self.cors_allowed_origins = _split_csv(
            os.getenv("CORS_ALLOWED_ORIGINS"),
            default=default_origins,
        )

        # Phase 8C — the LinkedIn callback redirects here so the SPA
        # picks up the ?linkedin=connected flag in the URL.
        self.frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173").strip()

        self.linkedin_token_encryption_key = os.getenv("LINKEDIN_TOKEN_ENCRYPTION_KEY")
        # P0-9: .strip() the LinkedIn OAuth credentials to defend against
        # accidental whitespace / quotes / newlines being introduced via
        # copy-paste into env-var UIs. A single trailing '\n' or a pair
        # of surrounding '"' would otherwise be sent verbatim to
        # LinkedIn's /oauth/v2/accessToken and produce invalid_client.
        self.linkedin_client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
        self.linkedin_client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
        self.linkedin_redirect_uri = os.getenv(
            "LINKEDIN_REDIRECT_URI",
            "http://localhost:8000/api/v1/linkedin/callback",
        ).strip()

        # Email (SMTP) — used by approval-email notifications.
        self.smtp_host = os.getenv("SMTP_HOST") or None
        try:
            self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        except ValueError:
            self.smtp_port = 587
        self.smtp_username = os.getenv("SMTP_USERNAME") or None
        self.smtp_password = os.getenv("SMTP_PASSWORD") or None
        self.email_from = os.getenv("EMAIL_FROM") or None
        self.email_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {
            "1", "true", "yes"
        }

        self.image_provider = os.getenv("IMAGE_PROVIDER", "pollinations")
        self.image_model = os.getenv("IMAGE_MODEL", "flux")

        # Source-generation (URL-to-LinkedIn) — Phase 8D / P0.
        # Defaults are safe; override via env. The SSRF guard is in
        # ``backend/app/services/sources/ssrf.py`` and reads these.
        self.source_fetch_max_bytes: int = int(os.getenv("SOURCE_FETCH_MAX_BYTES", "5242880"))
        self.source_fetch_max_redirects: int = int(os.getenv("SOURCE_FETCH_MAX_REDIRECTS", "5"))
        self.source_fetch_timeout_seconds: float = float(os.getenv("SOURCE_FETCH_TIMEOUT_SECONDS", "20"))
        self.source_fetch_total_timeout_seconds: float = float(
            os.getenv("SOURCE_FETCH_TOTAL_TIMEOUT_SECONDS", "90")
        )
        self.source_github_max_bytes: int = int(os.getenv("SOURCE_GITHUB_MAX_BYTES", "1048576"))
        self.source_html_max_bytes_after_strip: int = int(
            os.getenv("SOURCE_HTML_MAX_BYTES_AFTER_STRIP", "1048576")
        )
        raw_ports = os.getenv("SSRF_ALLOWED_PORTS", "80,443")
        self.ssrf_allowed_ports: frozenset = frozenset(
            int(p.strip()) for p in raw_ports.split(",") if p.strip()
        )
        self.ssrf_allow_private: bool = (
            os.getenv("SSRF_ALLOW_PRIVATE", "false").lower() in {"1", "true", "yes"}
        )
        self.github_token: Optional[str] = os.getenv("GITHUB_TOKEN")
        self.source_extractor: str = os.getenv("SOURCE_EXTRACTOR", "trafilatura")
        self.source_jobs_max_active_per_user: int = int(
            os.getenv("SOURCE_JOBS_MAX_ACTIVE_PER_USER", "3")
        )
        self.source_jobs_rate_per_hour: int = int(os.getenv("SOURCE_JOBS_RATE_PER_HOUR", "10"))

        # Search (Phase 8E) --------------------------------------------
        # The multi-provider search chain in services.search uses
        # these env vars to know which SearXNG instances to rotate
        # through and which fallback sources are enabled. No API
        # keys are required for any of them.
        # SEARXNG_INSTANCES is a comma-separated list of full URLs;
        # an empty list is valid (the orchestrator will skip
        # SearXNG and move to Wikipedia).
        searxng_raw = os.getenv("SEARXNG_INSTANCES", "")
        self.searxng_instances: List[str] = _split_csv(
            searxng_raw, default=[]
        )
        self.wikipedia_api_url: str = os.getenv(
            "WIKIPEDIA_API_URL", "https://en.wikipedia.org"
        ).strip()
        self.hn_algolia_api_url: str = os.getenv(
            "HN_ALGOLIA_API_URL", "https://hn.algolia.com"
        ).strip()
        self.search_timeout_seconds: float = float(
            os.getenv("SEARCH_TIMEOUT_SECONDS", "6")
        )
        self.search_max_bytes: int = int(
            os.getenv("SEARCH_MAX_BYTES", str(1 * 1024 * 1024))
        )
        # Per-provider allowlist of hostnames the search layer is
        # permitted to contact. Built from the configured providers
        # below; the SSRF guard uses this as the ``allow_hosts``
        # set on every outbound request.
        self.search_allowlist: List[str] = self._build_search_allowlist()

    def _build_search_allowlist(self) -> List[str]:
        """Compute the set of hostnames the search layer may
        contact. Built from the configured SearXNG instances plus
        the Wikipedia and HN Algolia base URLs.
        """
        from urllib.parse import urlparse
        hosts: List[str] = []
        seen: set[str] = set()

        def _add(url: str) -> None:
            try:
                host = (urlparse(url).hostname or "").lower()
            except ValueError:
                return
            if host and host not in seen:
                seen.add(host)
                hosts.append(host)

        for inst in self.searxng_instances:
            _add(inst)
        _add(self.wikipedia_api_url)
        _add(self.hn_algolia_api_url)
        return hosts

    # --- validation helpers ----------------------------------------------
    def require_mongo(self) -> None:
        if not self.mongodb_uri:
            raise RuntimeError(
                "MONGODB_URI is not set. The SaaS backend requires a real MongoDB instance."
            )
        if not self.mongodb_db_name:
            raise RuntimeError("MONGODB_DB_NAME is not set.")

    def require_firebase(self) -> None:
        if not self.firebase_credentials_path and not self.firebase_credentials_json:
            raise RuntimeError(
                "Firebase credentials are not configured. Set FIREBASE_CREDENTIALS_PATH "
                "or FIREBASE_CREDENTIALS_JSON before starting the SaaS backend."
            )

    def require_linkedin_encryption_key(self) -> bytes:
        if not self.linkedin_token_encryption_key:
            raise RuntimeError(
                "LINKEDIN_TOKEN_ENCRYPTION_KEY is not set. Generate one with "
                "`python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"` "
                "and add it to the backend .env."
            )
        return self.linkedin_token_encryption_key.encode("utf-8")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()