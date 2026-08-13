"""Generate Firebase ID tokens for Phase 7.10 smoke tests via real signUp/signInWithPassword."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local", override=True)
load_dotenv(ROOT / "frontend" / ".env", override=False)

api_key = os.environ.get("VITE_FIREBASE_API_KEY")
if not api_key:
    raise SystemExit("VITE_FIREBASE_API_KEY is required")

USERS = [
    ("USER_A", "live-user-a@example.com", "TestPass123!"),
    ("USER_B", "live-user-b@example.com", "TestPass456!"),
]

endpoint_signup = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signUp"
)
endpoint_signin = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
)


def try_signup(email, password):
    return requests.post(
        endpoint_signup, params={"key": api_key}, json={
            "email": email, "password": password, "returnSecureToken": True,
        }, timeout=15,
    )


def signin(email, password):
    return requests.post(
        endpoint_signin, params={"key": api_key}, json={
            "email": email, "password": password, "returnSecureToken": True,
        }, timeout=15,
    )


tokens = {}
import sys

for uid, email, password in USERS:
    r = try_signup(email, password)
    if r.status_code != 200:
        # user probably exists — sign in
        r = signin(email, password)
        r.raise_for_status()
    payload = r.json()
    tokens[uid] = {
        "id_token": payload["idToken"],
        "refresh_token": payload.get("refreshToken"),
        "local_id": payload.get("localId"),
        "email": payload.get("email"),
        "expires_in": payload.get("expiresIn"),
    }
    print(f"  {uid} ({email}) -> id token len={len(payload['idToken'])} expires_in={payload.get('expiresIn')}s", file=sys.stderr)

print(json.dumps({"project_id": "linkedin-agent-46782", "tokens": tokens}, indent=2))