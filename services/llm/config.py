"""Configuration for LLM providers."""

import os
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class LLMConfig:
    """Configuration for LLM providers."""
    
    # Provider priority (fallback order)
    PRIMARY_PROVIDER = os.getenv("PRIMARY_PROVIDER", "groq")
    SECONDARY_PROVIDER = os.getenv("SECONDARY_PROVIDER", "huggingface")
    TERTIARY_PROVIDER = os.getenv("TERTIARY_PROVIDER", "openrouter")
    
    # Legacy support (maps to PRIMARY_PROVIDER)
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", PRIMARY_PROVIDER)
    
    # API Keys
    HF_API_KEY = os.getenv("HF_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    
    # Default timeout
    DEFAULT_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
    
    # Model mappings
    MODEL_MAPPINGS: Dict[str, Dict[str, str]] = {
        "planner": {
            "huggingface": os.getenv("PLANNER_MODEL_HF", "Qwen/Qwen2.5-72B-Instruct"),
            "openrouter": os.getenv("PLANNER_MODEL_OR", "qwen/qwen-2.5-72b-instruct"),
            "groq": os.getenv("PLANNER_MODEL_GROQ", "llama-3.3-70b-versatile"),
        },
        "writer": {
            "huggingface": os.getenv("WRITER_MODEL_HF", "Qwen/Qwen2.5-72B-Instruct"),
            "openrouter": os.getenv("WRITER_MODEL_OR", "qwen/qwen-2.5-72b-instruct"),
            "groq": os.getenv("WRITER_MODEL_GROQ", "llama-3.3-70b-versatile"),
        },
        "reviewer": {
            "huggingface": os.getenv("REVIEWER_MODEL_HF", "deepseek-ai/DeepSeek-V3"),
            "openrouter": os.getenv("REVIEWER_MODEL_OR", "deepseek/deepseek-chat"),
            "groq": os.getenv("REVIEWER_MODEL_GROQ", "deepseek-r1-distill-llama-70b"),
        },
        "research": {
            "huggingface": os.getenv("RESEARCH_MODEL_HF", "deepseek-ai/DeepSeek-V3"),
            "openrouter": os.getenv("RESEARCH_MODEL_OR", "deepseek/deepseek-chat"),
            "groq": os.getenv("RESEARCH_MODEL_GROQ", "deepseek-r1-distill-llama-70b"),
        },
    }
    
    @classmethod
    def get_api_key(cls, provider: str) -> str:
        """Get API key for provider.
        
        Args:
            provider: Provider name (huggingface, openrouter, groq)
            
        Returns:
            API key string
            
        Raises:
            ValueError: If provider is unknown
        """
        keys = {
            "huggingface": cls.HF_API_KEY,
            "openrouter": cls.OPENROUTER_API_KEY,
            "groq": cls.GROQ_API_KEY,
        }
        
        if provider not in keys:
            raise ValueError(f"Unknown provider: {provider}")
        
        return keys[provider]
    
    @classmethod
    def get_model(cls, agent: str, provider: Optional[str] = None) -> str:
        """Get model for agent and provider.
        
        Args:
            agent: Agent name (planner, writer, reviewer, research)
            provider: Provider name (defaults to DEFAULT_PROVIDER)
            
        Returns:
            Model name string
            
        Raises:
            ValueError: If agent or provider is unknown
        """
        if provider is None:
            provider = cls.DEFAULT_PROVIDER
        
        if agent not in cls.MODEL_MAPPINGS:
            raise ValueError(f"Unknown agent: {agent}")
        
        if provider not in cls.MODEL_MAPPINGS[agent]:
            raise ValueError(f"Unknown provider: {provider}")
        
        return cls.MODEL_MAPPINGS[agent][provider]
    
    @classmethod
    def get_provider_priority(cls) -> list:
        """Get provider priority list.
        
        Returns:
            List of provider names in priority order
        """
        primary = os.getenv("PRIMARY_PROVIDER", "groq")
        secondary = os.getenv("SECONDARY_PROVIDER", "huggingface")
        tertiary = os.getenv("TERTIARY_PROVIDER", "openrouter")
        return [primary, secondary, tertiary]
    
    @classmethod
    def get_timeout(cls) -> int:
        """Get default timeout.
        
        Returns:
            Timeout in seconds
        """
        return cls.DEFAULT_TIMEOUT
    
    @classmethod
    def is_fallback_eligible_error(cls, error: Exception) -> bool:
        """Check if the error means the next provider in the priority
        list should be tried.

        Args:
            error: Exception to check.

        Returns:
            True if the FallbackProvider should advance to the next
            provider, False if the same error would be reproduced on
            every provider (and the caller should surface it
            immediately).

        Notes:
            This is the **fallback** predicate, not the **retry**
            predicate. The two answer different questions:

            * Retry (see :py:meth:`BaseProvider._is_retryable_error`) —
              "would the same provider succeed if we tried again
              right now?" True only for transient errors
              (rate limit, timeout, network).

            * Fallback (this method) — "would a *different* provider
              plausibly succeed?" True for transient errors AND for
              provider-specific errors (model not on this provider,
              auth on this provider, schema unsupported here).

            Concretely:

            * 429 / 5xx / 503 / 502 / 504 / 408 — primary degraded;
              try secondary.
            * timeout / network / connection / unavailable — primary
              unreachable; try secondary.
            * 404 / "not found" / "model not found" — model absent on
              primary; the next provider may have it.
            * "unsupported" / "endpoint" — schema unsupported here;
              another provider may support it.
            * 401 / 403 / unauthorized / forbidden / "invalid api
              key" / credentials — auth error on this provider; the
              next provider has a different key.

            A permanent error (e.g. an obviously-malformed user prompt
            that the provider rejects with a 4xx that is not in the
            list above) is NOT fallback-eligible. It would reproduce
            on every provider, so the FallbackProvider surfaces it
            immediately. The whole chain is only tried for errors that
            the next provider might actually handle differently.
        """
        error_str = str(error).lower()

        fallback_patterns = [
            # Transient + fallback-eligible.
            "timeout",
            "rate limit",
            "429",
            "503",
            "502",
            "504",
            "501",
            "500",
            "408",
            "connection",
            "network",
            "unavailable",
            "temporary",
            # Not transient, but fallback-eligible: model absence /
            # schema mismatch / endpoint unsupported on this provider.
            "not found",
            "404",
            "unsupported",
            "endpoint",
            # Not transient, but fallback-eligible: the next provider
            # has a different API key.
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "invalid api key",
            "credentials",
        ]

        for pattern in fallback_patterns:
            if pattern in error_str:
                return True

        return False

    # Backwards-compatible alias for code that still references the
    # original name. New code should use is_fallback_eligible_error.
    is_transient_error = is_fallback_eligible_error
