"""End-to-End Integration Test.

Validates the complete pipeline from topic to publish.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrationTest:
    """End-to-end integration test for the LinkedIn Agent pipeline."""
    
    def __init__(self):
        """Initialize the integration test."""
        self.results: Dict[str, Dict[str, Any]] = {}
        self.test_topic = "Four Pillars of Object Oriented Programming in Python"
    
    def record_result(self, stage: str, success: bool, reason: str, logs: str = "", files: list = None):
        """Record a test result.
        
        Args:
            stage: Stage name.
            success: Whether the stage passed.
            reason: Reason for success/failure.
            logs: Relevant log output.
            files: Files involved in the stage.
        """
        self.results[stage] = {
            "success": success,
            "reason": reason,
            "logs": logs,
            "files": files or []
        }
        
        status = "✅" if success else "❌"
        logger.info(f"{status} {stage}: {reason}")
    
    def test_research(self) -> bool:
        """Test the Research stage."""
        logger.info("Testing Research stage...")
        try:
            from services.research import ResearchService
            
            research_service = ResearchService()
            research_package = research_service.research(self.test_topic)
            
            if research_package and research_package.raw_results:
                self.record_result(
                    "Research",
                    True,
                    f"Research completed with {len(research_package.raw_results)} results",
                    "",
                    []
                )
                return True
            else:
                self.record_result(
                    "Research",
                    False,
                    "Research returned no results",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Research",
                False,
                f"Research failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_planner(self) -> bool:
        """Test the Planner stage."""
        logger.info("Testing Planner stage...")
        try:
            from agents.planner import PlannerAgent
            from models.context_models import Context
            
            planner = PlannerAgent()
            context = Context()
            execution_plan = planner.plan(self.test_topic, context)
            
            if execution_plan and execution_plan.topic:
                self.record_result(
                    "Planner",
                    True,
                    f"Plan created: {execution_plan.topic}",
                    f"Angle: {execution_plan.angle}",
                    []
                )
                return True
            else:
                self.record_result(
                    "Planner",
                    False,
                    "Planner returned no execution plan",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Planner",
                False,
                f"Planner failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_writer(self) -> bool:
        """Test the Writer stage."""
        logger.info("Testing Writer stage...")
        try:
            from agents.writer import WriterAgent
            from agents.planner import PlannerAgent
            from models.context_models import Context
            
            planner = PlannerAgent()
            context = Context()
            execution_plan = planner.plan(self.test_topic, context)
            
            writer = WriterAgent()
            post = asyncio.run(writer.write(
                topic=execution_plan.topic,
                intent=execution_plan.intent,
                user_prompt=self.test_topic,
                research=None,
                writing_style=execution_plan.writing_style,
                context=context,
                execution_plan=execution_plan
            ))
            if post and post.content:
                self.record_result(
                    "Writer",
                    True,
                    f"Post generated: {len(post.content)} characters",
                    f"Title: {post.title}",
                    []
                )
                return True
            else:
                self.record_result(
                    "Writer",
                    False,
                    "Writer returned no post content",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Writer",
                False,
                f"Writer failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_reviewer(self) -> bool:
        """Test the Reviewer stage."""
        logger.info("Testing Reviewer stage...")
        try:
            from agents.writer import WriterAgent
            from agents.planner import PlannerAgent
            from agents.reviewer import ReviewerAgent
            from models.context_models import Context
            
            planner = PlannerAgent()
            context = Context()
            execution_plan = planner.plan(self.test_topic, context)
            
            writer = WriterAgent()
            post = asyncio.run(writer.write(
                topic=execution_plan.topic,
                intent=execution_plan.intent,
                user_prompt=self.test_topic,
                research=None,
                writing_style=execution_plan.writing_style,
                context=context,
                execution_plan=execution_plan
            ))
            reviewer = ReviewerAgent()
            review = asyncio.run(reviewer.review(post, context))
            if review and review.scores:
                self.record_result(
                    "Reviewer",
                    True,
                    f"Review completed: {review.scores.overall}/10",
                    f"Decision: {review.decision.decision if review.decision else 'N/A'}",
                    []
                )
                return True
            else:
                self.record_result(
                    "Reviewer",
                    False,
                    "Reviewer returned no scores",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Reviewer",
                False,
                f"Reviewer failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_image_prompt(self) -> bool:
        """Test the Image Prompt generation stage."""
        logger.info("Testing Image Prompt generation...")
        try:
            from agents.writer import WriterAgent
            from agents.planner import PlannerAgent
            from agents.image_prompt import ImagePromptAgent
            from models.context_models import Context
            
            planner = PlannerAgent()
            context = Context()
            execution_plan = planner.plan(self.test_topic, context)
            
            writer = WriterAgent()
            post = asyncio.run(writer.write(
                topic=execution_plan.topic,
                intent=execution_plan.intent,
                user_prompt=self.test_topic,
                research=None,
                writing_style=execution_plan.writing_style,
                context=context,
                execution_plan=execution_plan

            ))

            image_prompt_agent = ImagePromptAgent()
            image_prompt = asyncio.run(image_prompt_agent.generate(post))
            
            if image_prompt and image_prompt.prompt:
                self.record_result(
                    "Image Prompt",
                    True,
                    f"Image prompt generated: {len(image_prompt.prompt)} characters",
                    f"Style: {image_prompt.style}",
                    []
                )
                return True
            else:
                self.record_result(
                    "Image Prompt",
                    False,
                    "Image prompt generation returned no prompt",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Image Prompt",
                False,
                f"Image prompt generation failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_image_generation(self) -> bool:
        """Test the Image Generation stage."""
        logger.info("Testing Image Generation...")
        try:
            from agents.writer import WriterAgent
            from agents.planner import PlannerAgent
            from agents.image_prompt import ImagePromptAgent
            from services.image import ImageService
            from models.context_models import Context
            from config.config import config
            
            planner = PlannerAgent()
            context = Context()
            execution_plan = planner.plan(self.test_topic, context)
            
            writer = WriterAgent()
            post = asyncio.run(writer.write(
                topic=execution_plan.topic,
                intent=execution_plan.intent,
                user_prompt=self.test_topic,
                research=None,
                writing_style=execution_plan.writing_style,
                context=context,
                execution_plan=execution_plan

            ))

            image_prompt_agent = ImagePromptAgent()
            image_prompt = asyncio.run(image_prompt_agent.generate(post))
            
            image_service = ImageService()
            image_path = image_service.generate_image(
                prompt=image_prompt.prompt,
                filename=image_prompt.filename,
                width=1200,
                height=675,
                validate=True
            )
            
            if image_path and image_path.exists():
                file_size = image_path.stat().st_size
                self.record_result(
                    "Image Generation",
                    True,
                    f"Image generated: {image_path} ({file_size} bytes)",
                    f"File exists: {image_path.exists()}",
                    [str(image_path)]
                )
                return True
            else:
                self.record_result(
                    "Image Generation",
                    False,
                    "Image generation returned no file or file doesn't exist",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Image Generation",
                False,
                f"Image generation failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_image_validation(self) -> bool:
        """Test the Image Validation stage."""
        logger.info("Testing Image Validation...")
        try:
            from utils.image_validator import ImageValidator
            from config.config import config
            
            # Check if there's a test image
            test_image = config.images_dir / "test_validation.png"
            
            if not test_image.exists():
                # Try to generate a test image first
                from services.image import ImageService
                image_service = ImageService()
                test_image = image_service.generate_image(
                    prompt="A simple test image for validation",
                    filename="test_validation.png",
                    width=1024,
                    height=1024,
                    validate=False
                )
            
            if test_image and test_image.exists():
                validator = ImageValidator()
                is_valid, message = validator.validate(test_image)
                
                self.record_result(
                    "Image Validation",
                    is_valid,
                    message,
                    "",
                    [str(test_image)]
                )
                return is_valid
            else:
                self.record_result(
                    "Image Validation",
                    False,
                    "No test image available for validation",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Image Validation",
                False,
                f"Image validation failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_approval_request(self) -> bool:
        """Test the Approval Request creation stage."""
        logger.info("Testing Approval Request creation...")
        try:
            from approval.service import ApprovalService
            from agents.writer import WriterAgent
            from agents.planner import PlannerAgent
            from models.context_models import Context
            
            planner = PlannerAgent()
            context = Context()
            execution_plan = planner.plan(self.test_topic, context)
            
            writer = WriterAgent()
            post = asyncio.run(writer.write(
                topic=execution_plan.topic,
                intent=execution_plan.intent,
                user_prompt=self.test_topic,
                research=None,
                writing_style=execution_plan.writing_style,
                context=context,
                execution_plan=execution_plan

            ))

            approval_service = ApprovalService()
            draft_id = approval_service.create_draft(
                topic=self.test_topic,
                title=post.title,
                content=post.content,
                hashtags=post.hashtags,
                image_path=None,
                review_score=8,
                review_feedback="Good post",
                research_summary=None
            )
            
            if draft_id:
                # Verify draft was saved
                draft = approval_service.store.get_draft(draft_id)
                if draft:
                    self.record_result(
                        "Approval Request",
                        True,
                        f"Draft created with ID: {draft_id}",
                        f"Title: {draft.title}",
                        []
                    )
                    return True
            
            self.record_result(
                "Approval Request",
                False,
                "Draft creation failed or draft not found",
                "",
                []
            )
            return False
                
        except Exception as e:
            self.record_result(
                "Approval Request",
                False,
                f"Approval request creation failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def test_approval_email(self) -> bool:
        """Test the Approval Email sending stage."""
        logger.info("Testing Approval Email sending...")
        try:
            from approval.service import ApprovalService
            from approval.email_service import EmailService
            from config.config import config
            import os
            
            # Check if SMTP is configured
            if not all([config.smtp_host, config.smtp_username, config.smtp_password]):
                self.record_result(
                    "Approval Email",
                    False,
                    "SMTP not configured (missing credentials in .env)",
                    "Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD in .env",
                    []
                )
                return False
            
            email_service = EmailService()
            if not email_service._is_configured():
                self.record_result(
                    "Approval Email",
                    False,
                    "Email service not configured",
                    "",
                    []
                )
                return False
            
            # Try to send a test email
            test_sent = email_service.send_approval_email(
                token="test_token_123",
                draft_title="Test Draft",
                draft_content="Test content for email validation",
                review_score=8,
                review_feedback="Test feedback",
                research_summary=None,
                image_path=None,
                version=1,
                generated_time="2026-07-28"
            )
            
            if test_sent:
                self.record_result(
                    "Approval Email",
                    True,
                    "Test email sent successfully",
                    "SMTP logs should show successful delivery",
                    []
                )
                return True
            else:
                self.record_result(
                    "Approval Email",
                    False,
                    "Email sending failed (check SMTP credentials)",
                    "",
                    []
                )
                return False
                
        except Exception as e:
            self.record_result(
                "Approval Email",
                False,
                f"Email sending failed: {str(e)}",
                str(e),
                []
            )
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all integration tests.
        
        Returns:
            Dictionary of all test results.
        """
        logger.info("="*60)
        logger.info("Starting End-to-End Integration Test")
        logger.info("="*60)
        
        # Run tests in order
        self.test_research()
        self.test_planner()
        self.test_writer()
        self.test_reviewer()
        self.test_image_prompt()
        self.test_image_generation()
        self.test_image_validation()
        self.test_approval_request()
        self.test_approval_email()
        
        # Calculate summary
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r["success"])
        failed = total - passed
        
        logger.info("="*60)
        logger.info(f"Integration Test Complete: {passed}/{total} passed")
        logger.info("="*60)
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "results": self.results
        }
    
    def generate_report(self) -> str:
        """Generate a human-readable report.
        
        Returns:
            Formatted report string.
        """
        lines = []
        lines.append("# End-to-End Integration Test Report")
        lines.append("")
        
        total = len(self.results)
        passed = sum(1 for r in self.results.values() if r["success"])
        failed = total - passed
        
        lines.append(f"## Summary")
        lines.append(f"- Total Tests: {total}")
        lines.append(f"- Passed: {passed}")
        lines.append(f"- Failed: {failed}")
        lines.append(f"- Success Rate: {passed/total*100:.1f}%")
        lines.append("")
        
        lines.append("## Detailed Results")
        lines.append("")
        
        for stage, result in self.results.items():
            status = "✅" if result["success"] else "❌"
            lines.append(f"### {status} {stage}")
            lines.append(f"**Reason:** {result['reason']}")
            if result["logs"]:
                lines.append(f"**Logs:** {result['logs']}")
            if result["files"]:
                lines.append(f"**Files:** {', '.join(result['files'])}")
            lines.append("")
        
        return "\n".join(lines)


if __name__ == "__main__":
    test = IntegrationTest()
    results = test.run_all_tests()
    report = test.generate_report()
    
    print(report)
    
    # Exit with error code if any tests failed
    sys.exit(0 if results["failed"] == 0 else 1)
