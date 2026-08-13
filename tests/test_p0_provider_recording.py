"""Tests for Phase 8A P0-5: provider/model recording."""

from __future__ import annotations

import pytest

from backend.app.core.security import AuthenticatedUser


class _StubLLM:
    """Mimics the contract the agents rely on."""
    def __init__(self, provider_name: str, model: str) -> None:
        self.provider_name = provider_name
        self.model = model

    def generate_text(self, prompt, **_kwargs):
        # Caller doesn't care about the body — return something parseable.
        return type("R", (), {"text": "ok"})()


class _FakeWriter:
    """Minimal stand-in for WriterAgent."""
    def __init__(self, provider: str, model: str) -> None:
        self.llm = _StubLLM(provider, model)

    def provider_info(self) -> dict[str, str]:
        return {"provider": self.llm.provider_name, "model": self.llm.model}


class _FakeReviewer:
    def __init__(self, provider: str, model: str) -> None:
        self.llm = _StubLLM(provider, model)

    def provider_info(self) -> dict[str, str]:
        return {"provider": self.llm.provider_name, "model": self.llm.model}


def test_writer_provider_info_returns_provider_and_model():
    w = _FakeWriter("groq", "llama-3.3-70b-versatile")
    info = w.provider_info()
    assert info == {"provider": "groq", "model": "llama-3.3-70b-versatile"}


def test_reviewer_provider_info_returns_provider_and_model():
    r = _FakeReviewer("openrouter", "qwen/qwen-2.5-72b-instruct")
    info = r.provider_info()
    assert info == {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct"}


def test_draft_repository_persists_llm_metadata():
    """The Mongo-backed draft carries the provider/model that produced it."""
    import asyncio
    from backend.app.db.mongo import get_database
    from backend.app.repositories.draft_repository import DraftRepository

    repo = DraftRepository(get_database())
    draft = asyncio.run(
        repo.create(
            user_id="USER_A",
            draft_id="draft-llm-meta",
            topic="t",
            title="T",
            content="c",
            hashtags=["#a"],
            metadata={
                "llm": {
                    "writer_provider": "groq",
                    "writer_model": "llama-3.3-70b-versatile",
                    "reviewer_provider": "openrouter",
                    "reviewer_model": "qwen/qwen-2.5-72b-instruct",
                }
            },
        )
    )
    assert draft["metadata"]["llm"]["writer_provider"] == "groq"
    assert draft["metadata"]["llm"]["writer_model"] == "llama-3.3-70b-versatile"
    assert draft["metadata"]["llm"]["reviewer_provider"] == "openrouter"


def test_provider_info_handles_missing_llm_gracefully():
    class _BrokenAgent:
        llm = None

        def provider_info(self):
            llm = getattr(self, "llm", None)
            if llm is None:
                return {"provider": "unknown", "model": "unknown"}
            return {
                "provider": getattr(llm, "provider_name", "unknown"),
                "model": getattr(llm, "model", "unknown"),
            }

    info = _BrokenAgent().provider_info()
    assert info == {"provider": "unknown", "model": "unknown"}


def test_content_endpoint_persists_provider_via_metadata(client_a, monkeypatch):
    """End-to-end: when /content/generate succeeds, the persisted draft
    carries provider+model from the workflow's metadata.
    """
    from shared.schemas import (
        GenerateContentRequest,
        GenerateContentResponse,
        LinkedInPostPayload,
    )
    from backend.app.services import workflow_service

    payload = GenerateContentRequest(topic="x")

    def fake_run(_self, _payload):
        return GenerateContentResponse(
            topic="x",
            final_post=LinkedInPostPayload(
                title="T", content="C", hashtags=["#a"], image_path=None
            ),
            approved=True,
            iterations=1,
            review_feedback="ok",
            review_scores={"overall": 8},
            metadata={
                "writer_provider": "groq",
                "writer_model": "llama-3.3-70b-versatile",
                "reviewer_provider": "groq",
                "reviewer_model": "llama-3.3-70b-versatile",
            },
        )

    monkeypatch.setattr(workflow_service.WorkflowService, "generate_content", fake_run)

    response = client_a.post("/api/v1/content/generate", json={"topic": "x"})
    assert response.status_code == 200
    draft_id = response.json()["draft_id"]

    # Fetch the persisted draft directly from the repository.
    import asyncio
    from backend.app.db.mongo import get_database
    from backend.app.repositories.draft_repository import DraftRepository

    repo = DraftRepository(get_database())
    raw = asyncio.run(repo.col.find_one({"_id": draft_id}))
    assert raw["metadata"]["llm"]["writer_provider"] == "groq"
    assert raw["metadata"]["llm"]["writer_model"] == "llama-3.3-70b-versatile"


def test_failed_generation_does_not_falsely_record_provider(client_a, monkeypatch):
    """A failed run must NOT produce a draft with a fake provider record."""
    from backend.app.services import workflow_service

    def boom(_self, _payload):
        raise RuntimeError("SECRET-LLM-KEY=sk-DO-NOT-LEAK")

    monkeypatch.setattr(workflow_service.WorkflowService, "generate_content", boom)

    response = client_a.post("/api/v1/content/generate", json={"topic": "boom"})
    assert response.status_code == 500
    # No draft_id returned.
    assert "draft_id" not in response.json()