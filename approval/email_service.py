"""Email service for sending approval requests."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from dotenv import load_dotenv
from utils.logger import logger

load_dotenv()


class EmailService:
    """Service for sending approval emails via SMTP."""
    
    def __init__(self):
        """Initialize the email service from environment variables."""
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.email_from = os.getenv("EMAIL_FROM")
        self.email_to = os.getenv("EMAIL_TO")
        self.server_url = os.getenv("SERVER_URL", "http://localhost:8000")
        
        if not all([self.smtp_host, self.smtp_username, self.smtp_password, self.email_from, self.email_to]):
            logger.warning("Email service not fully configured. Some environment variables missing.")
    
    def send_approval_email(
        self,
        token: str,
        draft_title: str,
        draft_content: str,
        review_score: int,
        review_feedback: str,
        research_summary: Optional[str] = None,
        image_path: Optional[str] = None,
        version: int = 1,
        generated_time: Optional[str] = None
    ) -> bool:
        """Send an approval email to the owner.
        
        Args:
            token: Approval token.
            draft_title: Post title.
            draft_content: Post content.
            review_score: Review score.
            review_feedback: Reviewer feedback.
            research_summary: Optional research summary.
            image_path: Optional path to generated image.
            version: Draft version number.
            generated_time: When the draft was generated.
            
        Returns:
            True if email sent successfully, False otherwise.
        """
        if not self._is_configured():
            logger.error("Email service not configured. Cannot send approval email.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = "LinkedIn Post Ready For Approval"
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            
            # Create HTML content
            html_content = self._create_html_email(
                token=token,
                draft_title=draft_title,
                draft_content=draft_content,
                review_score=review_score,
                review_feedback=review_feedback,
                research_summary=research_summary,
                image_path=image_path,
                version=version,
                generated_time=generated_time
            )
            
            # Attach HTML
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            logger.info(f"Connecting to SMTP server: {self.smtp_host}:{self.smtp_port}")
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                logger.info("Starting TLS encryption")
                server.starttls()
                logger.info(f"Authenticating as {self.smtp_username}")
                server.login(self.smtp_username, self.smtp_password)
                logger.info(f"Sending email to {self.email_to}")
                server.send_message(msg)
            
            logger.info(f"Approval email sent successfully for token {token[:8]}...")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            logger.error(f"Check SMTP_USERNAME and SMTP_PASSWORD in .env")
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP connection failed: {e}")
            logger.error(f"Check SMTP_HOST and SMTP_PORT in .env")
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
        except Exception as e:
            logger.error(f"Failed to send approval email: {e}")
        return False
    
    def _is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return all([
            self.smtp_host,
            self.smtp_username,
            self.smtp_password,
            self.email_from,
            self.email_to
        ])
    
    def _create_html_email(
        self,
        token: str,
        draft_title: str,
        draft_content: str,
        review_score: int,
        review_feedback: str,
        research_summary: Optional[str] = None,
        image_path: Optional[str] = None,
        version: int = 1,
        generated_time: Optional[str] = None
    ) -> str:
        """Create HTML email content.
        
        Args:
            token: Approval token.
            draft_title: Post title.
            draft_content: Post content.
            review_score: Review score.
            review_feedback: Reviewer feedback.
            research_summary: Optional research summary.
            image_path: Optional path to generated image.
            version: Draft version number.
            generated_time: When the draft was generated.
            
        Returns:
            HTML string.
        """
        approve_url = f"{self.server_url}/approve/{token}"
        reject_url = f"{self.server_url}/reject/{token}"
        view_url = f"{self.server_url}/draft/{token}"
        
        # Truncate content for preview (400 chars)
        content_preview = draft_content[:400] + "..." if len(draft_content) > 400 else draft_content
        
        # Calculate estimated read time (200 words per minute)
        word_count = len(draft_content.split())
        read_time = max(1, round(word_count / 200))
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 20px; background-color: #f9f9f9;">
            <table role="presentation" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <!-- Header -->
                <tr>
                    <td style="background-color: #0077b5; color: #ffffff; padding: 30px; text-align: center;">
                        <h1 style="margin: 0; font-size: 24px; color: #ffffff;">LinkedIn Post Ready For Approval</h1>
                        <p style="margin: 10px 0 0 0; font-size: 12px; color: rgba(255,255,255,0.8);">Version {version} | {generated_time if generated_time else 'Just now'}</p>
                    </td>
                </tr>
                
                <!-- Post Title -->
                <tr>
                    <td style="padding: 20px 30px;">
                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f5f5f5; border-left: 4px solid #0077b5; border-radius: 5px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <h2 style="margin: 0 0 10px 0; color: #0077b5; font-size: 18px;">📝 Post Title</h2>
                                    <p style="margin: 0;">{draft_title}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                
                <!-- Review Score -->
                <tr>
                    <td style="padding: 0 30px 20px 30px;">
                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f5f5f5; border-left: 4px solid #0077b5; border-radius: 5px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <h2 style="margin: 0 0 10px 0; color: #0077b5; font-size: 18px;">⭐ Review Score</h2>
                                    <p style="margin: 0; font-size: 24px; font-weight: bold; color: {self._get_score_color(review_score)};">{review_score}/10</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                
                <!-- Reviewer Feedback -->
                <tr>
                    <td style="padding: 0 30px 20px 30px;">
                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f5f5f5; border-left: 4px solid #0077b5; border-radius: 5px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <h2 style="margin: 0 0 10px 0; color: #0077b5; font-size: 18px;">💬 Reviewer Feedback</h2>
                                    <p style="margin: 0;">{review_feedback}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                
                {f'''<tr>
                    <td style="padding: 0 30px 20px 30px;">
                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f5f5f5; border-left: 4px solid #0077b5; border-radius: 5px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <h2 style="margin: 0 0 10px 0; color: #0077b5; font-size: 18px;">🔍 Research Summary</h2>
                                    <p style="margin: 0;">{research_summary}</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>''' if research_summary else ''}
                
                <!-- Content Preview -->
                <tr>
                    <td style="padding: 0 30px 20px 30px;">
                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f5f5f5; border-left: 4px solid #0077b5; border-radius: 5px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <h2 style="margin: 0 0 10px 0; color: #0077b5; font-size: 18px;">📄 Content Preview</h2>
                                    <p style="margin: 0; font-style: italic; color: #666; padding: 10px; background-color: #ffffff; border-radius: 4px;">{content_preview}</p>
                                    <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">📖 Estimated read time: {read_time} min ({word_count} words)</p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                
                {f'''<tr>
                    <td style="padding: 0 30px 20px 30px;">
                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%; background-color: #f5f5f5; border-left: 4px solid #0077b5; border-radius: 5px;">
                            <tr>
                                <td style="padding: 15px;">
                                    <h2 style="margin: 0 0 10px 0; color: #0077b5; font-size: 18px;">🖼️ Image Preview</h2>
                                    <img src="{image_path}" alt="Generated image" style="max-width: 100%; height: auto; border-radius: 4px; display: block;">
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>''' if image_path else ''}
                
                <!-- Buttons -->
                <tr>
                    <td style="padding: 30px; text-align: center;">
                        <table role="presentation" cellpadding="0" cellspacing="0" style="width: 100%;">
                            <tr>
                                <td style="padding: 10px 0; text-align: center;">
                                    <a href="{approve_url}" style="display: inline-block; padding: 12px 30px; background-color: #28a745; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">✅ Approve</a>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; text-align: center;">
                                    <a href="{reject_url}" style="display: inline-block; padding: 12px 30px; background-color: #dc3545; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">❌ Reject</a>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; text-align: center;">
                                    <a href="{view_url}" style="display: inline-block; padding: 12px 30px; background-color: #6c757d; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">👁️ View Full Draft</a>
                                </td>
                            </tr>
                            <tr>
                                <td style="padding: 10px 0; text-align: center;">
                                    <a href="{view_url}" style="display: inline-block; padding: 12px 30px; background-color: #17a2b8; color: #ffffff; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">✏️ Edit Draft</a>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
                
                <!-- Footer -->
                <tr>
                    <td style="padding: 20px 30px; background-color: #f9f9f9; text-align: center; border-top: 1px solid #e0e0e0;">
                        <p style="margin: 0 0 10px 0; font-size: 12px; color: #999;">This approval link will expire in 24 hours.</p>
                        <p style="margin: 0; font-size: 12px; color: #999;">If you did not request this email, please ignore it.</p>
                    </td>
                </tr>
            </table>
        </body>
        </html>
        """
        
        return html
    
    def _get_score_color(self, score: int) -> str:
        """Get color based on score.
        
        Args:
            score: Review score.
            
        Returns:
            CSS color code.
        """
        if score >= 8:
            return "#28a745"  # Green
        elif score >= 6:
            return "#ffc107"  # Yellow
        else:
            return "#dc3545"  # Red
