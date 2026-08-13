"""Firebase Admin SDK initialisation and FastAPI auth dependency."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from backend.app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_FIREBASE_APP_NAME = "linkedin-agent-saas"

_firebase_app: Optional[firebase_admin.App] = None


@dataclass(frozen=True)
class AuthenticatedUser:
    """Verified Firebase identity exposed to FastAPI handlers."""

    uid: str
    email: Optional[str]
    email_verified: bool
    name: Optional[str]
    picture: Optional[str]


def init_firebase(settings: Settings) -> firebase_admin.App:
    """Initialise the Firebase Admin SDK exactly once.

    Prefers ``FIREBASE_CREDENTIALS_PATH`` (path to a service-account JSON file).
    Falls back to ``FIREBASE_CREDENTIALS_JSON`` (raw JSON string in env).
    """
    global _firebase_app

    try:
        firebase_admin.get_app(_FIREBASE_APP_NAME)
        _firebase_app = firebase_admin.get_app(_FIREBASE_APP_NAME)
        return _firebase_app
    except ValueError:
        pass

    settings.require_firebase()

    cred: credentials.BaseCredential
    if settings.firebase_credentials_path:
        path = Path(settings.firebase_credentials_path).expanduser()
        if not path.exists():
            raise RuntimeError(
                f"FIREBASE_CREDENTIALS_PATH points to {path} which does not exist."
            )
        cred = credentials.Certificate(str(path))
    else:
        try:
            cred_dict = json.loads(settings.firebase_credentials_json or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "FIREBASE_CREDENTIALS_JSON is not valid JSON."
            ) from exc
        if not cred_dict:
            raise RuntimeError("FIREBASE_CREDENTIALS_JSON is empty.")
        cred = credentials.Certificate(cred_dict)

    project_id = settings.firebase_project_id or cred.project_id  # type: ignore[attr-defined]
    options: dict = {}
    if project_id:
        options["projectId"] = project_id

    _firebase_app = firebase_admin.initialize_app(cred, options, name=_FIREBASE_APP_NAME)
    logger.info("Firebase Admin SDK initialised for project %s", project_id)
    return _firebase_app


def get_firebase_app() -> firebase_admin.App:
    if _firebase_app is None:
        raise RuntimeError(
            "Firebase Admin SDK is not initialised. Call init_firebase() during startup."
        )
    return _firebase_app


def _decode_bearer_token(token: str) -> dict:
    app = get_firebase_app()
    try:
        return firebase_auth.verify_id_token(token, app=app)
    except firebase_auth.ExpiredIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except firebase_auth.RevokedIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has been revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except firebase_auth.InvalidIdTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected error verifying Firebase ID token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> AuthenticatedUser:
    """FastAPI dependency that returns the verified Firebase identity."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _decode_bearer_token(token.strip())

    uid = claims.get("uid") or claims.get("user_id") or claims.get("sub")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token did not contain a user id.",
        )

    return AuthenticatedUser(
        uid=str(uid),
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified", False)),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


CurrentUser = Depends(get_current_user)