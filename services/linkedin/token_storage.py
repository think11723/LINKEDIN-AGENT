"""Token Storage Module

Securely stores and retrieves LinkedIn authentication tokens locally.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from utils.logger import logger


class TokenStorage:
    """Manages secure local storage of authentication tokens."""
    
    def __init__(self, storage_dir: str = ".tokens"):
        """Initialize token storage.
        
        Args:
            storage_dir: Directory to store tokens (default: .tokens)
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.token_file = self.storage_dir / "linkedin_token.json"
    
    def save_token(self, token: Dict) -> bool:
        """Save authentication token to local storage.
        
        Args:
            token: Token dictionary from OAuth authentication
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add metadata
            token_data = {
                "access_token": token.get("access_token"),
                "refresh_token": token.get("refresh_token"),
                "token_type": token.get("token_type", "Bearer"),
                "expires_in": token.get("expires_in"),
                "expires_at": self._calculate_expiry(token.get("expires_in")),
                "scope": token.get("scope"),
                "saved_at": datetime.utcnow().isoformat()
            }
            
            with open(self.token_file, "w") as f:
                json.dump(token_data, f, indent=2)
            
            # Set file permissions (read/write for owner only)
            os.chmod(self.token_file, 0o600)
            
            return True
        except Exception as e:
            raise Exception(f"Failed to save token: {str(e)}")
    
    def load_token(self) -> Optional[Dict]:
        """Load authentication token from local storage.
        
        Returns:
            Token dictionary if exists, None otherwise
        """
        try:
            if not self.token_file.exists():
                return None
            
            with open(self.token_file, "r") as f:
                token_data = json.load(f)
            
            # Check if token is expired
            if self._is_token_expired(token_data):
                return None
            
            return token_data
        except Exception as e:
            raise Exception(f"Failed to load token: {str(e)}")
    
    def delete_token(self) -> bool:
        """Delete stored authentication token.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.token_file.exists():
                self.token_file.unlink()
            return True
        except Exception as e:
            raise Exception(f"Failed to delete token: {str(e)}")
    
    def is_authenticated(self) -> bool:
        """Check if a valid token exists.
        
        Returns:
            True if authenticated, False otherwise
        """
        token = self.load_token()
        return token is not None
    
    def get_expiry_time(self) -> Optional[datetime]:
        """Get the expiry time of the stored token.
        
        Returns:
            Datetime of expiry, or None if no token
        """
        token = self.load_token()
        if token and "expires_at" in token:
            return datetime.fromisoformat(token["expires_at"])
        return None
    
    def _calculate_expiry(self, expires_in: Optional[int]) -> str:
        """Calculate the expiry timestamp.
        
        Args:
            expires_in: Seconds until expiry
            
        Returns:
            ISO format expiry timestamp
        """
        if not expires_in:
            # Default to 60 days if not provided
            expires_in = 60 * 24 * 60 * 60
        
        expiry = datetime.utcnow().timestamp() + expires_in
        return datetime.utcfromtimestamp(expiry).isoformat()
    
    def _is_token_expired(self, token_data: Dict) -> bool:
        """Check if token is expired.
        
        Args:
            token_data: Token dictionary
            
        Returns:
            True if expired, False otherwise
        """
        if "expires_at" not in token_data:
            return True
        
        try:
            expiry = datetime.fromisoformat(token_data["expires_at"])
            return datetime.utcnow() >= expiry
        except:
            return True
