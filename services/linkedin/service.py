"""LinkedIn Service for LinkedIn Content Agent.

This module provides a unified service for LinkedIn authentication and publishing.
"""

import os
from typing import Optional, Dict
from services.linkedin.auth import LinkedInAuth
from services.linkedin.publisher import LinkedInPublisher
from services.linkedin.token_storage import TokenStorage
from config.config import config
from utils.logger import logger


class LinkedInService:
    """Service for LinkedIn authentication and publishing."""
    
    def __init__(self):
        """Initialize LinkedIn Service."""
        self.token_storage = TokenStorage()
        self.auth: Optional[LinkedInAuth] = None
        self.publisher: Optional[LinkedInPublisher] = None
        self.person_urn: Optional[str] = None
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with LinkedIn.
        
        Returns:
            True if authenticated, False otherwise.
        """
        return self.token_storage.is_authenticated()
    
    def authenticate(self) -> bool:
        """Authenticate with LinkedIn.
        
        This method handles the OAuth flow:
        1. Check if valid token exists
        2. If not, initiate OAuth flow
        3. Save token to storage
        4. Retrieve member URN
        
        Returns:
            True if authentication successful, False otherwise.
        """
        logger.info("Authentication started")
        
        try:
            # Check if already authenticated
            if self.is_authenticated():
                logger.info("Already authenticated, loading existing token")
                token = self.token_storage.load_token()
                self._setup_with_token(token)
                return True
            
            # Get LinkedIn credentials from config
            client_id = os.getenv("LINKEDIN_CLIENT_ID")
            client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
            redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/callback")
            
            if not client_id or not client_secret:
                logger.error("LinkedIn credentials not found in environment")
                return False
            
            # Initialize auth
            self.auth = LinkedInAuth(client_id, client_secret, redirect_uri)
            
            # Get authorization URL
            auth_url = self.auth.get_authorization_url()
            logger.info(f"Authorization URL generated: {auth_url}")
            
            # For CLI, we need user to visit URL and provide callback
            print(f"\nPlease visit this URL to authorize: {auth_url}")
            print("After authorization, paste the full callback URL here:")
            
            callback_url = input("Callback URL: ").strip()
            
            # Fetch token
            token = self.auth.fetch_token(callback_url)
            
            # Save token
            self.token_storage.save_token(token)
            logger.info("Authentication completed")
            
            # Setup with token
            self._setup_with_token(token)
            
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            return False
    
    def _setup_with_token(self, token: Dict) -> None:
        """Setup auth and publisher with token.
        
        Args:
            token: OAuth token dictionary.
        """
        # Get credentials
        client_id = os.getenv("LINKEDIN_CLIENT_ID")
        client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
        redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/callback")
        
        # Initialize auth with token
        self.auth = LinkedInAuth(client_id, client_secret, redirect_uri)
        self.auth.token = token
        
        # Get authenticated session
        session = self.auth.get_authenticated_session(token)
        
        # Get member URN
        self.person_urn = self.auth.get_member_urn(session)
        
        # Initialize publisher
        self.publisher = LinkedInPublisher(session, self.person_urn)
    
    def publish_post(self, title: str, content: str, hashtags: list, image_path: Optional[str] = None) -> Dict:
        """Publish a post to LinkedIn.
        
        Args:
            title: Post title.
            content: Post content.
            hashtags: List of hashtags.
            image_path: Optional path to image file.
            
        Returns:
            Response from LinkedIn API.
        """
        logger.info("Publishing started")
        
        try:
            # Check authentication
            if not self.is_authenticated():
                logger.error("Not authenticated with LinkedIn")
                return {"error": "Not authenticated"}
            
            # Ensure publisher is setup
            if not self.publisher:
                token = self.token_storage.load_token()
                if not token:
                    return {"error": "No valid token"}
                self._setup_with_token(token)
            
            # Combine title, content, and hashtags
            post_text = f"{title}\n\n{content}\n\n{' '.join(hashtags)}"
            
            # Publish with or without image
            if image_path:
                logger.info(f"Publishing with image: {image_path}")
                result = self.publisher.publish_image_post(post_text, image_path)
            else:
                logger.info("Publishing text-only post")
                result = self.publisher.publish_text_post(post_text)
            
            logger.info("Publishing completed")
            
            return result
            
        except Exception as e:
            logger.error(f"Publishing failed: {str(e)}")
            return {"error": str(e)}
