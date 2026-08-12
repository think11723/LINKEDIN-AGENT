"""Tests for LLM providers with mocked HTTP responses."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from services.llm.providers.huggingface import HuggingFaceProvider
from services.llm.providers.openrouter import OpenRouterProvider
from services.llm.providers.groq import GroqProvider
from services.llm.base import (
    MissingAPIKeyError, InvalidModelError, RateLimitError, 
    TimeoutError, NetworkError, MalformedResponseError, ProviderUnavailableError
)


class TestHuggingFaceProvider:
    """Tests for HuggingFace provider."""
    
    def test_initialization_with_valid_config(self):
        """Test provider initialization with valid configuration."""
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        assert provider.api_key == "test_key"
        assert provider.model == "test_model"
    
    def test_initialization_with_missing_api_key(self):
        """Test provider initialization fails with missing API key."""
        with pytest.raises(MissingAPIKeyError):
            HuggingFaceProvider(api_key="", model="test_model")
    
    def test_initialization_with_missing_model(self):
        """Test provider initialization fails with missing model."""
        with pytest.raises(InvalidModelError):
            HuggingFaceProvider(api_key="test_key", model="")
    
    @patch('services.llm.providers.huggingface.requests.post')
    def test_generate_text_success(self, mock_post):
        """Test successful text generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"generated_text": "Test response"}]
        mock_post.return_value = mock_response
        
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        response = provider.generate_text("Test prompt")
        
        assert response.text == "Test response"
        assert response.model == "test_model"
        assert response.metadata["provider"] == "huggingface"
    
    @patch('services.llm.providers.huggingface.requests.post')
    def test_generate_text_rate_limit(self, mock_post):
        """Test rate limit error handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response
        
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        with pytest.raises(RateLimitError):
            provider.generate_text("Test prompt")
    
    @patch('services.llm.providers.huggingface.requests.post')
    def test_generate_text_invalid_key(self, mock_post):
        """Test invalid API key error handling."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        with pytest.raises(NetworkError):
            provider.generate_text("Test prompt")
    
    @patch('services.llm.providers.huggingface.requests.post')
    def test_generate_text_model_not_found(self, mock_post):
        """Test model not found error handling."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        with pytest.raises(InvalidModelError):
            provider.generate_text("Test prompt")
    
    @patch('services.llm.providers.huggingface.requests.post')
    def test_generate_text_timeout(self, mock_post):
        """Test timeout error handling."""
        mock_post.side_effect = requests.exceptions.Timeout()
        
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        with pytest.raises(TimeoutError):
            provider.generate_text("Test prompt")
    
    @patch('services.llm.providers.huggingface.requests.post')
    def test_generate_text_malformed_response(self, mock_post):
        """Test malformed JSON response handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        with pytest.raises(MalformedResponseError):
            provider.generate_text("Test prompt")
    
    @patch('services.llm.providers.huggingface.requests.post')
    def test_generate_text_empty_response(self, mock_post):
        """Test empty response handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_post.return_value = mock_response
        
        provider = HuggingFaceProvider(api_key="test_key", model="test_model")
        with pytest.raises(MalformedResponseError):
            provider.generate_text("Test prompt")


class TestOpenRouterProvider:
    """Tests for OpenRouter provider."""
    
    def test_initialization_with_valid_config(self):
        """Test provider initialization with valid configuration."""
        provider = OpenRouterProvider(api_key="test_key", model="test_model")
        assert provider.api_key == "test_key"
        assert provider.model == "test_model"
    
    def test_initialization_with_missing_api_key(self):
        """Test provider initialization fails with missing API key."""
        with pytest.raises(MissingAPIKeyError):
            OpenRouterProvider(api_key="", model="test_model")
    
    @patch('services.llm.providers.openrouter.requests.post')
    def test_generate_text_success(self, mock_post):
        """Test successful text generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"total_tokens": 100}
        }
        mock_post.return_value = mock_response
        
        provider = OpenRouterProvider(api_key="test_key", model="test_model")
        response = provider.generate_text("Test prompt")
        
        assert response.text == "Test response"
        assert response.tokens_used == 100
        assert response.metadata["provider"] == "openrouter"
    
    @patch('services.llm.providers.openrouter.requests.post')
    def test_generate_text_rate_limit(self, mock_post):
        """Test rate limit error handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response
        
        provider = OpenRouterProvider(api_key="test_key", model="test_model")
        with pytest.raises(RateLimitError):
            provider.generate_text("Test prompt")
    
    @patch('services.llm.providers.openrouter.requests.post')
    def test_generate_text_malformed_response(self, mock_post):
        """Test malformed response handling."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}
        mock_post.return_value = mock_response
        
        provider = OpenRouterProvider(api_key="test_key", model="test_model")
        with pytest.raises(MalformedResponseError):
            provider.generate_text("Test prompt")


class TestGroqProvider:
    """Tests for Groq provider."""
    
    def test_initialization_with_valid_config(self):
        """Test provider initialization with valid configuration."""
        provider = GroqProvider(api_key="test_key", model="test_model")
        assert provider.api_key == "test_key"
        assert provider.model == "test_model"
    
    def test_initialization_with_missing_api_key(self):
        """Test provider initialization fails with missing API key."""
        with pytest.raises(MissingAPIKeyError):
            GroqProvider(api_key="", model="test_model")
    
    @patch('services.llm.providers.groq.requests.post')
    def test_generate_text_success(self, mock_post):
        """Test successful text generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}],
            "usage": {"total_tokens": 100}
        }
        mock_post.return_value = mock_response
        
        provider = GroqProvider(api_key="test_key", model="test_model")
        response = provider.generate_text("Test prompt")
        
        assert response.text == "Test response"
        assert response.tokens_used == 100
        assert response.metadata["provider"] == "groq"
    
    @patch('services.llm.providers.groq.requests.post')
    def test_generate_text_rate_limit(self, mock_post):
        """Test rate limit error handling."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_post.return_value = mock_response
        
        provider = GroqProvider(api_key="test_key", model="test_model")
        with pytest.raises(RateLimitError):
            provider.generate_text("Test prompt")
