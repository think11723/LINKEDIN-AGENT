"""Hugging Face provider implementation."""

import json
import requests
import time
from typing import Dict, Any, Tuple, Optional
from ..base import (
    BaseProvider, LLMResponse, NetworkError, RateLimitError, 
    TimeoutError, InvalidModelError, MalformedResponseError,
    ProviderUnavailableError
)


class HuggingFaceProvider(BaseProvider):
    """Hugging Face Inference API provider."""
    
    BASE_URL = "https://api-inference.huggingface.co/models"
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.
        
        Args:
            error: Exception to check
            
        Returns:
            True if retryable, False otherwise
        """
        # Retry on rate limit, timeout, and network errors
        return isinstance(error, (RateLimitError, TimeoutError, NetworkError))
    
    def _normalize_response(self, response_data: Any) -> str:
        """Normalize Hugging Face response to text.
        
        Args:
            response_data: Raw response from API
            
        Returns:
            Extracted text string
            
        Raises:
            MalformedResponseError: If response cannot be parsed
        """
        try:
            # Handle different response formats
            if isinstance(response_data, list):
                if len(response_data) == 0:
                    raise MalformedResponseError("Empty response list")
                text = response_data[0].get("generated_text", "")
            elif isinstance(response_data, dict):
                # Check for error field
                if "error" in response_data:
                    raise ProviderUnavailableError(response_data["error"])
                text = response_data.get("generated_text", "")
            else:
                text = str(response_data)
            
            if not text:
                raise MalformedResponseError("No generated text in response")
            
            return text
            
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
        endpoint = f"{self.BASE_URL}/{self.model}"
        
        def _make_request() -> Tuple[str, int]:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_new_tokens": kwargs.get("max_tokens", 2048),
                    "return_full_text": False,
                }
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
                    raise RateLimitError("Hugging Face rate limit exceeded")
                elif response.status_code == 401:
                    raise NetworkError("Invalid Hugging Face API key")
                elif response.status_code == 404:
                    raise InvalidModelError(f"Model not found: {self.model}")
                elif response.status_code == 503:
                    raise ProviderUnavailableError("Hugging Face model is loading or unavailable")
                elif response.status_code >= 500:
                    raise ProviderUnavailableError(f"Hugging Face server error: {response.status_code}")
                elif response.status_code != 200:
                    raise NetworkError(f"Hugging Face API error: {response.status_code}")
                
                # Parse response
                try:
                    result = response.json()
                except json.JSONDecodeError as e:
                    raise MalformedResponseError(f"Invalid JSON response: {str(e)}")
                
                text = self._normalize_response(result)
                return text, response.status_code
                
            except requests.exceptions.Timeout:
                raise TimeoutError("Hugging Face request timed out")
            except requests.exceptions.RequestException as e:
                raise NetworkError(f"Hugging Face network error: {str(e)}")
        
        try:
            # Measure total latency including retries
            start_time = time.time()
            text, http_status = self._retry_with_backoff(_make_request, self._is_retryable_error)
            latency = time.time() - start_time
            
            self._log_request("generate_text", prompt, latency, True, http_status=http_status)
            
            return LLMResponse(
                text=text,
                model=self.model,
                latency=latency,
                metadata={"provider": "huggingface", "http_status": http_status, "endpoint": endpoint}
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
        # Add JSON formatting instruction to prompt
        json_prompt = f"{prompt}\n\nRespond with valid JSON only."

        # ``generate_text`` is async (the base contract is now
        # async). Awaiting it actually executes the call;
        # without ``await`` we'd get a coroutine and the next
        # line (``response.text``) would raise
        # "'coroutine' object has no attribute 'text'".
        response = await self.generate_text(json_prompt, **kwargs)
        
        try:
            # Extract JSON from response
            text = response.text.strip()
            
            # Try to find JSON in the response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            return json.loads(text)
            
        except json.JSONDecodeError as e:
            raise MalformedResponseError(f"Failed to parse JSON from response: {str(e)}")
    
    def health_check(self) -> bool:
        """Check if provider is healthy using a lightweight inference call.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Use a minimal prompt to test the model
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": "test",
                "parameters": {
                    "max_new_tokens": 5,
                }
            }
            
            response = requests.post(
                f"{self.BASE_URL}/{self.model}",
                headers=headers,
                json=payload,
                timeout=10
            )
            
            # Consider healthy if we get a response (even if rate limited)
            return response.status_code in [200, 429, 503]
            
        except Exception:
            return False
