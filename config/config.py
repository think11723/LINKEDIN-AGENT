"""Configuration module for LinkedIn Content Agent.

This module handles loading environment variables and provides
a clean interface for accessing configuration settings.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration class for the LinkedIn Content Agent."""
    
    def __init__(self) -> None:
        """Initialize configuration with environment variables."""
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        self.model_name: Optional[str] = os.getenv("MODEL_NAME", "gemini-1.5-flash")
        self.linkedin_access_token: Optional[str] = os.getenv("LINKEDIN_ACCESS_TOKEN")
        self.linkedin_client_id: Optional[str] = os.getenv("LINKEDIN_CLIENT_ID")
        self.linkedin_client_secret: Optional[str] = os.getenv("LINKEDIN_CLIENT_SECRET")
        
        # Email configuration
        self.smtp_host: Optional[str] = os.getenv("SMTP_HOST")
        self.smtp_port: Optional[str] = os.getenv("SMTP_PORT")
        self.smtp_username: Optional[str] = os.getenv("SMTP_USERNAME")
        self.smtp_password: Optional[str] = os.getenv("SMTP_PASSWORD")
        self.email_from: Optional[str] = os.getenv("EMAIL_FROM")
        self.email_to: Optional[str] = os.getenv("EMAIL_TO")
        
        # Image generation configuration
        self.image_provider: str = os.getenv("IMAGE_PROVIDER", "pollinations")
        self.image_model: str = os.getenv("IMAGE_MODEL", "flux")
        self.image_size: str = os.getenv("IMAGE_SIZE", "1024x1024")
        self.image_style: str = os.getenv("IMAGE_STYLE", "professional")
        self.image_required: bool = os.getenv("IMAGE_REQUIRED", "false").lower() == "true"
        self.image_retry_count: int = int(os.getenv("IMAGE_RETRY_COUNT", "3"))
        self.enable_image_generation: bool = os.getenv("ENABLE_IMAGE_GENERATION", "true").lower() == "true"
        
        # Project paths
        self.project_root: Path = Path(__file__).parent.parent
        self.output_dir: Path = self.project_root / "output"
        self.images_dir: Path = self.output_dir / "images"
        self.database_dir: Path = self.project_root / "database"
        
        # Ensure output directories exist
        self._create_directories()
    
    def _create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.output_dir.mkdir(exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)
    
    def validate(self) -> bool:
        """Validate that required configuration is present.
        
        Returns:
            bool: True if required configuration is valid, False otherwise.
        """
        if not self.gemini_api_key:
            return False
        return True


# Global configuration instance
config = Config()
