"""Image Validation Utility.

Validates generated images before publishing to ensure they meet quality standards.
"""

import logging
from pathlib import Path
from typing import Tuple
from PIL import Image
import io

logger = logging.getLogger(__name__)


class ImageValidationError(Exception):
    """Exception raised when image validation fails."""
    pass


class ImageValidator:
    """Validator for generated images."""
    
    # Supported image formats
    SUPPORTED_FORMATS = {'.png', '.jpg', '.jpeg', '.webp'}
    
    # Minimum and maximum dimensions
    MIN_WIDTH = 600
    MIN_HEIGHT = 600
    MAX_WIDTH = 4096
    MAX_HEIGHT = 4096
    
    # Maximum file size (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    
    # Minimum file size (1KB)
    MIN_FILE_SIZE = 1024
    
    def __init__(self):
        """Initialize the image validator."""
        pass
    
    def validate(self, image_path: Path) -> Tuple[bool, str]:
        """Validate an image file.
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            # Check file exists
            if not image_path.exists():
                return False, f"Image file does not exist: {image_path}"
            
            # Check file extension
            if image_path.suffix.lower() not in self.SUPPORTED_FORMATS:
                return False, f"Unsupported image format: {image_path.suffix}. Supported: {self.SUPPORTED_FORMATS}"
            
            # Check file size
            file_size = image_path.stat().st_size
            if file_size < self.MIN_FILE_SIZE:
                return False, f"Image file too small: {file_size} bytes (minimum: {self.MIN_FILE_SIZE})"
            
            if file_size > self.MAX_FILE_SIZE:
                return False, f"Image file too large: {file_size} bytes (maximum: {self.MAX_FILE_SIZE})"
            
            # Try to open and validate the image
            try:
                with Image.open(image_path) as img:
                    # Check dimensions
                    width, height = img.size
                    
                    if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                        return False, f"Image dimensions too small: {width}x{height} (minimum: {self.MIN_WIDTH}x{self.MIN_HEIGHT})"
                    
                    if width > self.MAX_WIDTH or height > self.MAX_HEIGHT:
                        return False, f"Image dimensions too large: {width}x{height} (maximum: {self.MAX_WIDTH}x{self.MAX_HEIGHT})"
                    
                    # Verify image can be loaded
                    img.verify()
                    
                    # Re-open after verify (verify closes the file)
                    with Image.open(image_path) as img_verify:
                        # Check if image is corrupted by loading it
                        img_verify.load()
                    
                    logger.info(f"Image validation passed: {image_path} ({width}x{height}, {file_size} bytes)")
                    return True, "Image validation passed"
                    
            except Image.UnidentifiedImageError:
                return False, "Image file is corrupted or not a valid image"
            except Image.DecompressionBombError:
                return False, "Image file is too large to process (decompression bomb)"
            except Exception as e:
                return False, f"Failed to validate image: {str(e)}"
                
        except Exception as e:
            logger.error(f"Unexpected error during image validation: {e}")
            return False, f"Unexpected validation error: {str(e)}"
    
    def validate_for_linkedin(self, image_path: Path) -> Tuple[bool, str]:
        """Validate image specifically for LinkedIn upload requirements.
        
        LinkedIn requires:
        - PNG, JPEG, or GIF format
        - Maximum 5MB file size
        - Recommended aspect ratio: 1.91:1 to 1:1
        
        Args:
            image_path: Path to the image file.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            # First run basic validation
            is_valid, message = self.validate(image_path)
            if not is_valid:
                return False, message
            
            # LinkedIn-specific checks
            file_size = image_path.stat().st_size
            linkedin_max_size = 5 * 1024 * 1024  # 5MB
            
            if file_size > linkedin_max_size:
                return False, f"Image exceeds LinkedIn's 5MB limit: {file_size} bytes"
            
            # Check aspect ratio (LinkedIn recommends 1.91:1 to 1:1)
            with Image.open(image_path) as img:
                width, height = img.size
                aspect_ratio = width / height
                
                if aspect_ratio < 0.8 or aspect_ratio > 2.0:
                    logger.warning(f"Image aspect ratio {aspect_ratio:.2f} is outside LinkedIn's recommended range (1.91:1 to 1:1)")
                    # This is a warning, not a hard failure
            
            logger.info(f"LinkedIn validation passed: {image_path}")
            return True, "LinkedIn validation passed"
            
        except Exception as e:
            logger.error(f"Error during LinkedIn validation: {e}")
            return False, f"LinkedIn validation error: {str(e)}"
    
    def validate_image_data(self, image_data: bytes) -> Tuple[bool, str]:
        """Validate image data directly (from memory).
        
        Args:
            image_data: Raw image data as bytes.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        try:
            # Check data size
            if len(image_data) < self.MIN_FILE_SIZE:
                return False, f"Image data too small: {len(image_data)} bytes"
            
            if len(image_data) > self.MAX_FILE_SIZE:
                return False, f"Image data too large: {len(image_data)} bytes"
            
            # Try to load image from bytes
            try:
                with Image.open(io.BytesIO(image_data)) as img:
                    # Check dimensions
                    width, height = img.size
                    
                    if width < self.MIN_WIDTH or height < self.MIN_HEIGHT:
                        return False, f"Image dimensions too small: {width}x{height}"
                    
                    if width > self.MAX_WIDTH or height > self.MAX_HEIGHT:
                        return False, f"Image dimensions too large: {width}x{height}"
                    
                    # Verify image
                    img.verify()
                    
                    logger.info(f"Image data validation passed: {width}x{height}, {len(image_data)} bytes")
                    return True, "Image data validation passed"
                    
            except Image.UnidentifiedImageError:
                return False, "Image data is corrupted or not a valid image"
            except Exception as e:
                return False, f"Failed to validate image data: {str(e)}"
                
        except Exception as e:
            logger.error(f"Unexpected error during image data validation: {e}")
            return False, f"Unexpected validation error: {str(e)}"


def validate_image(image_path: Path, for_linkedin: bool = True) -> Tuple[bool, str]:
    """Convenience function to validate an image.
    
    Args:
        image_path: Path to the image file.
        for_linkedin: Whether to validate for LinkedIn requirements.
        
    Returns:
        Tuple of (is_valid, error_message).
    """
    validator = ImageValidator()
    
    if for_linkedin:
        return validator.validate_for_linkedin(image_path)
    else:
        return validator.validate(image_path)


if __name__ == "__main__":
    # Test the validator
    import sys
    
    print("Testing Image Validator\n")
    
    if len(sys.argv) > 1:
        # Validate provided image
        image_path = Path(sys.argv[1])
        is_valid, message = validate_image(image_path)
        
        if is_valid:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
    else:
        print("Usage: python image_validator.py <image_path>")
        print("\nExample:")
        print("  python image_validator.py output/images/test.png")
