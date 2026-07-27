"""LLM wrapper for LinkedIn Content Agent.

This module provides a unified interface for all Gemini LLM interactions.
It handles initialization, API key loading, and provides a clean generate_text function.
"""

from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from config.config import config


class LLMWrapper:
    """Wrapper for Gemini LLM interactions."""
    
    def __init__(self, temperature: float = 0.7) -> None:
        """Initialize the LLM wrapper with Gemini.
        
        Args:
            temperature: Temperature for LLM generation (default: 0.7).
        """
        self.llm = ChatGoogleGenerativeAI(
            model=config.model_name or "gemini-1.5-pro",
            api_key=config.gemini_api_key,
            temperature=temperature
        )
    
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None
    ) -> str:
        """Generate text using the LLM.
        
        Args:
            system_prompt: System prompt for the LLM.
            user_prompt: User prompt for the LLM.
            temperature: Optional temperature override for this call.
            
        Returns:
            Generated text string.
            
        Raises:
            Exception: If LLM generation fails.
        """
        try:
            # Update temperature if provided
            if temperature is not None:
                self.llm.temperature = temperature
            
            # Create prompt chain
            chain = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", user_prompt)
            ]) | self.llm
            
            # Generate response
            response = chain.invoke({})
            
            return response.content
            
        except Exception as e:
            # Re-raise with more context
            raise RuntimeError(f"LLM generation failed: {str(e)}") from e


# Global LLM instance with default temperature
default_llm = LLMWrapper(temperature=0.7)


def generate_text(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7
) -> str:
    """Convenience function to generate text using the default LLM instance.
    
    Args:
        system_prompt: System prompt for the LLM.
        user_prompt: User prompt for the LLM.
        temperature: Temperature for LLM generation (default: 0.7).
        
    Returns:
        Generated text string.
        
    Raises:
        Exception: If LLM generation fails.
    """
    return default_llm.generate_text(system_prompt, user_prompt, temperature)
