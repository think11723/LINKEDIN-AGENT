"""Base provider interface for LLM providers."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import time
import random


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class MissingAPIKeyError(ProviderError):
    """Exception raised when API key is missing."""
    pass


class InvalidModelError(ProviderError):
    """Exception raised when model is invalid."""
    pass


class RateLimitError(ProviderError):
    """Exception raised when rate limit is exceeded."""
    pass


class TimeoutError(ProviderError):
    """Exception raised when request times out."""
    pass


class NetworkError(ProviderError):
    """Exception raised when network error occurs."""
    pass


class MalformedResponseError(ProviderError):
    """Exception raised when response is malformed."""
    pass


class UnsupportedModelError(ProviderError):
    """Exception raised when model is not supported."""
    pass


class ProviderUnavailableError(ProviderError):
    """Exception raised when provider is unavailable."""
    pass


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    text: str
    model: str
    latency: float
    tokens_used: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, api_key: str, model: str, timeout: int = 60, max_retries: int = 3):
        """Initialize provider.
        
        Args:
            api_key: API key for the provider
            model: Model name to use
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for retryable errors
        
        Raises:
            MissingAPIKeyError: If API key is empty
            InvalidModelError: If model is empty
        """
        self._validate_config(api_key, model)
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
    
    def _validate_config(self, api_key: str, model: str):
        """Validate configuration during initialization.
        
        Args:
            api_key: API key to validate
            model: Model name to validate
            
        Raises:
            MissingAPIKeyError: If API key is empty
            InvalidModelError: If model is empty
        """
        if not api_key or not api_key.strip():
            raise MissingAPIKeyError(f"API key is required for {self.__class__.__name__}")
        if not model or not model.strip():
            raise InvalidModelError(f"Model name is required for {self.__class__.__name__}")
    
    @abstractmethod
    def generate_text(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate text from prompt.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with generated text and metadata
        """
        pass
    
    @abstractmethod
    def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate JSON from prompt.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dictionary with parsed JSON response
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if provider is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
    
    def _measure_latency(self, func):
        """Measure latency of a function call.
        
        Args:
            func: Function to measure
            
        Returns:
            Tuple of (result, latency_seconds)
        """
        start_time = time.time()
        result = func()
        latency = time.time() - start_time
        return result, latency
    
    def _retry_with_backoff(self, func: Callable, is_retryable: Callable[[Exception], bool]) -> Any:
        """Retry function with exponential backoff.
        
        Args:
            func: Function to retry
            is_retryable: Function that determines if exception is retryable
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    from utils.logger import logger
                    logger.info(f"Retry attempt {attempt}/{self.max_retries} for {self.__class__.__name__} model={self.model}")
                return func()
            except Exception as e:
                last_exception = e
                
                # Check if error is retryable
                if not is_retryable(e):
                    raise
                
                # Don't sleep after last attempt
                if attempt < self.max_retries:
                    # Exponential backoff with jitter
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    from utils.logger import logger
                    logger.info(f"Rate limited or transient error, retrying in {backoff:.2f}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(backoff)
        
        # All retries exhausted
        raise last_exception
    
    def _log_request(self, method: str, prompt: str, latency: float, success: bool, error: Optional[str] = None, http_status: Optional[int] = None):
        """Log request details.
        
        Args:
            method: Method name (generate_text, generate_json, health_check)
            prompt: Input prompt (truncated)
            latency: Request latency in seconds
            success: Whether request succeeded
            error: Error message if failed
            http_status: HTTP status code if available
        """
        from utils.logger import logger
        
        truncated_prompt = prompt[:100] + "..." if len(prompt) > 100 else prompt
        
        if success:
            log_msg = (
                f"LLM Request: provider={self.__class__.__name__}, "
                f"model={self.model}, method={method}, "
                f"latency={latency:.2f}s, success=True"
            )
            if http_status:
                log_msg += f", http_status={http_status}"
            logger.info(log_msg)
        else:
            log_msg = (
                f"LLM Request: provider={self.__class__.__name__}, "
                f"model={self.model}, method={method}, "
                f"latency={latency:.2f}s, success=False"
            )
            if http_status:
                log_msg += f", http_status={http_status}"
            if error:
                log_msg += f", error={error}"
            logger.error(log_msg)
