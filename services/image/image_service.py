"""Image Generation Service.

Provides image generation with provider abstraction, retry logic, and validation.
"""

import time
import logging
from pathlib import Path
from typing import Optional, Dict
from config.config import config
from utils.image_validator import ImageValidator, ImageValidationError
from .base_provider import BaseImageProvider, ImageGenerationError, TransientImageError, PermanentImageError
from .pollinations_provider import PollinationsProvider

logger = logging.getLogger(__name__)


class ImageService:
    """Service for generating images with retry logic and validation."""
    
    # Provider registry
    PROVIDERS = {
        "pollinations": PollinationsProvider,
    }
    
    def __init__(self):
        """Initialize the image service."""
        self.provider = self._get_provider()
        self.validator = ImageValidator()
        self.max_retries = config.image_retry_count
        self.enabled = config.enable_image_generation
        self.required = config.image_required
    
    def _get_provider(self) -> BaseImageProvider:
        """Get the configured image provider.
        
        Returns:
            Configured provider instance.
            
        Raises:
            ValueError: If provider is not supported.
        """
        provider_name = config.image_provider.lower()
        
        if provider_name not in self.PROVIDERS:
            raise ValueError(f"Unsupported image provider: {provider_name}. Supported: {list(self.PROVIDERS.keys())}")
        
        provider_class = self.PROVIDERS[provider_name]
        provider_config = {
            "timeout": 60,
        }
        
        return provider_class(provider_config)
    
    def generate_image(
        self,
        prompt: str,
        filename: str,
        width: int = 1024,
        height: int = 1024,
        validate: bool = True
    ) -> Optional[Path]:
        """Generate an image with retry logic and validation.
        
        Args:
            prompt: Text prompt for image generation.
            filename: Output filename.
            width: Image width in pixels.
            height: Image height in pixels.
            validate: Whether to validate the generated image.
            
        Returns:
            Path to the generated image, or None if failed and not required.
            
        Raises:
            ImageGenerationError: If image generation fails and is required.
        """
        if not self.enabled:
            logger.info("Image generation is disabled in configuration")
            return None
        
        output_path = config.images_dir / filename
        
        logger.info(f"Starting image generation: {prompt[:100]}...")
        logger.info(f"Provider: {self.provider.get_provider_name()}")
        logger.info(f"Output: {output_path}")
        logger.info(f"Size: {width}x{height}")
        
        # Generate with retry logic
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Image generation attempt {attempt + 1}/{self.max_retries}")
                
                # Generate image
                image_path = self.provider.generate(
                    prompt=prompt,
                    output_path=output_path,
                    width=width,
                    height=height
                )
                
                logger.info(f"Image generated successfully: {image_path}")
                
                # Validate if requested
                if validate:
                    logger.info("Validating generated image...")
                    is_valid, message = self.validator.validate_for_linkedin(image_path)
                    
                    if not is_valid:
                        error_msg = f"Image validation failed: {message}"
                        logger.error(error_msg)
                        
                        if attempt < self.max_retries - 1:
                            logger.warning(f"Retrying due to validation failure...")
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            if self.required:
                                raise ImageGenerationError(error_msg)
                            else:
                                logger.warning(f"Image validation failed but not required, continuing without image")
                                return None
                
                return image_path
                
            except TransientImageError as e:
                logger.warning(f"Transient error on attempt {attempt + 1}: {e}")
                
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    error_msg = f"Image generation failed after {self.max_retries} attempts: {e}"
                    logger.error(error_msg)
                    
                    if self.required:
                        raise ImageGenerationError(error_msg)
                    else:
                        logger.warning(f"Image generation failed but not required, continuing without image")
                        return None
                    
            except PermanentImageError as e:
                error_msg = f"Permanent image generation error: {e}"
                logger.error(error_msg)
                
                if self.required:
                    raise ImageGenerationError(error_msg)
                else:
                    logger.warning(f"Permanent error but image not required, continuing without image")
                    return None
                    
            except Exception as e:
                error_msg = f"Unexpected error during image generation: {e}"
                logger.error(error_msg)
                
                if self.required:
                    raise ImageGenerationError(error_msg)
                else:
                    logger.warning(f"Unexpected error but image not required, continuing without image")
                    return None
        
        # Should not reach here, but just in case
        if self.required:
            raise ImageGenerationError("Image generation failed")
        return None
    
    def health_check(self) -> bool:
        """Check if the image service is healthy.
        
        Returns:
            True if service is healthy, False otherwise.
        """
        if not self.enabled:
            logger.info("Image generation is disabled")
            return True
        
        return self.provider.health_check()
