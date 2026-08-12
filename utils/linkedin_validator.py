"""LinkedIn Post Formatting Validator.

Validates LinkedIn posts against formatting rules to ensure
they are properly formatted for the LinkedIn platform.
"""

import re
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of LinkedIn post validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def add_error(self, error: str) -> None:
        """Add an error to the validation result."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(warning)


class LinkedInValidator:
    """Validator for LinkedIn post formatting."""
    
    # Markdown patterns to detect
    MARKDOWN_PATTERNS = [
        (r'#{1,6}\s', 'Markdown heading (#)'),
        (r'\*\*[^*]+\*\*', 'Markdown bold (**text**)'),
        (r'\*[^*]+\*', 'Markdown italic (*text*)'),
        (r'```[^`]*```', 'Markdown code fence (```code```)'),
        (r'`[^`]+`', 'Markdown inline code (`code`)'),
        (r'___+', 'Markdown horizontal rule (___)'),
        (r'\*\*\*+', 'Markdown horizontal rule (***)'),
        (r'\|.*\|', 'Markdown table'),
    ]
    
    # Patterns that indicate good formatting
    GOOD_PATTERNS = [
        (r'•\s', 'Bullet point'),
        (r'^\d+\.\s', 'Numbered list'),
        (r'\n\n', 'Paragraph breaks'),
    ]
    
    def __init__(self):
        """Initialize the LinkedIn validator."""
        self.min_hashtags = 5
        self.max_hashtags = 8
        self.min_words = 150
        self.max_words = 350
        self.max_paragraph_lines = 3
        self.max_sentence_words = 25
    
    def validate(self, title: str, content: str, hashtags: List[str]) -> ValidationResult:
        """Validate a LinkedIn post against formatting rules.
        
        Args:
            title: Post title.
            content: Post content.
            hashtags: List of hashtags.
            
        Returns:
            ValidationResult with errors and warnings.
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Validate no Markdown in content
        self._check_markdown(content, result)
        
        # Validate no Markdown in title
        self._check_markdown(title, result)
        
        # Validate hook strength
        self._check_hook(content, result)
        
        # Validate paragraph length
        self._check_paragraph_length(content, result)
        
        # Validate sentence length
        self._check_sentence_length(content, result)
        
        # Validate word count
        self._check_word_count(content, result)
        
        # Validate hashtags
        self._check_hashtags(hashtags, result)
        
        # Validate CTA
        self._check_cta(content, result)
        
        # Validate formatting quality
        self._check_formatting_quality(content, result)
        
        return result
    
    def _check_markdown(self, text: str, result: ValidationResult) -> None:
        """Check for Markdown syntax in text."""
        for pattern, description in self.MARKDOWN_PATTERNS:
            if re.search(pattern, text):
                result.add_error(f"Found {description} in text. LinkedIn does not render Markdown.")
                logger.warning(f"Markdown detected: {description}")
    
    def _check_hook(self, content: str, result: ValidationResult) -> None:
        """Check if the post has a strong hook."""
        lines = content.strip().split('\n')
        if not lines:
            result.add_error("Post content is empty")
            return
        
        first_line = lines[0].strip()
        
        # Check if first line is too long (should grab attention in first 2 lines)
        if len(first_line.split()) > 20:
            result.add_warning("Hook might be too long. First line should grab attention quickly.")
        
        # Check for weak hook patterns
        weak_hooks = [
            'in this post',
            'today i want to talk about',
            'here is',
            'in this article',
        ]
        
        first_line_lower = first_line.lower()
        for weak_hook in weak_hooks:
            if weak_hook in first_line_lower:
                result.add_warning(f"Weak hook detected: '{weak_hook}'. Consider a stronger opening.")
    
    def _check_paragraph_length(self, content: str, result: ValidationResult) -> None:
        """Check if paragraphs are too long."""
        paragraphs = content.split('\n\n')
        
        for i, paragraph in enumerate(paragraphs):
            lines = paragraph.split('\n')
            if len(lines) > self.max_paragraph_lines:
                result.add_warning(
                    f"Paragraph {i+1} is {len(lines)} lines. Max recommended is {self.max_paragraph_lines} lines."
                )
    
    def _check_sentence_length(self, content: str, result: ValidationResult) -> None:
        """Check if sentences are too long."""
        sentences = re.split(r'[.!?]+', content)
        
        for i, sentence in enumerate(sentences):
            word_count = len(sentence.split())
            if word_count > self.max_sentence_words:
                result.add_warning(
                    f"Sentence {i+1} is {word_count} words. Max recommended is {self.max_sentence_words} words."
                )
    
    def _check_word_count(self, content: str, result: ValidationResult) -> None:
        """Check if word count is within acceptable range."""
        word_count = len(content.split())
        
        if word_count < self.min_words:
            result.add_warning(
                f"Post is {word_count} words. Minimum recommended is {self.min_words} words."
            )
        elif word_count > self.max_words:
            result.add_warning(
                f"Post is {word_count} words. Maximum recommended is {self.max_words} words."
            )
    
    def _check_hashtags(self, hashtags: List[str], result: ValidationResult) -> None:
        """Check if hashtags are properly formatted."""
        if not hashtags:
            result.add_error("No hashtags provided. Add 5-8 relevant hashtags.")
            return
        
        if len(hashtags) < self.min_hashtags:
            result.add_error(
                f"Only {len(hashtags)} hashtags. Minimum required is {self.min_hashtags}."
            )
        elif len(hashtags) > self.max_hashtags:
            result.add_warning(
                f"{len(hashtags)} hashtags. Maximum recommended is {self.max_hashtags}."
            )
        
        # Check hashtag format
        for tag in hashtags:
            if not tag.startswith('#'):
                result.add_error(f"Hashtag '{tag}' does not start with #")
    
    def _check_cta(self, content: str, result: ValidationResult) -> None:
        """Check if post has a call-to-action."""
        cta_patterns = [
            r'what do you think',
            r'how would you',
            r'have you',
            r'what\'s your',
            r'your thoughts',
            r'agree or disagree',
        ]
        
        content_lower = content.lower()
        has_cta = any(re.search(pattern, content_lower) for pattern in cta_patterns)
        
        if not has_cta:
            result.add_warning("No clear call-to-action detected. Consider adding a question to engage readers.")
    
    def _check_formatting_quality(self, content: str, result: ValidationResult) -> None:
        """Check for good formatting practices."""
        # Check for bullet points or numbered lists
        has_bullets = bool(re.search(r'•\s', content))
        has_numbers = bool(re.search(r'^\d+\.\s', content, re.MULTILINE))
        
        if not has_bullets and not has_numbers:
            result.add_warning("No bullet points or numbered lists detected. Consider using them for better readability.")
        
        # Check for sufficient whitespace
        line_breaks = content.count('\n\n')
        if line_breaks < 2:
            result.add_warning("Insufficient paragraph breaks. Add more whitespace for readability.")
        
        # Check for emoji overuse
        emoji_count = len(re.findall(r'[^\w\s,.\!?]', content))
        if emoji_count > 5:
            result.add_warning(f"Too many emojis ({emoji_count}). Use sparingly (max 2-3 per post).")
    
    def get_validation_summary(self, result: ValidationResult) -> str:
        """Get a human-readable summary of validation results.
        
        Args:
            result: ValidationResult to summarize.
            
        Returns:
            Formatted summary string.
        """
        lines = []
        
        if result.is_valid:
            lines.append("✅ Post validation passed!")
        else:
            lines.append("❌ Post validation failed!")
        
        if result.errors:
            lines.append("\n🔴 Errors:")
            for error in result.errors:
                lines.append(f"  • {error}")
        
        if result.warnings:
            lines.append("\n🟡 Warnings:")
            for warning in result.warnings:
                lines.append(f"  • {warning}")
        
        if result.is_valid and not result.warnings:
            lines.append("\n✨ Post looks great! Ready for review.")
        
        '\n'.join(lines)
        return '\n'.join(lines)


def validate_linkedin_post(title: str, content: str, hashtags: List[str]) -> Tuple[bool, str]:
    """Convenience function to validate a LinkedIn post.
    
    Args:
        title: Post title.
        content: Post content.
        hashtags: List of hashtags.
        
    Returns:
        Tuple of (is_valid, summary_message).
    """
    validator = LinkedInValidator()
    result = validator.validate(title, content, hashtags)
    summary = validator.get_validation_summary(result)
    
    return result.is_valid, summary


if __name__ == "__main__":
    # Test the validator
    print("Testing LinkedIn Validator\n")
    
    # Test with bad formatting
    bad_title = "# This is a **bad** title"
    bad_content = """## Introduction
This post has **markdown** and `code` fences.

It's a wall of text without proper formatting. The sentences are very long and go on and on without any breaks which makes it hard to read on mobile devices."""
    bad_hashtags = ["#Python", "#Coding"]
    
    is_valid, summary = validate_linkedin_post(bad_title, bad_content, bad_hashtags)
    print(f"Bad post validation: {is_valid}")
    print(summary)
    
    print("\n" + "="*50 + "\n")
    
    # Test with good formatting
    good_title = "I Finally Understood OOP"
    good_content = """I thought I understood OOP... until I actually implemented it.

After building multiple projects, one concept finally clicked.

Here's what I learned:

• Encapsulation is about hiding complexity
• Inheritance isn't always the answer
• Composition over inheritance

The biggest lesson for me was that simple code beats clever code every time.

What do you think?"""
    good_hashtags = ["#Python", "#OOP", "#SoftwareEngineering", "#Programming", "#Developer"]
    
    is_valid, summary = validate_linkedin_post(good_title, good_content, good_hashtags)
    print(f"Good post validation: {is_valid}")
    print(summary)
