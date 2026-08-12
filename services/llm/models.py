"""Model definitions for LLM providers."""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    name: str
    provider: str
    context_length: int
    supports_json: bool = True
    supports_streaming: bool = False
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None


# Available models
AVAILABLE_MODELS: Dict[str, ModelConfig] = {
    # Hugging Face models
    "Qwen/Qwen2.5-72B-Instruct": ModelConfig(
        name="Qwen/Qwen2.5-72B-Instruct",
        provider="huggingface",
        context_length=32768,
        supports_json=True,
    ),
    "deepseek-ai/DeepSeek-V3": ModelConfig(
        name="deepseek-ai/DeepSeek-V3",
        provider="huggingface",
        context_length=64000,
        supports_json=True,
    ),
    
    # OpenRouter models
    "qwen/qwen-2.5-72b-instruct": ModelConfig(
        name="qwen/qwen-2.5-72b-instruct",
        provider="openrouter",
        context_length=32768,
        supports_json=True,
    ),
    "deepseek/deepseek-chat": ModelConfig(
        name="deepseek/deepseek-chat",
        provider="openrouter",
        context_length=64000,
        supports_json=True,
    ),
    
    # Groq models
    "llama-3.3-70b-versatile": ModelConfig(
        name="llama-3.3-70b-versatile",
        provider="groq",
        context_length=131072,
        supports_json=True,
    ),
    "deepseek-r1-distill-llama-70b": ModelConfig(
        name="deepseek-r1-distill-llama-70b",
        provider="groq",
        context_length=65536,
        supports_json=True,
    ),
}


def get_model_config(model_name: str) -> Optional[ModelConfig]:
    """Get model configuration by name.
    
    Args:
        model_name: Name of the model
        
    Returns:
        ModelConfig if found, None otherwise
    """
    return AVAILABLE_MODELS.get(model_name)
