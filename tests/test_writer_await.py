"""Phase 8E — Writer/Reviewer await fix tests.

Regression coverage for the fix of the
"'coroutine' object has no attribute 'text'" failure. The Writer
and Reviewer used to call ``self.llm.generate_text(...)``
synchronously; the LLM is now async (FallbackProvider walks the
provider chain via ``await``), so the agents must ``await`` the
coroutine. These tests assert that the await is in place and that
the actual response object reaches the agent's parsing code.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Dict, List, Optional

import pytest

from services.llm import base as llm_base
from services.llm import factory as llm_factory


class _StubLLM(llm_base.BaseProvider):
    """Async stub LLM that returns a canned response.

    Mirrors the real LLM contract: ``generate_text`` and
    ``generate_json`` are coroutines.
    """

    def __init__(self, **kwargs: Any) -> None:  # noqa: D401
        # Bypass the real __init__'s API-key validation.
        self.api_key = kwargs.get("api_key", "stub")
        self.model = kwargs.get("model", "stub-model")
        self.timeout = kwargs.get("timeout", 60)
        self.max_retries = kwargs.get("max_retries", 0)
        self.calls: List[Dict[str, Any]] = []

    async def generate_text(self, prompt: str, **kwargs: Any):  # type: ignore[override]
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        return llm_base.LLMResponse(
            text=(
                "TITLE: Stub Title\n"
                "CONTENT: Stub content from the async LLM stub.\n"
                "HASHTAGS: #stub, #test"
            ),
            model="stub-model",
            latency=0.0,
            tokens_used=42,
            metadata={"provider": "stub"},
        )

    async def generate_json(self, prompt: str, **kwargs: Any):  # type: ignore[override]
        return {"text": "stub"}

    def health_check(self) -> bool:  # type: ignore[override]
        return True


def test_writer_awaits_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: WriterAgent.write is async and awaits
    ``self.llm.generate_text(...)``. The previous sync version
    returned a coroutine, which then failed with
    ``'coroutine' object has no attribute 'text'``.
    """
    from agents.writer import WriterAgent
    from models.context_models import Context

    llm_factory.LLMFactory.clear_cache()
    for name in ("groq", "openrouter", "huggingface"):
        llm_factory.LLMFactory.register_provider(name, _StubLLM)

    async def run() -> None:
        writer = WriterAgent()
        # The Writer's LLM is the FallbackProvider from
        # LLMFactory.fallback("writer"). Each provider in the
        # pool is the _StubLLM above, so the chain always
        # succeeds.
        assert inspect.iscoroutinefunction(writer.write)
        result = await writer.write(
            topic="Async topic",
            intent="discuss",
            user_prompt="Async topic",
            research=None,
            writing_style="professional",
            context=Context(),
        )
        assert result is not None
        assert result.title == "Stub Title"
        assert "Stub content" in result.content

    asyncio.run(run())


def test_writer_does_not_receive_a_coroutine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct check for the original bug: after awaiting
    ``writer.write(...)``, the result must be a real
    ``LinkedInPost`` with a ``.content`` attribute, NOT a coroutine.
    """
    from agents.writer import WriterAgent
    from models.context_models import Context

    llm_factory.LLMFactory.clear_cache()
    for name in ("groq", "openrouter", "huggingface"):
        llm_factory.LLMFactory.register_provider(name, _StubLLM)

    async def run() -> None:
        writer = WriterAgent()
        result = await writer.write(
            topic="No coroutine",
            intent="x",
            user_prompt="x",
            research=None,
            writing_style="x",
            context=Context(),
        )
        # The original bug was that result was a coroutine and
        # ``result.content`` raised "'coroutine' object has no
        # attribute 'content'". The fact that this line passes
        # proves the coroutine was awaited.
        assert hasattr(result, "content")
        assert not inspect.iscoroutine(result)

    asyncio.run(run())


def test_reviewer_awaits_llm_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same regression for the Reviewer, which also calls
    ``self.llm.generate_text(...)`` twice (review + improve)."""
    from agents.reviewer import ReviewerAgent
    from models.context_models import Context
    from models.models import LinkedInPost

    llm_factory.LLMFactory.clear_cache()
    for name in ("groq", "openrouter", "huggingface"):
        llm_factory.LLMFactory.register_provider(name, _StubLLM)

    async def run() -> None:
        post = LinkedInPost(
            title="t",
            content="c",
            hashtags=["#a"],
        )
        reviewer = ReviewerAgent()
        assert inspect.iscoroutinefunction(reviewer.review)
        result = await reviewer.review(post, Context())
        assert result is not None
        assert hasattr(result, "scores")

    asyncio.run(run())


def test_provider_fallback_chain_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """The async refactor must NOT remove the provider
    fallback. A primary provider that raises should cascade to
    the secondary; the secondary's response must reach the
    Writer.
    """

    class _BoomLLM(_StubLLM):
        async def generate_text(self, prompt: str, **kwargs: Any):
            raise llm_base.RateLimitError("429 from primary")

    class _OkLLM(_StubLLM):
        async def generate_text(self, prompt: str, **kwargs: Any):
            return llm_base.LLMResponse(
                text=(
                    "TITLE: Cascade Title\n"
                    "CONTENT: Cascade content from secondary.\n"
                    "HASHTAGS: #cascade"
                ),
                model="cascade",
                latency=0.0,
                tokens_used=42,
                metadata={"provider": "secondary"},
            )

    # Clear the LLMFactory cache and register fresh stubs. Without
    # this, a previously-cached provider from a prior test would
    # shadow our _BoomLLM and the test would not exercise the
    # cascade path.
    llm_factory.LLMFactory.clear_cache()
    llm_factory.LLMFactory.register_provider("groq", _BoomLLM)
    llm_factory.LLMFactory.register_provider("openrouter", _OkLLM)
    llm_factory.LLMFactory.register_provider("huggingface", _OkLLM)

    from agents.writer import WriterAgent
    from models.context_models import Context

    async def run() -> None:
        writer = WriterAgent()
        result = await writer.write(
            topic="Cascade",
            intent="x",
            user_prompt="Cascade",
            research=None,
            writing_style="x",
            context=Context(),
        )
        assert result.title == "Cascade Title"
        assert "Cascade content" in result.content

    asyncio.run(run())


def test_image_prompt_agent_awaits_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: ``ImagePromptAgent.generate`` is async and
    awaits the LLM call. The sync version produced a coroutine
    that then failed on ``response.text``."""

    for name in ("groq", "openrouter", "huggingface"):
        llm_factory.LLMFactory.register_provider(name, _StubLLM)
    llm_factory.LLMFactory.clear_cache()

    from agents.image_prompt import ImagePromptAgent
    from models.models import LinkedInPost

    async def run() -> None:
        agent = ImagePromptAgent()
        assert inspect.iscoroutinefunction(agent.generate)
        post = LinkedInPost(title="t", content="c", hashtags=["#a"])
        result = await agent.generate(post)
        assert result is not None
        # The original failure was that result was a coroutine
        # and ``result.prompt`` raised "'coroutine' object has no
        # attribute 'prompt'". The fact that this line passes
        # proves the coroutine was awaited.
        assert hasattr(result, "prompt")

    asyncio.run(run())


def test_huggingface_generate_json_awaits_generate_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: ``HuggingFaceProvider.generate_json`` is async
    and its internal ``self.generate_text`` call is awaited. The
    HuggingFace provider is reached only after Groq and OpenRouter
    both fail in the fallback chain."""

    import importlib
    from services.llm import base as llm_base_mod
    from services.llm.providers import huggingface as hf_mod

    importlib.reload(hf_mod)

    real_generate_text = hf_mod.HuggingFaceProvider.generate_text

    async def fake_text(self, prompt: str, **kwargs: Any):
        # Return text that contains a JSON block, mimicking a
        # model that responded with a JSON object.
        return llm_base_mod.LLMResponse(
            text='```json\n{"answer": 42}\n```',
            model="stub",
            latency=0.0,
            tokens_used=1,
            metadata={"provider": "huggingface"},
        )

    monkeypatch.setattr(
        hf_mod.HuggingFaceProvider, "generate_text", fake_text
    )

    async def run() -> None:
        provider = hf_mod.HuggingFaceProvider(
            api_key="stub", model="stub", timeout=5, max_retries=0
        )
        result = await provider.generate_json("anything")
        assert isinstance(result, dict)
        assert result == {"answer": 42}

    asyncio.run(run())
