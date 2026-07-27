"""
LinkedIn OAuth Authentication Module

Handles LinkedIn OAuth 2.0 / OpenID Connect authentication.
"""

import os
from typing import Optional, Dict
from requests_oauthlib import OAuth2Session
from utils.logger import logger

# Required for localhost development
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# LinkedIn may return scopes in a different order
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"


class LinkedInAuth:
    AUTHORIZATION_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        # Request publishing permission + profile scopes
        # w_member_social: Required to create LinkedIn posts on behalf of authenticated member
        # r_liteprofile: Required to retrieve member profile (name, photo) for person ID
        # openid, profile, email: OpenID Connect scopes for authentication
        self.scope = [
            "w_member_social",
            "openid",
            "profile",
            "email"
        ]

        self.session: Optional[OAuth2Session] = None
        self.token: Optional[Dict] = None

    def get_authorization_url(self):
        """Generate LinkedIn authorization URL."""

        self.session = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=self.redirect_uri,
            scope=self.scope,
        )

        authorization_url, state = self.session.authorization_url(
            self.AUTHORIZATION_URL
        )

        return authorization_url

    def fetch_token(self, authorization_response: str):
        """Exchange authorization code for an access token."""

        if self.session is None:
            raise RuntimeError(
                "OAuth session not initialized. Call get_authorization_url() first."
            )

        token = self.session.fetch_token(
            token_url=self.TOKEN_URL,
            authorization_response=authorization_response,
            client_id=self.client_id,
            client_secret=self.client_secret,
            include_client_id=True,
        )

        self.token = token
        return token

    def get_authenticated_session(self, token: Optional[Dict] = None):
        """Return an authenticated OAuth session."""

        if token is None:
            token = self.token

        if token is None:
            raise RuntimeError("No OAuth token available.")

        return OAuth2Session(
            client_id=self.client_id,
            token=token,
        )

    def get_member_urn(self, session: OAuth2Session) -> str:
        """Retrieve the authenticated member's URN using OpenID Connect userinfo.
        
        Uses the /v2/userinfo endpoint which is supported with openid, profile, email scopes.
        The 'sub' field from userinfo is the correct identifier for constructing Person URN.
        
        Args:
            session: Authenticated OAuth2Session
            
        Returns:
            Person URN in format: urn:li:person:{sub}
            
        Raises:
            Exception: If unable to retrieve member identifier
        """
        url = "https://api.linkedin.com/v2/userinfo"
        
        headers = {
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        logger.info(f"Fetching member profile from: {url}")
        logger.info(f"Request headers: {headers}")
        
        try:
            response = session.get(url, headers=headers)
            
            logger.info(f"Userinfo Response Status: {response.status_code}")
            logger.info(f"Userinfo Response Body: {response.text}")
            
            response.raise_for_status()
            
            data = response.json()
            
            # The 'sub' field contains the person identifier (OpenID subject)
            person_sub = data.get("sub")
            
            if not person_sub:
                raise Exception("Could not find 'sub' in userinfo response.")
            
            # Construct the proper Person URN
            person_urn = f"urn:li:person:{person_sub}"
            
            logger.info(f"Successfully retrieved member URN: {person_urn}")
            
            return person_urn
            
        except Exception as e:
            logger.error(f"Failed to retrieve member URN: {str(e)}")
            raise Exception(f"Failed to retrieve member URN: {str(e)}")
