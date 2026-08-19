"""LLM Factory for creating provider instances."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from .config import LLMConfig
from .base import (
    BaseProvider,
    LLMResponse,
    MissingAPIKeyError,
    ProviderAllFailedError,
    ProviderAttempt,
)
from .providers.huggingface import HuggingFaceProvider
from .providers.openrouter import OpenRouterProvider
from .providers.groq import GroqProvider

logger = logging.getLogger(__name__)


# Patterns that look like a secret. Match bearer tokens, sk-*,
# ghp_*, AIza*, AKIA*, JSON-style private keys, and long opaque
# strings. Used by ``_safe_error_message`` to scrub the error string
# before it reaches the structured envelope.
_SECRET_PATTERNS = [
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-or-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9]{8,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{8,}"),
    re.compile(r"hf_[A-Za-z0-9]{8,}"),
    re.compile(r"gsk_[A-Za-z0-9]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def _safe_error_message(exc: BaseException) -> str:
    """Return a single-line, secret-free string for a provider error."""
    msg = str(exc).replace("\n", " ").replace("\r", " ").strip()
    for pat in _SECRET_PATTERNS:
        msg = pat.sub("[REDACTED]", msg)
    if len(msg) > 240:
        msg = msg[:237] + "..."
    return msg


class FallbackProvider(BaseProvider):
    """A composite provider that walks the priority list on every call.

    ``LLMFactory.get(agent)`` returns a single cached provider — the
    fallback loop in that method only runs at instantiation, so a
    runtime 429 / 404 / 401 / 5xx on the first provider in the priority
    list would never reach the second or third.

    ``FallbackProvider`` closes that gap. It looks like a ``BaseProvider``
    to the agent (same ``generate_text`` / ``generate_json`` signature)
    but on every call it:

      1. Iterates the configured provider priority list.
      2. Reuses the factory's per-(provider, agent, model) cache, so a
         healthy provider is not re-instantiated.
      3. On a transient failure (rate limit, model-not-found, auth,
         timeout, network, 5xx) it evicts the cache key for that
         provider and advances to the next one.
      4. On a non-transient failure, it surfaces the error directly
         because the same error would be reproduced on every provider.
      5. When every provider has been tried and failed, it raises
         :class:`ProviderAllFailedError` carrying a structured
         ``attempts`` list (provider, model, error_type, error_message,
         fallback_eligible) so the workflow and frontend can report
         exactly which providers were tried and why each one failed.

    The model is resolved per provider via
    :py:meth:`LLMFactory._instantiate`, which calls
    :py:meth:`LLMConfig.get_model` with the specific provider name.
    So Groq uses ``WRITER_MODEL_GROQ``, OpenRouter uses
    ``WRITER_MODEL_OR``, Hugging Face uses ``WRITER_MODEL_HF`` — never
    a single shared model string.

    ``provider_name`` and ``model`` are properties that return the
    **last successful** provider/model from the most recent call.
    They are reset to ``"unknown"`` at the start of every call so
    metadata from one request never leaks into the next.
    """

    def __init__(self, agent: str) -> None:
        # The base class requires api_key/model; we don't have one until
        # the first successful call, so use placeholders that pass
        # _validate_config (non-empty). The real values are tracked per
        # call via ``_last_provider_name`` and ``_last_model``.
        super().__init__(api_key="fallback", model="fallback", timeout=60)
        self._agent = agent
        self._last_provider_name: str = "unknown"
        self._last_model: str = "unknown"

    @property
    def provider_name(self) -> str:
        return self._last_provider_name

    @property
    def model(self) -> str:
        # ``BaseProvider.__init__`` assigns ``self.model = model``; the
        # parent treats that as a plain instance attribute. To expose a
        # dynamic ``model`` here, we shadow the attribute with a
        # property backed by ``_last_model``, plus a setter so the
        # parent's constructor can write the placeholder.
        return self._last_model

    @model.setter
    def model(self, value: str) -> None:
        self._last_model = value

    def _record_attempt(
        self,
        attempts: List[ProviderAttempt],
        provider: str,
        model: str,
        exc: BaseException,
    ) -> None:
        attempts.append(
            ProviderAttempt(
                provider=provider,
                model=model,
                error_type=type(exc).__name__,
                error_message=_safe_error_message(exc),
                fallback_eligible=LLMConfig.is_fallback_eligible_error(exc),
            )
        )

    def _walk(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """Call ``method_name`` on each provider in priority order.

        Resets ``_last_provider_name`` and ``_last_model`` at entry so a
        request that starts and fails (or never reaches a provider) does
        not leak the previous request's success metadata.
        """
        # Reset per-request state. The properties are read by the
        # agent's ``provider_info()`` *after* the call returns; if this
        # call fails and the next one succeeds on a different
        # provider, the metadata must reflect the new success.
        self._last_provider_name = "unknown"
        self._last_model = "unknown"

        provider_priority = LLMConfig.get_provider_priority()
        if not provider_priority:
            raise RuntimeError(
                f"No LLM providers configured for agent {self._agent!r}. "
                f"Set PRIMARY_PROVIDER / SECONDARY_PROVIDER / TERTIARY_PROVIDER."
            )

        attempts: List[ProviderAttempt] = []
        last_error: Optional[BaseException] = None

        for i, current_provider in enumerate(provider_priority):
            # Resolve the per-provider model fresh on every iteration.
            # ``_instantiate`` consults ``LLMConfig.get_model(agent,
            # provider)`` which reads the provider-specific env var, so
            # Groq uses WRITER_MODEL_GROQ, OpenRouter uses
            # WRITER_MODEL_OR, Hugging Face uses WRITER_MODEL_HF.
            try:
                instance, model = LLMFactory._instantiate(
                    current_provider, self._agent
                )
            except Exception as e:
                last_error = e
                # If instantiation failed because the model env var is
                # not configured, we still need a model string for the
                # attempt record. Use a placeholder; the error_type
                # carries the real reason.
                recorded_model = LLMConfig.get_model(
                    self._agent, current_provider
                ) or "unknown"
                self._record_attempt(
                    attempts, current_provider, recorded_model, e
                )
                if LLMConfig.is_fallback_eligible_error(e):
                    logger.warning(
                        "FallbackProvider(%s): provider %s could not be "
                        "instantiated: %s; trying next provider.",
                        self._agent, current_provider, e,
                    )
                    if i < len(provider_priority) - 1:
                        continue
                    break
                # Non-transient at instantiation: do not try to call
                # the others for the same reason. Surface immediately.
                raise

            try:
                method = getattr(instance, method_name)
                response = method(*args, **kwargs)
            except Exception as e:
                last_error = e
                self._record_attempt(
                    attempts, current_provider, model, e
                )
                # Evict the cached client for this provider so the next
                # call to LLMFactory.get() builds a fresh one. The
                # underlying error may be transient (rate limit, 5xx)
                # and the existing client may have a stale circuit
                # state.
                LLMFactory._evict(
                    LLMFactory._cache_key(current_provider, self._agent, model)
                )
                if LLMConfig.is_fallback_eligible_error(e):
                    logger.warning(
                        "FallbackProvider(%s): provider %s (model=%s) "
                        "raised transient error: %s; trying next provider.",
                        self._agent, current_provider, model, e,
                    )
                    if i < len(provider_priority) - 1:
                        continue
                    break
                # Non-transient at runtime (e.g. 400 invalid prompt
                # schema). Do not try the other providers — they would
                # fail identically. Surface immediately.
                logger.error(
                    "FallbackProvider(%s): provider %s (model=%s) raised "
                    "non-transient error: %s",
                    self._agent, current_provider, model, e,
                )
                raise

            # Success. Remember which provider actually answered.
            self._last_provider_name = current_provider
            self._last_model = model
            logger.info(
                "FallbackProvider(%s): %s (model=%s) succeeded.",
                self._agent, current_provider, model,
            )
            return response

        # All providers failed. Raise a structured exception.
        logger.error(
            "FallbackProvider(%s): all %d provider(s) failed. Attempts: %s",
            self._agent,
            len(attempts),
            [
                {
                    "provider": a.provider,
                    "model": a.model,
                    "error_type": a.error_type,
                }
                for a in attempts
            ],
        )
        raise ProviderAllFailedError(self._agent, attempts)

    def generate_text(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self._walk("generate_text", prompt, **kwargs)

    def generate_json(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return self._walk("generate_json", prompt, **kwargs)

    def health_check(self) -> bool:
        """True if at least one provider in the priority list is healthy."""
        for current_provider in LLMConfig.get_provider_priority():
            try:
                instance, _ = LLMFactory._instantiate(current_provider, self._agent)
            except Exception:
                continue
            try:
                if instance.health_check():
                    return True
            except Exception:
                continue
        return False


class LLMFactory:
    """Factory for creating LLM provider instances.

    Phase 8A / P0-6: the cache key is now ``(provider, agent, model)``
    so a model change (env override, A/B swap, hot reload) is picked up
    without a process restart. Cached entries are also evicted on
    transient failure so the next call re-walks the priority list.

    Phase 8E: the cache miss path was extracted into
    :py:meth:`_instantiate` so :class:`FallbackProvider` can reuse it
    for per-call provider iteration.
    """

    _providers: Dict[str, BaseProvider] = {}
    _provider_classes: Dict[str, type] = {
        "huggingface": HuggingFaceProvider,
        "openrouter": OpenRouterProvider,
        "groq": GroqProvider,
    }

    @classmethod
    def _cache_key(cls, provider: str, agent: str, model: str) -> str:
        return f"{provider}__{agent}__{model}"

    @classmethod
    def _evict(cls, key: str) -> None:
        cls._providers.pop(key, None)

    @classmethod
    def _instantiate(cls, provider: str, agent: str) -> tuple[BaseProvider, str]:
        """Return ``(instance, model)`` for a single provider.

        Reuses the per-``(provider, agent, model)`` cache; on cache hit
        returns the cached instance. On cache miss, builds a new one
        using the configured API key, model, and timeout.

        Raises:
            ValueError: If ``provider`` is not in ``_provider_classes``.
            MissingAPIKeyError: If no API key is configured for
                ``provider`` in the environment.
        """
        model = LLMConfig.get_model(agent, provider)
        cache_key = cls._cache_key(provider, agent, model)

        if cache_key in cls._providers:
            logger.info(
                "Using Provider: %s (model=%s) [cached]", provider, model
            )
            return cls._providers[cache_key], model

        if provider not in cls._provider_classes:
            raise ValueError(f"Unknown provider: {provider}")

        api_key = LLMConfig.get_api_key(provider)
        if not api_key:
            raise MissingAPIKeyError(
                f"API key not found for provider: {provider}"
            )

        timeout = LLMConfig.get_timeout()
        provider_class = cls._provider_classes[provider]
        instance = provider_class(api_key=api_key, model=model, timeout=timeout)
        cls._providers[cache_key] = instance

        logger.info("Using Provider: %s (model=%s) [new]", provider, model)
        return instance, model

    @classmethod
    def get(cls, agent: str, provider: Optional[str] = None) -> BaseProvider:
        """Get a single provider instance for ``agent``.

        The factory walks the priority list at *instantiation time* only.
        For runtime fallback across providers on every call, use
        :py:meth:`fallback` instead.

        Args:
            agent: Agent name (planner, writer, reviewer, research).
            provider: If set, restrict to a single provider (no
                fallback). If ``None``, walk the configured priority list.

        Returns:
            A single :class:`BaseProvider` instance.

        Raises:
            ValueError: If ``agent`` or ``provider`` is unknown.
            MissingAPIKeyError: If the API key is missing for all
                candidate providers.
        """
        if provider is None:
            provider_priority = LLMConfig.get_provider_priority()
        else:
            provider_priority = [provider]

        last_error: Optional[BaseException] = None
        for i, current_provider in enumerate(provider_priority):
            try:
                instance, model = cls._instantiate(current_provider, agent)
                return instance
            except Exception as e:
                last_error = e
                if LLMConfig.is_fallback_eligible_error(e):
                    logger.warning(
                        "Provider failed at instantiation: %s — %s",
                        current_provider, e,
                    )
                    if i < len(provider_priority) - 1:
                        continue
                    raise
                logger.error(
                    "Non-transient error with provider %s: %s",
                    current_provider, e,
                )
                raise
        # Unreachable: the loop either returns or raises.
        assert last_error is not None
        raise last_error

    @classmethod
    def fallback(cls, agent: str) -> FallbackProvider:
        """Return a :class:`FallbackProvider` that retries across the
        configured priority list on every call.

        This is the recommended entry point for runtime LLM resilience.
        The returned object is a :class:`BaseProvider` subclass and
        exposes ``generate_text`` / ``generate_json`` / ``health_check``
        with the same signatures, so the agent code that previously
        called ``LLMFactory.get(agent)`` does not need to change except
        for the factory method name.

        Example::

            self.llm = LLMFactory.fallback("writer")
            response = self.llm.generate_text(prompt, temperature=0.7)
        """
        return FallbackProvider(agent)

    @classmethod
    def clear_cache(cls):
        """Clear all cached provider instances."""
        cls._providers.clear()

    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a custom provider class.

        Args:
            name: Provider name
            provider_class: Provider class (must inherit from BaseProvider)
        """
        if not issubclass(provider_class, BaseProvider):
            raise ValueError(f"Provider class must inherit from BaseProvider")
        cls._provider_classes[name] = provider_class
