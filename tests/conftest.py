"""Test fixtures: in-memory Mongo via mongomock-motor + stubbed Firebase auth."""

from __future__ import annotations

import os
from typing import Iterator

# Ensure required env vars exist BEFORE the app is imported.
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("MONGODB_DB_NAME", "linkedin_agent_test")
os.environ.setdefault(
    "LINKEDIN_TOKEN_ENCRYPTION_KEY",
    "e4B9HfVJbcPkx-_geylkqWSA3L9LucX6pbpwtCHjLdQ=",
)

import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient


@pytest.fixture(autouse=True)
def mock_mongo(monkeypatch) -> Iterator[None]:
    """Replace the Motor client with an in-memory mock for every test."""
    client = AsyncMongoMockClient()
    db = client["linkedin_agent_test"]

    import backend.app.db.mongo as mongo_mod

    async def fake_ping() -> None:
        return None

    monkeypatch.setattr(mongo_mod, "_client", client)
    monkeypatch.setattr(mongo_mod, "_db", db)
    monkeypatch.setattr(mongo_mod, "ping_mongo", fake_ping)

    yield


@pytest.fixture
def firebase_uid_a() -> str:
    return "USER_A"


@pytest.fixture
def firebase_uid_b() -> str:
    return "USER_B"


class _StubUser:
    def __init__(self, uid: str, email: str | None = None) -> None:
        self.uid = uid
        self.email = email or f"{uid}@example.com"
        self.email_verified = True
        self.name = uid
        self.picture = None


@pytest.fixture
def user_a(monkeypatch, firebase_uid_a) -> _StubUser:
    from backend.app.core import security

    def fake_verify(token: str, app=None) -> dict:
        return {
            "uid": token,
            "email": f"{token}@example.com",
            "email_verified": True,
            "name": token,
            "sub": token,
        }

    monkeypatch.setattr(security.firebase_auth, "verify_id_token", fake_verify)
    return _StubUser(firebase_uid_a)


@pytest.fixture
def user_b(monkeypatch, firebase_uid_b) -> _StubUser:
    from backend.app.core import security

    def fake_verify(token: str, app=None) -> dict:
        return {
            "uid": token,
            "email": f"{token}@example.com",
            "email_verified": True,
            "name": token,
            "sub": token,
        }

    monkeypatch.setattr(security.firebase_auth, "verify_id_token", fake_verify)
    return _StubUser(firebase_uid_b)


@pytest.fixture(autouse=True)
def stub_firebase_init(monkeypatch) -> Iterator[None]:
    """Skip Firebase Admin SDK initialisation during tests."""
    class _StubApp:
        project_id = "test-project"

    import backend.app.main as main_module

    monkeypatch.setattr(main_module, "init_firebase", lambda settings: _StubApp())
    monkeypatch.setattr(
        "backend.app.core.security.init_firebase",
        lambda settings: _StubApp(),
    )
    monkeypatch.setattr(
        "backend.app.core.security._firebase_app", _StubApp(), raising=False
    )

    # Don't start the scheduler runner during tests.
    class _StubRunner:
        def start(self) -> None:
            return None

        async def stop(self) -> None:
            return None

    monkeypatch.setattr(
        "backend.app.main.SchedulerRunner", lambda poll_interval=5.0: _StubRunner()
    )
    yield


@pytest.fixture
def client_a(user_a) -> Iterator[TestClient]:
    from backend.app.main import app

    with TestClient(app, headers={"Authorization": f"Bearer {user_a.uid}"}) as c:
        yield c


@pytest.fixture
def client_b(user_b) -> Iterator[TestClient]:
    from backend.app.main import app

    with TestClient(app, headers={"Authorization": f"Bearer {user_b.uid}"}) as c:
        yield c


@pytest.fixture
def client_anon() -> Iterator[TestClient]:
    from backend.app.main import app

    with TestClient(app) as c:
        yield c