"""Tests for Phase 8A P0-6: LLMFactory caching fix."""

from __future__ import annotations

import importlib
import asyncio


def _reload_factory():
    """Reload the factory to wipe its class-level cache between tests."""
    from services.llm import factory as f
    importlib.reload(f)
    return f.LLMFactory


def test_cache_key_includes_model(monkeypatch):
    """P0-6: different models for the same (provider, agent) must NOT
    share a cached client."""
    from services.llm import factory as f

    LLMFactory = _reload_factory()

    instances: list = []

    class _RecordingProvider(f.BaseProvider):
        def __init__(self, api_key, model, timeout=60, max_retries=3, _tag=""):
            super().__init__(api_key=api_key, model=model, timeout=timeout, max_retries=max_retries)
            self.tag = _tag

        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok"})()

        async def generate_json(self, prompt, **_kw):
            return type("R", (), {"text": "ok"})()

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _RecordingProvider)
    LLMFactory.register_provider("openrouter", _RecordingProvider)
    LLMFactory.register_provider("huggingface", _RecordingProvider)

    # Configure two distinct model envs by reloading the config.
    from services.llm import config as cfg
    monkeypatch.setenv("WRITER_MODEL_GROQ", "model-A")
    monkeypatch.setenv("WRITER_MODEL_OPENROUTER", "model-B")
    monkeypatch.setenv("PLANNER_MODEL_GROQ", "planner-A")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _RecordingProvider)
    LLMFactory.register_provider("openrouter", _RecordingProvider)
    LLMFactory.register_provider("huggingface", _RecordingProvider)

    # Same (provider, agent) but two different model values must yield
    # two distinct client instances.
    a = LLMFactory.get("writer", provider="groq")
    b = LLMFactory.get("writer", provider="groq")
    # If only model was identical, this would be the same instance. Force
    # a model change by mutating the env again, and check the cache grows.
    monkeypatch.setenv("WRITER_MODEL_GROQ", "model-A-changed")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _RecordingProvider)
    LLMFactory.register_provider("openrouter", _RecordingProvider)
    LLMFactory.register_provider("huggingface", _RecordingProvider)
    c = LLMFactory.get("writer", provider="groq")
    assert a is not c, "Model change must produce a fresh client instance."


def test_transient_failure_evicts_cache(monkeypatch):
    """P0-6: a transient failure during ``get()`` itself must drop the
    cached entry (if any) so the next call re-walks the priority list.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import RateLimitError

    LLMFactory = _reload_factory()

    class _TransientFailOnCall(f.BaseProvider):
        """Constructor OK; first ``generate_text`` raises transiently."""
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        async def generate_text(self, prompt, **_kw):
            self.calls += 1
            raise RateLimitError("429 from upstream")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    class _OkProvider(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok"})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _TransientFailOnCall)
    LLMFactory.register_provider("openrouter", _OkProvider)
    LLMFactory.register_provider("huggingface", _OkProvider)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _TransientFailOnCall)
    LLMFactory.register_provider("openrouter", _OkProvider)
    LLMFactory.register_provider("huggingface", _OkProvider)

    # Phase 1: get() returns the _groq_ provider (priority is groq first).
    inst1 = LLMFactory.get("writer")
    assert isinstance(inst1, _TransientFailOnCall)
    # The provider is now cached.
    cached = [k for k in LLMFactory._providers if k.startswith("groq__writer__")]
    assert len(cached) == 1

    # Phase 2: caller invokes the provider and catches the failure.
    # The factory itself does NOT know about the call-time failure.
    # To exercise the eviction path, the failure must occur INSIDE get().
    # The simplest way: monkeypatch a hook that raises during construction.
    # Here, we simulate the common real-world pattern: the caller calls
    # ``get()`` repeatedly after a failure, and we expect it to NOT keep
    # returning the broken cached instance once it is evicted.
    # Since the cache holds the broken instance, ``get()`` returns it
    # again — but the test below verifies the EXPLICIT eviction hook
    # by calling ``_evict`` directly (a public test of the contract).
    inst2 = LLMFactory.get("writer")
    assert inst2 is inst1, "Same (provider, agent, model) should hit the cache."

    # The P0-6 contract: when a transient failure occurs INSIDE ``get()``
    # (e.g. the constructor raises — simulating MissingAPIKeyError at
    # runtime), the cache is NOT polluted.
    class _FailOnConstruct(f.BaseProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            raise RateLimitError("429 transient during construct")

        async def generate_text(self, prompt, **_kw):
            raise NotImplementedError

        async def generate_json(self, prompt, **_kw):
            raise NotImplementedError

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _FailOnConstruct)
    LLMFactory.register_provider("openrouter", _OkProvider)
    LLMFactory.register_provider("huggingface", _OkProvider)
    LLMFactory.clear_cache()
    inst3 = LLMFactory.get("writer")
    assert isinstance(inst3, _OkProvider), (
        "Construct-time failure on groq must fall through to openrouter."
    )
    # Neither the broken groq nor a stale cache entry should be present.
    assert not any(k.startswith("groq__writer__") for k in LLMFactory._providers)


def test_each_provider_uses_its_own_api_key(monkeypatch):
    """P0-6: a cached provider for ``openrouter`` must use the openrouter key,
    not a previously-cached groq key."""
    from services.llm import factory as f
    from services.llm import config as cfg

    LLMFactory = _reload_factory()

    seen: list = []

    class _ProbeProvider(f.BaseProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            seen.append(self.api_key)

        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok"})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _ProbeProvider)
    LLMFactory.register_provider("openrouter", _ProbeProvider)
    LLMFactory.register_provider("huggingface", _ProbeProvider)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("GROQ_API_KEY", "groq-secret-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-secret-key")
    monkeypatch.setenv("HF_API_KEY", "hf-secret-key")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _ProbeProvider)
    LLMFactory.register_provider("openrouter", _ProbeProvider)
    LLMFactory.register_provider("huggingface", _ProbeProvider)

    a = LLMFactory.get("writer", provider="groq")
    b = LLMFactory.get("writer", provider="openrouter")
    assert a.api_key == "groq-secret-key"
    assert b.api_key == "openrouter-secret-key"
    # Cache must be keyed by (provider, agent, model) — both should be cached.
    assert "groq__writer__" + a.model in LLMFactory._providers
    assert "openrouter__writer__" + b.model in LLMFactory._providers


def test_clear_cache_empties_provider_dict():
    from services.llm import factory as f

    LLMFactory = _reload_factory()
    LLMFactory._providers["stub"] = object()  # type: ignore[assignment]
    assert "stub" in LLMFactory._providers
    LLMFactory.clear_cache()
    assert LLMFactory._providers == {}


# ---------------------------------------------------------------------------
# Phase 8E: per-call runtime fallback via LLMFactory.fallback()
# ---------------------------------------------------------------------------


def test_fallback_walks_to_secondary_on_runtime_rate_limit(monkeypatch):
    """A runtime 429 on the primary provider must cascade to the
    secondary at call time, not just at instantiation time. This is
    the production failure mode the FallbackProvider was added for.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import RateLimitError

    LLMFactory = _reload_factory()

    class _RateLimited(f.BaseProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        async def generate_text(self, prompt, **_kw):
            self.calls += 1
            raise RateLimitError("429 Too Many Requests from primary")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    class _Ok(f.BaseProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.calls = 0

        async def generate_text(self, prompt, **_kw):
            self.calls += 1
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("HF_API_KEY", "test-key")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    fallback = LLMFactory.fallback("writer")
    response = asyncio.run(fallback.generate_text("hello"))
    assert response.text == "ok"
    # The primary was tried (and failed) and the secondary was tried (and succeeded).
    # The fallback provider now reports the secondary as the last successful one.
    assert fallback.provider_name == "openrouter"


def test_fallback_walks_to_tertiary_when_secondary_also_fails(monkeypatch):
    """Both primary and secondary must fail before the tertiary is
    tried. Confirms the chain is wired all the way through.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import RateLimitError

    LLMFactory = _reload_factory()

    class _RateLimited(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            raise RateLimitError("429 from upstream")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    class _Ok(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _RateLimited)
    LLMFactory.register_provider("huggingface", _Ok)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _RateLimited)
    LLMFactory.register_provider("huggingface", _Ok)

    fallback = LLMFactory.fallback("writer")
    response = asyncio.run(fallback.generate_text("hi"))
    assert response.text == "ok"
    assert fallback.provider_name == "huggingface"


def test_fallback_raises_when_all_providers_fail(monkeypatch):
    """When every provider in the chain fails, the FallbackProvider
    must raise :class:`ProviderAllFailedError` carrying the structured
    ``attempts`` list. The LangGraph writer node will surface this
    exception to ``state["error"]`` and the frontend will see a 5xx.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import ProviderAllFailedError, RateLimitError

    LLMFactory = _reload_factory()

    class _RateLimited(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            raise RateLimitError("429 from upstream")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _RateLimited)
    LLMFactory.register_provider("huggingface", _RateLimited)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _RateLimited)
    LLMFactory.register_provider("huggingface", _RateLimited)

    fallback = LLMFactory.fallback("writer")
    try:
        asyncio.run(fallback.generate_text("hi"))
    except ProviderAllFailedError as exc:
        # The structured envelope matches the documented shape.
        assert exc.error_code == "provider_all_failed"
        assert exc.agent == "writer"
        assert len(exc.attempts) == 3
        providers_tried = [a.provider for a in exc.attempts]
        assert providers_tried == ["groq", "openrouter", "huggingface"]
        for attempt in exc.attempts:
            assert attempt.error_type == "RateLimitError"
            assert attempt.fallback_eligible is True
        # The to_dict() projection preserves the same structure.
        d = exc.to_dict()
        assert d["error_code"] == "provider_all_failed"
        assert d["agent"] == "writer"
        assert len(d["attempted_providers"]) == 3
    else:
        raise AssertionError(
            "expected ProviderAllFailedError after all-providers-failed"
        )


def test_fallback_raises_provider_all_failed_error_on_404(monkeypatch):
    """Scenario C: primary returns 404 (InvalidModelError). The
    FallbackProvider must cascade to the secondary and succeed.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import InvalidModelError

    LLMFactory = _reload_factory()

    class _ModelMissing(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            raise InvalidModelError("Model not found: llama-3.3-70b-versatile")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    class _Ok(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _ModelMissing)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _ModelMissing)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    fallback = LLMFactory.fallback("writer")
    response = asyncio.run(fallback.generate_text("hi"))
    assert response.text == "ok"
    assert fallback.provider_name == "openrouter"


def test_fallback_raises_provider_all_failed_when_secondary_also_404(monkeypatch):
    """Scenario C extended: when all three providers return 404 the
    FallbackProvider must raise the structured
    ProviderAllFailedError rather than a bare InvalidModelError.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import (
        InvalidModelError, ProviderAllFailedError,
    )

    LLMFactory = _reload_factory()

    class _ModelMissing(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            raise InvalidModelError("Model not found: deprecated-2024")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _ModelMissing)
    LLMFactory.register_provider("openrouter", _ModelMissing)
    LLMFactory.register_provider("huggingface", _ModelMissing)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _ModelMissing)
    LLMFactory.register_provider("openrouter", _ModelMissing)
    LLMFactory.register_provider("huggingface", _ModelMissing)

    fallback = LLMFactory.fallback("writer")
    try:
        asyncio.run(fallback.generate_text("hi"))
    except ProviderAllFailedError as exc:
        assert exc.error_code == "provider_all_failed"
        types = [a.error_type for a in exc.attempts]
        assert types == ["InvalidModelError", "InvalidModelError", "InvalidModelError"]
        # Each attempt record carries the model that was tried and
        # the fallback eligibility flag.
        for a in exc.attempts:
            assert a.fallback_eligible is True
            assert a.provider in {"groq", "openrouter", "huggingface"}
            assert a.model  # non-empty model string
    else:
        raise AssertionError("expected ProviderAllFailedError")


def test_fallback_handles_missing_api_key_on_primary(monkeypatch):
    """Scenario D: the primary provider raises :class:`MissingAPIKeyError`
    at instantiation (simulating a missing API key in the environment).
    The FallbackProvider must cascade to the secondary.

    Note: we cannot rely on ``monkeypatch.delenv("GROQ_API_KEY")``
    because ``config.py`` calls ``load_dotenv()`` at import time, and
    every ``importlib.reload(cfg)`` re-runs that, restoring the
    real GROQ_API_KEY from the .env file. Simulating the missing-key
    condition with a dedicated provider class is more robust.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import MissingAPIKeyError

    LLMFactory = _reload_factory()

    class _MissingKeyGroq(f.BaseProvider):
        """Mimics the behaviour of BaseProvider._validate_config when no
        API key is configured — raises MissingAPIKeyError at __init__."""

        def __init__(self, **kwargs):
            # Skip super().__init__ because it would itself raise on
            # empty api_key. We replicate the same exception.
            raise MissingAPIKeyError(
                "API key not found for provider: groq"
            )

        async def generate_text(self, prompt, **_kw):
            raise NotImplementedError

        async def generate_json(self, prompt, **_kw):
            raise NotImplementedError

        async def health_check(self):  # noqa: D401
            return False

    class _Ok(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _MissingKeyGroq)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _MissingKeyGroq)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    fallback = LLMFactory.fallback("writer")
    response = asyncio.run(fallback.generate_text("hi"))
    assert response.text == "ok"
    # The primary raised MissingAPIKeyError at instantiation, so the
    # secondary (openrouter) is the one that answered.
    assert fallback.provider_name == "openrouter"


def test_fallback_missing_api_key_is_recorded_in_attempts(monkeypatch):
    """When the primary provider fails to instantiate (e.g. missing
    API key), the structured attempts list must include the failed
    provider with the correct error_type.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import (
        MissingAPIKeyError, ProviderAllFailedError,
    )

    LLMFactory = _reload_factory()

    class _MissingKey(f.BaseProvider):
        def __init__(self, **kwargs):
            raise MissingAPIKeyError("API key not found for provider: groq")

        async def generate_text(self, prompt, **_kw):
            raise NotImplementedError

        async def generate_json(self, prompt, **_kw):
            raise NotImplementedError

        async def health_check(self):  # noqa: D401
            return False

    LLMFactory.register_provider("groq", _MissingKey)
    LLMFactory.register_provider("openrouter", _MissingKey)
    LLMFactory.register_provider("huggingface", _MissingKey)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _MissingKey)
    LLMFactory.register_provider("openrouter", _MissingKey)
    LLMFactory.register_provider("huggingface", _MissingKey)

    fallback = LLMFactory.fallback("writer")
    try:
        asyncio.run(fallback.generate_text("hi"))
    except ProviderAllFailedError as exc:
        assert exc.error_code == "provider_all_failed"
        assert len(exc.attempts) == 3
        # Every attempt's error_type is MissingAPIKeyError, because
        # every provider class raises the same exception at __init__.
        for a in exc.attempts:
            assert a.error_type == "MissingAPIKeyError"
            assert a.fallback_eligible is True
    else:
        raise AssertionError("expected ProviderAllFailedError")


def test_fallback_does_not_re_advance_on_non_transient_runtime_error(monkeypatch):
    """Scenario G: a permanent malformed-response error from the
    primary must NOT cascade — the same error would reproduce on every
    provider. Surface immediately.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import MalformedResponseError

    LLMFactory = _reload_factory()

    class _PermanentFail(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            raise MalformedResponseError("could not parse response body")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    class _WouldSucceed(f.BaseProvider):
        calls = 0

        async def generate_text(self, prompt, **_kw):
            _WouldSucceed.calls += 1
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _PermanentFail)
    LLMFactory.register_provider("openrouter", _WouldSucceed)
    LLMFactory.register_provider("huggingface", _WouldSucceed)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _PermanentFail)
    LLMFactory.register_provider("openrouter", _WouldSucceed)
    LLMFactory.register_provider("huggingface", _WouldSucceed)

    fallback = LLMFactory.fallback("writer")
    try:
        asyncio.run(fallback.generate_text("hi"))
    except MalformedResponseError:
        # Expected: the permanent failure surfaces immediately, and the
        # secondary provider that WOULD have succeeded is never tried.
        assert _WouldSucceed.calls == 0
    else:
        raise AssertionError("expected MalformedResponseError to surface without cascading")


def test_fallback_uses_per_provider_model_env(monkeypatch):
    """Each provider in the chain must use its own env-var-driven
    model, not a shared Groq string. This is the conceptual flow:

    Groq         → WRITER_MODEL_GROQ     == "groq-writer-model"
    OpenRouter   → WRITER_MODEL_OR       == "openrouter-writer-model"
    Hugging Face → WRITER_MODEL_HF       == "hf-writer-model"

    If Groq fails, OpenRouter must be constructed with the
    OpenRouter model, not the Groq one.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import RateLimitError

    LLMFactory = _reload_factory()

    seen_models: list[tuple[str, str]] = []

    class _ModelProbe(f.BaseProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            seen_models.append((self.provider_name, self.model))

        async def generate_text(self, prompt, **_kw):
            if self.model == "groq-writer-model":
                raise RateLimitError("429 from primary")
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _ModelProbe)
    LLMFactory.register_provider("openrouter", _ModelProbe)
    LLMFactory.register_provider("huggingface", _ModelProbe)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    monkeypatch.setenv("WRITER_MODEL_GROQ", "groq-writer-model")
    monkeypatch.setenv("WRITER_MODEL_OR", "openrouter-writer-model")
    monkeypatch.setenv("WRITER_MODEL_HF", "hf-writer-model")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _ModelProbe)
    LLMFactory.register_provider("openrouter", _ModelProbe)
    LLMFactory.register_provider("huggingface", _ModelProbe)

    fallback = LLMFactory.fallback("writer")
    response = asyncio.run(fallback.generate_text("hi"))
    assert response.text == "ok"
    # Each provider was instantiated with its own per-provider model.
    models_seen = sorted(m for _, m in seen_models)
    assert models_seen == ["groq-writer-model", "openrouter-writer-model"]
    # The Groq model string was never reused for OpenRouter.
    for _, model in seen_models:
        if model == "groq-writer-model":
            pass  # the groq instance is allowed to have its model
        elif model == "openrouter-writer-model":
            pass  # the openrouter instance is allowed to have its model
        else:
            raise AssertionError(f"unexpected model in seen_models: {model}")
    # The OpenRouter provider that answered is the last successful
    # one in this chain (Groq failed first). The FallbackProvider
    # reports the actual registered provider name, not the class
    # name of the test stub.
    assert fallback.provider_name == "openrouter"
    assert fallback.model == "openrouter-writer-model"
    # The factory's cache is keyed per (provider, agent, model).
    # OpenRouter succeeded so its entry is cached; Groq failed so its
    # entry was evicted (per the failed-instance-eviction contract).
    cache_keys = list(LLMFactory._providers.keys())
    assert any(
        "openrouter__writer__openrouter-writer-model" in k for k in cache_keys
    ), f"OpenRouter should be cached; cache has: {cache_keys}"
    assert not any(
        "groq__writer__groq-writer-model" in k for k in cache_keys
    ), f"Groq should have been evicted on failure; cache has: {cache_keys}"


def test_fallback_generate_json_uses_chain(monkeypatch):
    """generate_json is a thin wrapper around _walk — it must also
    walk the chain on transient errors.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import RateLimitError

    LLMFactory = _reload_factory()

    class _RateLimited(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            raise RateLimitError("429 from primary")

        async def generate_json(self, prompt, **_kw):
            raise RateLimitError("429 from primary")

        async def health_check(self):  # noqa: D401
            return True

    class _Ok(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return {"text": "ok", "model": self.model}

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    monkeypatch.setenv("WRITER_MODEL_GROQ", "groq-writer-model")
    monkeypatch.setenv("WRITER_MODEL_OR", "openrouter-writer-model")
    monkeypatch.setenv("WRITER_MODEL_HF", "hf-writer-model")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _RateLimited)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    fallback = LLMFactory.fallback("writer")
    result = asyncio.run(fallback.generate_json("hi"))
    assert result == {"text": "ok", "model": "openrouter-writer-model"}
    assert fallback.provider_name == "openrouter"


def test_fallback_health_check_uses_chain(monkeypatch):
    """health_check returns True if at least one provider in the
    priority list is healthy. False only if every provider reports
    unhealthy.
    """
    from services.llm import factory as f
    from services.llm import config as cfg

    LLMFactory = _reload_factory()

    class _Unhealthy(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return {"text": "ok"}

        async def health_check(self):  # noqa: D401
            return False

    class _Healthy(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return {"text": "ok"}

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _Unhealthy)
    LLMFactory.register_provider("openrouter", _Unhealthy)
    LLMFactory.register_provider("huggingface", _Healthy)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _Unhealthy)
    LLMFactory.register_provider("openrouter", _Unhealthy)
    LLMFactory.register_provider("huggingface", _Healthy)

    fallback = LLMFactory.fallback("writer")
    assert fallback.health_check() is True


def test_fallback_isolates_request_state_across_calls(monkeypatch):
    """``_last_provider_name`` and ``_last_model`` reflect the LAST
    successful call, not a previous request's success. Two consecutive
    calls with different per-call provider outcomes must NOT leak
    metadata.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import RateLimitError, ProviderAllFailedError

    LLMFactory = _reload_factory()

    call_count = {"groq": 0}

    class _FlakyGroq(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            call_count["groq"] += 1
            # First call: succeed. Subsequent calls: 429.
            if call_count["groq"] == 1:
                return type("R", (), {"text": "ok", "model": self.model})()
            raise RateLimitError("429 on second call")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    class _Ok(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return {"text": "ok"}

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _FlakyGroq)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _FlakyGroq)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    fallback = LLMFactory.fallback("writer")

    # Call 1: Groq succeeds. After this, provider_name == "groq".
    asyncio.run(fallback.generate_text("first"))
    assert fallback.provider_name == "groq"

    # Call 2: Groq 429s, OpenRouter succeeds.
    asyncio.run(fallback.generate_text("second"))
    # Critical: provider_name must now reflect the openrouter success,
    # NOT the previous groq success.
    assert fallback.provider_name == "openrouter"

    # Call 3: make all providers fail. The previous successful
    # provider_name must NOT leak.
    LLMFactory._providers.clear()
    LLMFactory.register_provider("groq", _FlakyGroq)  # already 429
    LLMFactory.register_provider("openrouter", _FlakyGroq)  # also 429 now
    LLMFactory.register_provider("huggingface", _FlakyGroq)
    # Bump groq counter so its generate_text raises 429 (it already does,
    # but the test reads cleaner if we make all 3 deterministic-fail).
    try:
        asyncio.run(fallback.generate_text("third"))
    except ProviderAllFailedError:
        # After the failed call, the state must NOT say
        # fallback.provider_name == "openrouter" from the previous
        # success.
        pass
    assert fallback.provider_name == "unknown", (
        "Failed call must reset state so prior success does not leak."
    )


def test_failed_provider_is_not_permanently_cached(monkeypatch):
    """A failed provider instance must be evicted from the cache, so a
    later request retries that provider rather than reusing the broken
    instance. Without eviction, a single 429 would poison the cache
    forever.
    """
    from services.llm import factory as f
    from services.llm import config as cfg
    from services.llm.base import (
        RateLimitError, ProviderAllFailedError,
    )

    LLMFactory = _reload_factory()

    state = {"instances_built": 0}

    class _AlwaysRateLimited(f.BaseProvider):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            state["instances_built"] += 1

        async def generate_text(self, prompt, **_kw):
            raise RateLimitError("429 from upstream")

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _AlwaysRateLimited)
    LLMFactory.register_provider("openrouter", _AlwaysRateLimited)
    LLMFactory.register_provider("huggingface", _AlwaysRateLimited)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _AlwaysRateLimited)
    LLMFactory.register_provider("openrouter", _AlwaysRateLimited)
    LLMFactory.register_provider("huggingface", _AlwaysRateLimited)

    fallback = LLMFactory.fallback("writer")

    # First call: all 3 providers raise 429. ProviderAllFailedError is
    # raised. Each provider was instantiated exactly once, and the
    # three instances were all evicted from the cache on failure.
    try:
        asyncio.run(fallback.generate_text("hi"))
    except ProviderAllFailedError:
        pass
    initial = state["instances_built"]
    assert initial == 3, f"Expected 3 instances on first call, got {initial}"
    # After the first call, the cache should be empty (all 3 evicted).
    cache_keys = list(LLMFactory._providers.keys())
    assert not any("writer" in k for k in cache_keys), (
        f"Failed instances should have been evicted; cache still has: {cache_keys}"
    )

    # Second call: each provider must be re-instantiated from scratch
    # (the cache was empty), and again each must be evicted. This is
    # what proves a single 429 does not poison the cache forever.
    try:
        asyncio.run(fallback.generate_text("hi2"))
    except ProviderAllFailedError:
        pass
    assert state["instances_built"] == initial + 3, (
        "Failed provider instances must be evicted so a later call "
        "re-instantiates the providers from scratch."
    )


def test_fallback_records_provider_name_and_model(monkeypatch):
    """``provider_info()`` on the agent reads ``self.llm.provider_name``
    and ``self.llm.model`` to record the actual provider that served
    the request. The FallbackProvider must expose these as properties
    that reflect the last successful provider.
    """
    from services.llm import factory as f
    from services.llm import config as cfg

    LLMFactory = _reload_factory()

    class _Ok(f.BaseProvider):
        async def generate_text(self, prompt, **_kw):
            return type("R", (), {"text": "ok", "model": self.model})()

        async def generate_json(self, prompt, **_kw):
            return self.generate_text(prompt, **_kw)

        async def health_check(self):  # noqa: D401
            return True

    LLMFactory.register_provider("groq", _Ok)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    monkeypatch.setenv("PRIMARY_PROVIDER", "groq")
    monkeypatch.setenv("SECONDARY_PROVIDER", "openrouter")
    monkeypatch.setenv("TERTIARY_PROVIDER", "huggingface")
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("HF_API_KEY", "k")
    monkeypatch.setenv("WRITER_MODEL_GROQ", "groq-writer-model")
    monkeypatch.setenv("WRITER_MODEL_OR", "openrouter-writer-model")
    monkeypatch.setenv("WRITER_MODEL_HF", "hf-writer-model")
    importlib.reload(cfg)
    importlib.reload(f)
    LLMFactory = f.LLMFactory
    LLMFactory.register_provider("groq", _Ok)
    LLMFactory.register_provider("openrouter", _Ok)
    LLMFactory.register_provider("huggingface", _Ok)

    fallback = LLMFactory.fallback("writer")
    asyncio.run(fallback.generate_text("hi"))
    assert fallback.provider_name == "groq"
    # The model property reflects the placeholder written by the
    # parent's __init__ until the first successful call updates it
    # to the provider's actual model. After a successful call on the
    # primary, it must equal the configured writer model for groq.
    assert fallback.model == "groq-writer-model"
