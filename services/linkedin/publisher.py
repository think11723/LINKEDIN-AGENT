"""
LinkedIn Publisher Module

Handles publishing posts to LinkedIn API.
"""

import requests
from typing import Dict, Optional
from requests_oauthlib import OAuth2Session
from utils.logger import logger


class ApprovalRequiredError(Exception):
    """Exception raised when attempting to publish without approval."""
    pass


class LinkedInPublisher:
    """Handles publishing content to LinkedIn."""

    API_BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, session: OAuth2Session, person_urn: Optional[str] = None, require_approval: bool = True):
        self.session = session
        self.person_urn = person_urn
        self.require_approval = require_approval

    def _verify_approval(self, approval_status: Optional[str] = None, approval_token: Optional[str] = None) -> None:
        """Verify that the post has been approved before publishing.
        
        Args:
            approval_status: The approval status (must be "APPROVED")
            approval_token: The approval token (must exist)
            
        Raises:
            ApprovalRequiredError: If approval is required but not granted
        """
        if not self.require_approval:
            return
            
        if approval_status != "APPROVED":
            raise ApprovalRequiredError(
                f"Cannot publish: Post not approved. Current status: {approval_status or 'None'}. "
                "Please approve the draft via the approval email before publishing."
            )
        
        if not approval_token:
            raise ApprovalRequiredError(
                "Cannot publish: No approval token found. "
                "Please approve the draft via the approval email before publishing."
            )
        
        logger.info(f"Approval verified: status={approval_status}, token={approval_token[:8]}...")

    def get_profile_urn(self) -> str:
        """
        DEPRECATED: This method is no longer used.
        Use auth.get_member_urn() instead.
        
        The OpenID userinfo endpoint's 'sub' field is NOT a valid LinkedIn member URN.
        The correct method is to use the Profile API (/v2/me) via auth.get_member_urn().
        """
        raise DeprecationWarning(
            "get_profile_urn() is deprecated. Use auth.get_member_urn() instead. "
            "The OpenID 'sub' field is not a valid LinkedIn member URN for publishing."
        )

    def publish_text_post(self, text: str, approval_status: Optional[str] = None, approval_token: Optional[str] = None) -> Dict:
        """
        Publish a text-only post to LinkedIn.
        
        Args:
            text: The text content of the post
            approval_status: The approval status (must be "APPROVED" if require_approval=True)
            approval_token: The approval token (must exist if require_approval=True)
            
        Returns:
            Response data from LinkedIn API
            
        Raises:
            ValueError: If person_urn is not set
            ApprovalRequiredError: If approval is required but not granted
            Exception: If API request fails
        """
        # Verify approval before publishing
        self._verify_approval(approval_status, approval_token)
        
        if not self.person_urn:
            raise ValueError(
                "person_urn is required. Use auth.get_member_urn() to retrieve it before publishing."
            )

        share_url = f"{self.API_BASE_URL}/ugcPosts"

        headers = {
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        logger.info(f"Publishing text post to: {share_url}")
        logger.info(f"Request headers: {headers}")
        logger.info(f"Request payload: {payload}")

        try:
            response = self.session.post(
                share_url,
                json=payload,
                headers=headers
            )

            logger.info(f"Response Status Code: {response.status_code}")
            logger.info(f"Response Body: {response.text}")

            response.raise_for_status()

            if response.text:
                try:
                    return response.json()
                except Exception:
                    return {"response": response.text}

            return {}

        except Exception as e:
            logger.error(f"Failed to publish text post: {str(e)}")
            logger.error(f"Request URL: {share_url}")
            logger.error(f"Request Headers: {headers}")
            logger.error(f"Request Payload: {payload}")
            raise Exception(f"Failed to publish text post: {str(e)}")

    def upload_image(self, image_path: str) -> str:
        """
        Register and upload an image to LinkedIn.
        
        Args:
            image_path: Local path to the image file
            
        Returns:
            Asset URN of the uploaded image
            
        Raises:
            ValueError: If person_urn is not set
            Exception: If upload fails
        """
        if not self.person_urn:
            raise ValueError(
                "person_urn is required. Use auth.get_member_urn() to retrieve it before uploading."
            )

        register_url = f"{self.API_BASE_URL}/assets?action=registerUpload"

        headers = {
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        register_payload = {
            "registerUploadRequest": {
                "owner": self.person_urn,
                "recipes": [
                    "urn:li:digitalmediaAsset:jpeg"
                ],
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ],
                "supportedUploadMechanism": [
                    "BINARY_UPLOAD"
                ]
            }
        }

        logger.info(f"Registering image upload at: {register_url}")
        logger.info(f"Request headers: {headers}")
        logger.info(f"Request payload: {register_payload}")

        try:
            response = self.session.post(
                register_url,
                json=register_payload,
                headers=headers
            )

            logger.info(f"Register Response Status: {response.status_code}")
            logger.info(f"Register Response Body: {response.text}")

            response.raise_for_status()

            register_data = response.json()

            value = register_data["value"]

            upload_url = value["uploadMechanism"][
                "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
            ]["uploadUrl"]

            asset_urn = value["asset"]

            logger.info(f"Upload URL: {upload_url}")
            logger.info(f"Asset URN: {asset_urn}")

            # Read and upload the image
            with open(image_path, "rb") as f:
                image_data = f.read()

            logger.info(f"Uploading image from: {image_path}")

            upload_response = requests.put(
                upload_url,
                data=image_data,
                headers={
                    "Content-Type": "application/octet-stream"
                }
            )

            logger.info(f"Upload Response Status: {upload_response.status_code}")
            logger.info(f"Upload Response Body: {upload_response.text}")

            upload_response.raise_for_status()

            logger.info(f"Image uploaded successfully. Asset URN: {asset_urn}")

            return asset_urn

        except Exception as e:
            logger.error(f"Failed to upload image: {str(e)}")
            logger.error(f"Register URL: {register_url}")
            logger.error(f"Request Headers: {headers}")
            logger.error(f"Request Payload: {register_payload}")
            raise Exception(f"Failed to upload image: {str(e)}")

    def publish_image_post(self, text: str, image_path: str, approval_status: Optional[str] = None, approval_token: Optional[str] = None) -> Dict:
        """
        Publish an image post to LinkedIn.
        
        Args:
            text: The text content of the post
            image_path: Local path to the image file
            approval_status: The approval status (must be "APPROVED" if require_approval=True)
            approval_token: The approval token (must exist if require_approval=True)
            
        Returns:
            Response data from LinkedIn API
            
        Raises:
            ApprovalRequiredError: If approval is required but not granted
            Exception: If upload or publishing fails
        """
        # Verify approval before publishing
        self._verify_approval(approval_status, approval_token)
        
        asset_urn = self.upload_image(image_path)

        share_url = f"{self.API_BASE_URL}/ugcPosts"

        headers = {
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }

        payload = {
            "author": self.person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "media": asset_urn,
                            "description": {
                                "text": text
                            },
                            "title": {
                                "text": "Image"
                            }
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        logger.info(f"Publishing image post to: {share_url}")
        logger.info(f"Request headers: {headers}")
        logger.info(f"Request payload: {payload}")

        try:
            response = self.session.post(
                share_url,
                json=payload,
                headers=headers
            )

            logger.info(f"Response Status Code: {response.status_code}")
            logger.info(f"Response Body: {response.text}")

            response.raise_for_status()

            if response.text:
                try:
                    return response.json()
                except Exception:
                    return {"response": response.text}

            return {}

        except Exception as e:
            logger.error(f"Failed to publish image post: {str(e)}")
            logger.error(f"Request URL: {share_url}")
            logger.error(f"Request Headers: {headers}")
            logger.error(f"Request Payload: {payload}")
            raise Exception(f"Failed to publish image post: {str(e)}")
