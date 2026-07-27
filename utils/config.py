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
        
        # Project paths
        self.project_root: Path = Path(__file__).parent.parent
        self.output_dir: Path = self.project_root / "output"
        self.images_dir: Path = self.output_dir / "images"
        
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
