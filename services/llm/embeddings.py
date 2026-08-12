"""Embedding provider abstraction for LLM providers."""

from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass


@dataclass
class EmbeddingResponse:
    """Response from embedding provider."""
    embedding: List[float]
    model: str
    latency: float
    metadata: dict = None


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""
    
    def __init__(self, api_key: str, model: str, timeout: int = 60):
        """Initialize embedding provider.
        
        Args:
            api_key: API key for the provider
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
    
    @abstractmethod
    def generate_embedding(self, text: str) -> EmbeddingResponse:
        """Generate embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            EmbeddingResponse with embedding vector and metadata
        """
        pass


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """Hugging Face embedding provider using free inference API."""
    
    BASE_URL = "https://api-inference.huggingface.co/models"
    
    def generate_embedding(self, text: str) -> EmbeddingResponse:
        """Generate embedding using Hugging Face feature extraction API.
        
        Args:
            text: Text to embed
            
        Returns:
            EmbeddingResponse with embedding vector
        """
        import requests
        import time
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": text
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                f"{self.BASE_URL}/{self.model}",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            latency = time.time() - start_time
            
            if response.status_code != 200:
                raise Exception(f"Hugging Face API error: {response.status_code}")
            
            result = response.json()
            
            # Handle different response formats
            if isinstance(result, list):
                embedding = result[0] if isinstance(result[0], list) else result
            elif isinstance(result, dict):
                embedding = result.get("embeddings", result.get("embedding", []))
            else:
                embedding = list(result)
            
            return EmbeddingResponse(
                embedding=embedding,
                model=self.model,
                latency=latency,
                metadata={"provider": "huggingface"}
            )
            
        except Exception as e:
            raise Exception(f"Failed to generate embedding: {str(e)}")


class OpenRouterEmbeddingProvider(BaseEmbeddingProvider):
    """OpenRouter embedding provider (placeholder - not yet implemented)."""
    
    def generate_embedding(self, text: str) -> EmbeddingResponse:
        """Generate embedding using OpenRouter.
        
        Note: OpenRouter does not currently provide a dedicated embedding API.
        This is a placeholder for future implementation.
        """
        raise NotImplementedError("OpenRouter does not currently provide embedding API")


class GroqEmbeddingProvider(BaseEmbeddingProvider):
    """Groq embedding provider (placeholder - not yet implemented)."""
    
    def generate_embedding(self, text: str) -> EmbeddingResponse:
        """Generate embedding using Groq.
        
        Note: Groq does not currently provide a dedicated embedding API.
        This is a placeholder for future implementation.
        """
        raise NotImplementedError("Groq does not currently provide embedding API")


class EmbeddingFactory:
    """Factory for creating embedding provider instances."""
    
    _providers = {
        "huggingface": HuggingFaceEmbeddingProvider,
        "openrouter": OpenRouterEmbeddingProvider,
        "groq": GroqEmbeddingProvider,
    }
    
    _default_models = {
        "huggingface": "sentence-transformers/all-MiniLM-L6-v2",
        "openrouter": None,
        "groq": None,
    }
    
    @classmethod
    def get(cls, provider: str = "huggingface", api_key: str = None, model: str = None) -> BaseEmbeddingProvider:
        """Get or create an embedding provider instance.
        
        Args:
            provider: Provider name (huggingface, openrouter, groq)
            api_key: API key for the provider
            model: Model name to use (defaults to provider default)
            
        Returns:
            BaseEmbeddingProvider instance
            
        Raises:
            ValueError: If provider is unknown or not supported
        """
        if provider not in cls._providers:
            raise ValueError(f"Unknown embedding provider: {provider}")
        
        provider_class = cls._providers[provider]
        
        # Use default model if not specified
        if model is None:
            model = cls._default_models[provider]
        
        if model is None:
            raise ValueError(f"Embedding provider '{provider}' requires explicit model specification")
        
        return provider_class(api_key=api_key, model=model)
