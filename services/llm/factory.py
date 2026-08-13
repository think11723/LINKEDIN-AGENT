"""LLM Factory for creating provider instances."""

import logging
from typing import Dict, Optional
from .config import LLMConfig
from .base import BaseProvider, MissingAPIKeyError
from .providers.huggingface import HuggingFaceProvider
from .providers.openrouter import OpenRouterProvider
from .providers.groq import GroqProvider

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM provider instances.

    Phase 8A / P0-6: the cache key is now ``(provider, agent, model)``
    so a model change (env override, A/B swap, hot reload) is picked up
    without a process restart. Cached entries are also evicted on
    transient failure so the next call re-walks the priority list.
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
    def get(cls, agent: str, provider: Optional[str] = None) -> BaseProvider:
        """Get or create a provider instance for an agent with fallback logic.

        Args:
            agent: Agent name (planner, writer, reviewer, research)
            provider: Provider name (defaults to priority order)

        Returns:
            BaseProvider instance

        Raises:
            ValueError: If agent or provider is unknown
            MissingAPIKeyError: If API key is missing for all providers
        """
        # Use provider priority if none specified
        if provider is None:
            provider_priority = LLMConfig.get_provider_priority()
        else:
            provider_priority = [provider]

        # Try each provider in priority order
        last_error = None
        for i, current_provider in enumerate(provider_priority):
            model = LLMConfig.get_model(agent, current_provider)
            cache_key = cls._cache_key(current_provider, agent, model)

            try:
                logger.info(f"Using Provider: {current_provider} (model={model})")

                # Return cached instance if available.
                # P0-6: cache key includes the model so different models
                # for the same (provider, agent) never share a client.
                if cache_key in cls._providers:
                    return cls._providers[cache_key]

                # Get provider class
                if current_provider not in cls._provider_classes:
                    raise ValueError(f"Unknown provider: {current_provider}")

                provider_class = cls._provider_classes[current_provider]

                # Get API key
                api_key = LLMConfig.get_api_key(current_provider)
                if not api_key:
                    raise MissingAPIKeyError(
                        f"API key not found for provider: {current_provider}"
                    )

                # Get timeout
                timeout = LLMConfig.get_timeout()

                # Create provider instance
                provider_instance = provider_class(
                    api_key=api_key, model=model, timeout=timeout
                )

                # Cache instance
                cls._providers[cache_key] = provider_instance

                return provider_instance

            except Exception as e:
                last_error = e
                error_str = str(e)

                # P0-6: on transient failure, drop the cached entry (if
                # any) so the next call re-walks the priority list and
                # the runner is not stuck on a now-down provider.
                cls._evict(cache_key)

                if LLMConfig.is_transient_error(e):
                    logger.warning(f"Provider failed: {current_provider} (model={model})")
                    logger.warning(f"Reason: {error_str}")

                    if i < len(provider_priority) - 1:
                        next_provider = provider_priority[i + 1]
                        logger.info(f"Switching to {next_provider}")
                        continue
                    logger.error(f"All providers failed. Last error: {error_str}")
                    raise
                logger.error(
                    f"Non-transient error with provider {current_provider}: {error_str}"
                )
                raise

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
