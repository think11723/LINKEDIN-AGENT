"""Base Image Provider Abstraction.

Defines the interface for image generation providers.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ImageGenerationError(Exception):
    """Base exception for image generation errors."""
    pass


class TransientImageError(ImageGenerationError):
    """Exception for transient errors that can be retried."""
    pass


class PermanentImageError(ImageGenerationError):
    """Exception for permanent errors that cannot be retried."""
    pass


class BaseImageProvider(ABC):
    """Abstract base class for image generation providers."""
    
    def __init__(self, config: dict):
        """Initialize the image provider.
        
        Args:
            config: Provider-specific configuration.
        """
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self) -> None:
        """Validate provider configuration.
        
        Raises:
            ValueError: If configuration is invalid.
        """
        pass
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        output_path: Path,
        width: int = 1024,
        height: int = 1024,
        **kwargs
    ) -> Path:
        """Generate an image from a prompt.
        
        Args:
            prompt: Text prompt for image generation.
            output_path: Path where the image should be saved.
            width: Image width in pixels.
            height: Image height in pixels.
            **kwargs: Additional provider-specific parameters.
            
        Returns:
            Path to the generated image.
            
        Raises:
            TransientImageError: For retryable errors.
            PermanentImageError: For non-retryable errors.
            ImageGenerationError: For general errors.
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the provider.
        
        Returns:
            Provider name string.
        """
        pass
    
    def health_check(self) -> bool:
        """Check if the provider is available and configured correctly.
        
        Returns:
            True if provider is healthy, False otherwise.
        """
        try:
            self._validate_config()
            return True
        except Exception as e:
            logger.warning(f"Provider health check failed: {e}")
            return False
