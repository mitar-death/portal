"""
Tests for AI engine service.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from server.app.services.ai_engine import generate_response, model


class TestAIEngine:
    """Test AI engine functionality."""

    @pytest.mark.asyncio
    async def test_generate_response_success(self):
        """Test successful AI response generation."""
        with patch('server.app.services.ai_engine.model') as mock_model:
            mock_response = MagicMock()
            mock_response.text = "This is a test AI response."
            mock_model.generate_content_async = AsyncMock(return_value=mock_response)
            
            response = await generate_response("Hello, how are you?")
            
            assert response == "This is a test AI response."
            mock_model.generate_content_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_with_context(self):
        """Test AI response generation with context."""
        with patch('server.app.services.ai_engine.model') as mock_model:
            mock_response = MagicMock()
            mock_response.text = "Context-aware response."
            mock_model.generate_content_async = AsyncMock(return_value=mock_response)
            
            response = await generate_response(
                "What's the weather?", 
                context="You are a helpful weather assistant."
            )
            
            assert response == "Context-aware response."
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_empty_message(self):
        """Test AI response generation with empty message."""
        response = await generate_response("")
        
        assert response == "I'm sorry, I didn't receive your message. Could you please try again?"

    @pytest.mark.asyncio
    async def test_generate_response_none_message(self):
        """Test AI response generation with None message."""
        response = await generate_response(None)
        
        assert response == "I'm sorry, I didn't receive your message. Could you please try again?"

    @pytest.mark.asyncio
    async def test_generate_response_api_error(self):
        """Test AI response generation with API error."""
        with patch('server.app.services.ai_engine.model') as mock_model:
            mock_model.generate_content_async = AsyncMock(side_effect=Exception("API Error"))
            
            response = await generate_response("Test message")
            
            assert "I'm sorry, I'm having trouble" in response

    @pytest.mark.asyncio
    async def test_generate_response_empty_ai_response(self):
        """Test AI response generation when AI returns empty response."""
        with patch('server.app.services.ai_engine.model') as mock_model:
            mock_response = MagicMock()
            mock_response.text = ""
            mock_model.generate_content_async = AsyncMock(return_value=mock_response)
            
            response = await generate_response("Test message")
            
            assert "I'm sorry, I couldn't generate a response" in response

    @pytest.mark.asyncio
    async def test_generate_response_none_ai_response(self):
        """Test AI response generation when AI returns None response."""
        with patch.object(model, 'generate_content') as mock_generate:
            mock_response = MagicMock()
            mock_response.text = None
            mock_generate.return_value = mock_response
            
            response = await generate_response("Test message")
            
            assert "I'm sorry, I couldn't generate a response" in response

    @pytest.mark.asyncio
    async def test_generate_response_long_message(self):
        """Test AI response generation with very long message."""
        long_message = "Hello " * 1000  # Very long message
        
        with patch.object(model, 'generate_content') as mock_generate:
            mock_response = MagicMock()
            mock_response.text = "Response to long message."
            mock_generate.return_value = mock_response
            
            response = await generate_response(long_message)
            
            assert response == "Response to long message."
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_response_special_characters(self):
        """Test AI response generation with special characters."""
        special_message = "Hello! @#$%^&*()_+ 🔥 emoji test"
        
        with patch.object(model, 'generate_content') as mock_generate:
            mock_response = MagicMock()
            mock_response.text = "Handled special characters."
            mock_generate.return_value = mock_response
            
            response = await generate_response(special_message)
            
            assert response == "Handled special characters."
            mock_generate.assert_called_once()