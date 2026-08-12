"""Pollinations.ai Image Provider.

Free image generation provider using Pollinations.ai.
"""

import requests
import urllib.parse
import time
from pathlib import Path
from typing import Optional
import logging

from .base_provider import BaseImageProvider, TransientImageError, PermanentImageError, ImageGenerationError

logger = logging.getLogger(__name__)


class PollinationsProvider(BaseImageProvider):
    """Image provider using Pollinations.ai (free service)."""
    
    BASE_URL = "https://image.pollinations.ai/prompt/"
    
    def __init__(self, config: dict):
        """Initialize Pollinations provider.
        
        Args:
            config: Provider configuration (can be empty for Pollinations).
        """
        super().__init__(config)
        self.timeout = config.get("timeout", 60)
    
    def _validate_config(self) -> None:
        """Validate Pollinations configuration.
        
        Pollinations doesn't require any configuration, so this always passes.
        """
        pass
    
    def generate(
        self,
        prompt: str,
        output_path: Path,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        nologo: bool = True,
        **kwargs
    ) -> Path:
        """Generate an image using Pollinations.ai.
        
        Args:
            prompt: Text prompt for image generation.
            output_path: Path where the image should be saved.
            width: Image width in pixels.
            height: Image height in pixels.
            seed: Optional seed for reproducibility.
            nologo: Whether to remove the logo.
            **kwargs: Additional parameters (ignored).
            
        Returns:
            Path to the generated image.
            
        Raises:
            TransientImageError: For network timeouts, rate limits.
            PermanentImageError: For invalid parameters, permanent failures.
            ImageGenerationError: For other errors.
        """
        logger.info(f"Generating image with Pollinations.ai: {prompt[:100]}...")
        
        try:
            # Encode the prompt for URL
            encoded_prompt = urllib.parse.quote(prompt)
            
            # Build full URL with parameters
            url = f"{self.BASE_URL}{encoded_prompt}"
            url += f"?width={width}&height={height}"
            
            if nologo:
                url += "&nologo=true"
            
            if seed is None:
                seed = hash(prompt)
            url += f"&seed={seed}"
            
            logger.debug(f"Pollinations URL: {url[:100]}...")
            
            # Download the image
            response = requests.get(url, timeout=self.timeout)
            
            # Check for rate limiting
            if response.status_code == 429:
                raise TransientImageError("Rate limited by Pollinations.ai")
            
            # Check for server errors
            if response.status_code >= 500:
                raise TransientImageError(f"Pollinations.ai server error: {response.status_code}")
            
            # Check for client errors
            if response.status_code >= 400:
                raise PermanentImageError(f"Pollinations.ai client error: {response.status_code}")
            
            # Ensure we got image content
            content_type = response.headers.get('content-type', '')
            if 'image' not in content_type:
                raise PermanentImageError(f"Unexpected content type: {content_type}")
            
            # Save to output path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Image generated successfully: {output_path} ({len(response.content)} bytes)")
            return output_path
            
        except requests.Timeout as e:
            raise TransientImageError(f"Request timeout: {str(e)}")
        except requests.ConnectionError as e:
            raise TransientImageError(f"Connection error: {str(e)}")
        except requests.RequestException as e:
            raise ImageGenerationError(f"Request failed: {str(e)}")
        except IOError as e:
            raise ImageGenerationError(f"Failed to save image: {str(e)}")
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "Pollinations.ai"
