"""Research question planner for LinkedIn Content Agent.

This module generates focused research questions for a given topic.
"""

from typing import List


class ResearchQuestionPlanner:
    """Generates research questions for a given topic."""
    
    def generate_questions(self, topic: str) -> List[str]:
        """Generate 3-6 focused research questions for the topic.
        
        Args:
            topic: The topic to research.
            
        Returns:
            List of research questions.
        """
        # Generate questions based on topic keywords
        questions = []
        
        # Base questions
        questions.append(f"What is {topic}?")
        questions.append(f"Why is {topic} important?")
        
        # Add contextual questions based on topic analysis
        topic_lower = topic.lower()
        
        if any(word in topic_lower for word in ["future", "trend", "upcoming", "2026", "next"]):
            questions.append(f"What are the latest trends in {topic}?")
            questions.append(f"What are the predictions for {topic}?")
        elif any(word in topic_lower for word in ["how", "guide", "tutorial", "learn"]):
            questions.append(f"How does {topic} work?")
            questions.append(f"What are the best practices for {topic}?")
        elif any(word in topic_lower for word in ["benefits", "advantages", "pros"]):
            questions.append(f"What are the benefits of {topic}?")
            questions.append(f"What are the challenges with {topic}?")
        else:
            questions.append(f"What are the key aspects of {topic}?")
            questions.append(f"What are real-world applications of {topic}?")
        
        # Ensure we have between 3-6 questions
        if len(questions) > 6:
            questions = questions[:6]
        elif len(questions) < 3:
            questions.append(f"What are the challenges in {topic}?")
        
        return questions
