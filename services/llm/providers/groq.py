"""Groq provider implementation."""

import json
import requests
import time
from typing import Dict, Any, Tuple, Optional
from ..base import (
    BaseProvider, LLMResponse, NetworkError, RateLimitError, 
    TimeoutError, InvalidModelError, MalformedResponseError,
    ProviderUnavailableError
)


class GroqProvider(BaseProvider):
    """Groq API provider."""
    
    BASE_URL = "https://api.groq.com/openai/v1"
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if retryable, False otherwise
        """
        return isinstance(error, (RateLimitError, TimeoutError, NetworkError))
    
    def _normalize_response(self, response_data: Dict[str, Any]) -> Tuple[str, Optional[int]]:
        """Normalize Groq response to text.
        
        Args:
            response_data: Raw response from API
            
        Returns:
            Tuple of (text, tokens_used)
            
        Raises:
            MalformedResponseError: If response cannot be parsed
        """
        try:
            if "choices" not in response_data or len(response_data["choices"]) == 0:
                raise MalformedResponseError("No choices in response")
            
            text = response_data["choices"][0]["message"]["content"]
            tokens_used = response_data.get("usage", {}).get("total_tokens")
            
            if not text:
                raise MalformedResponseError("No content in response")
            
            return text, tokens_used
            
        except (KeyError, IndexError, TypeError) as e:
            raise MalformedResponseError(f"Failed to parse response: {str(e)}")
    
    async def generate_text(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate text from prompt. Async.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResponse with generated text and metadata
        """
        endpoint = f"{self.BASE_URL}/chat/completions"
        
        def _make_request() -> Tuple[str, Optional[int], int]:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
            }
            
            try:
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                # Handle specific HTTP status codes
                if response.status_code == 429:
                    raise RateLimitError("Groq rate limit exceeded")
                elif response.status_code == 401:
                    raise NetworkError("Invalid Groq API key")
                elif response.status_code == 404:
                    raise InvalidModelError(f"Model not found: {self.model}")
                elif response.status_code == 400:
                    error_msg = response.text
                    # Check if error indicates endpoint not supported
                    if "does not support endpoint" in error_msg or "endpoint" in error_msg.lower():
                        raise UnsupportedModelError(f"Model {self.model} does not support the chat/completions endpoint. Error: {error_msg}")
                    raise InvalidModelError(f"Invalid request: {response.text}")
                elif response.status_code >= 500:
                    raise ProviderUnavailableError(f"Groq server error: {response.status_code}")
                elif response.status_code != 200:
                    raise NetworkError(f"Groq API error: {response.status_code}")
                
                # Parse response
                try:
                    result = response.json()
                except json.JSONDecodeError as e:
                    raise MalformedResponseError(f"Invalid JSON response: {str(e)}")
                
                text, tokens_used = self._normalize_response(result)
                return text, tokens_used, response.status_code
                
            except requests.exceptions.Timeout:
                raise TimeoutError("Groq request timed out")
            except requests.exceptions.RequestException as e:
                raise NetworkError(f"Groq network error: {str(e)}")
        
        try:
            # Measure total latency including retries
            start_time = time.time()
            text, tokens_used, http_status = self._retry_with_backoff(_make_request, self._is_retryable_error)
            latency = time.time() - start_time
            
            self._log_request("generate_text", prompt, latency, True, http_status=http_status)
            
            return LLMResponse(
                text=text,
                model=self.model,
                latency=latency,
                tokens_used=tokens_used,
                metadata={"provider": "groq", "http_status": http_status, "endpoint": endpoint}
            )
            
        except Exception as e:
            self._log_request("generate_text", prompt, 0, False, str(e))
            raise
    
    async def generate_json(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Generate JSON from prompt.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with parsed JSON response
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
            "response_format": {"type": "json_object"},
        }
        
        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                raise NetworkError(f"Groq API error: {response.status_code}")
            
            result = response.json()
            text = result["choices"][0]["message"]["content"]
            
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            raise MalformedResponseError(f"Failed to parse JSON from response: {str(e)}")
    
    def health_check(self) -> bool:
        """Check if provider is healthy using models endpoint.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10
            )
            # Consider healthy if we can access the models endpoint
            return response.status_code in [200, 429]
        except Exception:
            return False
