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
        self.linkedin_client_id = os.getenv("LINKEDIN_CLIENT_ID")
        self.linkedin_client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
        self.linkedin_redirect_uri = os.getenv(
            "LINKEDIN_REDIRECT_URI",
            "http://localhost:8000/api/v1/linkedin/callback",
        )

        self.image_provider = os.getenv("IMAGE_PROVIDER", "pollinations")
        self.image_model = os.getenv("IMAGE_MODEL", "flux")

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