"""Approval service for managing approval workflow."""

import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, List
from approval.models import ApprovalToken, ApprovalStatus, DraftRecord, DraftVersion
from approval.store import ApprovalStore
from approval.email_service import EmailService
from approval.audit import AuditLog, AuditEventType
from services.linkedin import LinkedInService
from memory.service import MemoryService
from utils.logger import logger


class ApprovalService:
    """Service for managing approval workflow."""
    
    def __init__(self):
        """Initialize the approval service."""
        self.store = ApprovalStore()
        self.email_service = EmailService()
        self.linkedin_service = LinkedInService()
        self.memory_service = MemoryService()
        
        # Configuration
        self.approval_expiry_hours = int(os.getenv("APPROVAL_EXPIRY_HOURS", "24"))
        self.max_publish_retries = int(os.getenv("MAX_PUBLISH_RETRIES", "3"))
        self.enable_versioning = os.getenv("ENABLE_VERSIONING", "true").lower() == "true"
        self.enable_audit_log = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"
        self.auto_cleanup_expired = os.getenv("AUTO_CLEANUP_EXPIRED", "true").lower() == "true"
        self.enable_background_publish = os.getenv("ENABLE_BACKGROUND_PUBLISH", "true").lower() == "true"
        self.max_draft_versions = int(os.getenv("MAX_DRAFT_VERSIONS", "10"))
        self.audit_log_retention_days = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "30"))
        
        # Initialize audit log if enabled
        self.audit_log = AuditLog() if self.enable_audit_log else None
        
        logger.info("Approval service initialized")
    
    def create_draft(
        self,
        topic: str,
        title: str,
        content: str,
        hashtags: list,
        image_path: Optional[str] = None,
        review_score: int = 0,
        review_feedback: str = "",
        research_summary: Optional[str] = None
    ) -> str:
        """Create a draft and generate approval token.
        
        Args:
            topic: Original topic.
            title: Post title.
            content: Post content.
            hashtags: Post hashtags.
            image_path: Optional path to image.
            review_score: Review score.
            review_feedback: Reviewer feedback.
            research_summary: Optional research summary.
            
        Returns:
            Draft ID.
        """
        draft_id = str(uuid.uuid4())
        
        draft = DraftRecord(
            draft_id=draft_id,
            topic=topic,
            title=title,
            content=content,
            hashtags=hashtags,
            image_path=image_path,
            review_score=review_score,
            review_feedback=review_feedback,
            research_summary=research_summary
        )
        
        self.store.save_draft(draft)
        
        # Create approval token
        token = self.store.create_token(draft_id, self.approval_expiry_hours)
        
        # Update draft with token
        draft.approval_token = token.token
        self.store.save_draft(draft)
        
        # Log audit events
        if self.audit_log:
            self.audit_log.log_event(AuditEventType.DRAFT_CREATED, draft_id=draft_id, title=title)
            self.audit_log.log_event(AuditEventType.TOKEN_CREATED, draft_id=draft_id, token=token.token)
        
        # Send approval email
        logger.info(f"Sending approval email for draft {draft_id} to {self.email_service.email_to}")
        email_sent = self.email_service.send_approval_email(
            token=token.token,
            draft_title=title,
            draft_content=content,
            review_score=review_score,
            review_feedback=review_feedback,
            research_summary=research_summary,
            image_path=image_path,
            version=draft.current_version,
            generated_time=draft.created_at.strftime("%Y-%m-%d %H:%M")
        )
        
        if email_sent:
            if self.audit_log:
                self.audit_log.log_event(AuditEventType.EMAIL_SENT, draft_id=draft_id, token=token.token)
            logger.info(f"Approval email sent successfully for draft {draft_id}")
        else:
            logger.error(f"Approval email failed for draft {draft_id} - SMTP error or configuration issue")
            if self.audit_log:
                self.audit_log.log_event(AuditEventType.EMAIL_FAILED, draft_id=draft_id, token=token.token, reason="SMTP error or configuration issue")
        
        return draft_id
    
    def approve(self, token: str, schedule_time: Optional[datetime] = None) -> tuple[bool, str]:
        """Approve a draft (marks token as approved, publishing happens separately).
        
        Args:
            token: Approval token.
            schedule_time: Optional scheduled publish time.
            
        Returns:
            Tuple of (success, message).
        """
        # Validate token
        approval_token = self.store.get_token(token)
        if not approval_token:
            return False, "Invalid token"
        
        if not approval_token.is_valid():
            if approval_token.is_expired():
                return False, "Token has expired"
            if approval_token.used:
                return False, "Token has already been used"
            return False, "Token is not valid"
        
        # Get draft
        draft = self.store.get_draft_by_token(token)
        if not draft:
            return False, "Draft not found"
        
        # Mark token as approved
        if not self.store.approve_token(token):
            return False, "Failed to approve token"
        
        # Store scheduled time if provided
        if schedule_time:
            draft.scheduled_publish_time = schedule_time
            self.store.save_draft(draft)
            if self.audit_log:
                self.audit_log.log_event(AuditEventType.SCHEDULED, draft_id=draft.draft_id, token=token, scheduled_time=schedule_time.isoformat())
            logger.info(f"Draft {draft.draft_id} approved and scheduled for {schedule_time}")
            return True, f"Draft approved and scheduled for {schedule_time.strftime('%Y-%m-%d %H:%M')}"
        
        if self.audit_log:
            self.audit_log.log_event(AuditEventType.APPROVED, draft_id=draft.draft_id, token=token)
        logger.info(f"Draft {draft.draft_id} approved, queued for publishing")
        return True, "Draft approved successfully. Publishing in progress."
    
    def publish_draft(self, draft_id: str, retry_count: int = 0) -> tuple[bool, str]:
        """Publish a draft to LinkedIn (called asynchronously with retry logic).
        
        Args:
            draft_id: Draft identifier.
            retry_count: Current retry attempt.
            
        Returns:
            Tuple of (success, message).
        """
        # Get draft
        draft = self.store.get_draft(draft_id)
        if not draft:
            return False, "Draft not found"
        
        # Check if already published
        if draft.published_at:
            return False, "Draft already published"
        
        # Verify approval status before publishing
        approval_token = self.store.get_token_by_draft_id(draft_id)
        if not approval_token:
            error_msg = "No approval token found for draft"
            logger.error(f"Cannot publish draft {draft_id}: {error_msg}")
            draft.publish_failure_reason = error_msg
            self.store.save_draft(draft)
            if self.audit_log:
                self.audit_log.log_event(AuditEventType.PUBLISH_FAILED, draft_id=draft_id, status="error", reason=error_msg, retry_count=retry_count)
            return False, error_msg
        
        if not approval_token.is_approved():
            error_msg = f"Draft not approved. Current status: {approval_token.status.value if approval_token.status else 'Unknown'}"
            logger.error(f"Cannot publish draft {draft_id}: {error_msg}")
            draft.publish_failure_reason = error_msg
            self.store.save_draft(draft)
            if self.audit_log:
                self.audit_log.log_event(AuditEventType.PUBLISH_FAILED, draft_id=draft_id, status="error", reason=error_msg, retry_count=retry_count)
            return False, error_msg
        
        logger.info(f"Publishing draft {draft_id} with approval status: {approval_token.status.value}, token: {approval_token.token[:8]}...")
        
        # Publish to LinkedIn with retry logic
        try:
            if not self.linkedin_service.authenticate():
                error_msg = "LinkedIn authentication failed"
                draft.publish_failure_reason = error_msg
                self.store.save_draft(draft)
                if self.audit_log:
                    self.audit_log.log_event(AuditEventType.PUBLISH_FAILED, draft_id=draft_id, status="error", reason=error_msg, retry_count=retry_count)
                return False, error_msg
            
            result = self.linkedin_service.publish_post(
                draft.title,
                draft.content,
                draft.hashtags,
                draft.image_path,
                approval_status=approval_token.status.value,
                approval_token=approval_token.token
            )
            
            if "error" in result:
                error_msg = f"LinkedIn publish failed: {result['error']}"
                # Retry if under max retries
                if retry_count < self.max_publish_retries:
                    logger.warning(f"Publish failed for draft {draft_id}, retrying ({retry_count + 1}/{self.max_publish_retries})")
                    import time
                    time.sleep(2 ** retry_count)  # Exponential backoff
                    return self.publish_draft(draft_id, retry_count + 1)
                
                draft.publish_failure_reason = error_msg
                self.store.save_draft(draft)
                if self.audit_log:
                    self.audit_log.log_event(AuditEventType.PUBLISH_FAILED, draft_id=draft_id, status="error", reason=error_msg, retry_count=retry_count)
                return False, error_msg
            
            linkedin_post_id = result.get("id", "unknown")
            
            # Verify LinkedIn returned success
            if not linkedin_post_id or linkedin_post_id == "unknown":
                error_msg = "LinkedIn did not return a valid post ID"
                draft.publish_failure_reason = error_msg
                self.store.save_draft(draft)
                if self.audit_log:
                    self.audit_log.log_event(AuditEventType.PUBLISH_FAILED, draft_id=draft_id, status="error", reason=error_msg, retry_count=retry_count)
                return False, error_msg
            
            # Mark draft as published
            self.store.mark_draft_published(draft_id, linkedin_post_id)
            
            # Index into memory (only after successful publish)
            self._index_to_memory(draft)
            
            if self.audit_log:
                self.audit_log.log_event(AuditEventType.PUBLISHED, draft_id=draft_id, linkedin_post_id=linkedin_post_id)
                self.audit_log.log_event(AuditEventType.MEMORY_INDEXED, draft_id=draft_id)
            logger.info(f"Draft {draft_id} published to LinkedIn (ID: {linkedin_post_id}) and indexed to memory")
            return True, f"Post published successfully! LinkedIn Post ID: {linkedin_post_id}"
            
        except Exception as e:
            error_msg = f"Publish failed: {str(e)}"
            draft.publish_failure_reason = error_msg
            self.store.save_draft(draft)
            if self.audit_log:
                self.audit_log.log_event(AuditEventType.PUBLISH_FAILED, draft_id=draft_id, status="error", reason=error_msg, retry_count=retry_count)
            logger.error(f"Failed to publish draft {draft_id}: {e}")
            return False, error_msg
    
    def reject(self, token: str) -> tuple[bool, str]:
        """Reject a draft.
        
        Args:
            token: Approval token.
            
        Returns:
            Tuple of (success, message).
        """
        # Validate token
        approval_token = self.store.get_token(token)
        if not approval_token:
            return False, "Invalid token"
        
        if not approval_token.is_valid():
            if approval_token.is_expired():
                return False, "Token has expired"
            if approval_token.used:
                return False, "Token has already been used"
            return False, "Token is not valid"
        
        # Mark token as rejected
        if not self.store.reject_token(token):
            return False, "Failed to reject token"
        
        if self.audit_log:
            self.audit_log.log_event(AuditEventType.REJECTED, draft_id=draft.draft_id, token=token)
        logger.info(f"Draft rejected via token {token[:8]}...")
        return True, "Draft rejected successfully"
    
    def get_draft(self, token: str) -> Optional[DraftRecord]:
        """Get a draft by approval token.
        
        Args:
            token: Approval token.
            
        Returns:
            DraftRecord or None if not found.
        """
        return self.store.get_draft_by_token(token)
    
    def edit_draft(self, draft_id: str, title: str, content: str, hashtags: List[str], edited_by: str = "owner") -> tuple[bool, str]:
        """Edit a draft and create a new version.
        
        Args:
            draft_id: Draft identifier.
            title: New title.
            content: New content.
            hashtags: New hashtags.
            edited_by: Who made the edit.
            
        Returns:
            Tuple of (success, message).
        """
        draft = self.store.get_draft(draft_id)
        if not draft:
            return False, "Draft not found"
        
        # Check if already published
        if draft.published_at:
            return False, "Cannot edit published draft"
        
        # Add new version
        draft.add_version(title, content, hashtags, edited_by)
        
        # Save updated draft
        self.store.save_draft(draft)
        
        if self.audit_log:
            self.audit_log.log_event(AuditEventType.DRAFT_EDITED, draft_id=draft_id, version=draft.current_version, edited_by=edited_by)
        logger.info(f"Draft {draft_id} edited to version {draft.current_version} by {edited_by}")
        return True, f"Draft updated to version {draft.current_version}"
    
    def get_draft_version(self, draft_id: str, version_number: int) -> Optional[DraftVersion]:
        """Get a specific version of a draft.
        
        Args:
            draft_id: Draft identifier.
            version_number: Version number.
            
        Returns:
            DraftVersion or None if not found.
        """
        draft = self.store.get_draft(draft_id)
        if not draft:
            return None
        
        for version in draft.versions:
            if version.version_number == version_number:
                return version
        
        return None
    
    def _index_to_memory(self, draft: DraftRecord) -> None:
        """Index a published draft into memory.
        
        Args:
            draft: DraftRecord to index.
        """
        try:
            self.memory_service.index_post(
                topic=draft.topic,
                title=draft.title,
                content=draft.content,
                hashtags=draft.hashtags,
                writing_style="professional"
            )
            logger.info(f"Indexed draft {draft.draft_id} into memory")
        except Exception as e:
            logger.error(f"Failed to index draft {draft.draft_id} into memory: {e}")
