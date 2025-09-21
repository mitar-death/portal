"""
Tests for AI routes.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status


class TestAIRoutes:
    """Test AI route endpoints."""

    @pytest.mark.asyncio
    async def test_generate_response_success(self, client, auth_headers, mock_ai_engine):
        """Test successful AI response generation."""
        mock_ai_engine.return_value = "This is a test AI response."
        
        response = client.post("/api/ai/generate", 
                             headers=auth_headers,
                             json={
                                 "message": "Hello, how are you?",
                                 "context": "friendly_chat"
                             })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "response" in data["data"]
        assert data["data"]["response"] == "This is a test AI response."

    @pytest.mark.asyncio
    async def test_generate_response_missing_message(self, client, auth_headers):
        """Test AI response generation without message."""
        response = client.post("/api/ai/generate", 
                             headers=auth_headers,
                             json={"context": "friendly_chat"})
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_generate_response_unauthenticated(self, client):
        """Test AI response generation without authentication."""
        response = client.post("/api/ai/generate", 
                             json={"message": "Hello"})
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_generate_response_ai_error(self, client, auth_headers):
        """Test AI response generation with AI service error."""
        with patch('server.app.services.ai_engine.generate_response') as mock_ai:
            mock_ai.side_effect = Exception("AI service error")
            
            response = client.post("/api/ai/generate", 
                                 headers=auth_headers,
                                 json={"message": "Hello"})
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_get_ai_accounts_success(self, client, auth_headers, test_ai_account):
        """Test successful AI accounts retrieval."""
        response = client.get("/api/ai/accounts", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["phone_number"] == test_ai_account.phone_number

    @pytest.mark.asyncio
    async def test_create_ai_account_success(self, client, auth_headers):
        """Test successful AI account creation."""
        with patch('server.app.services.telegram.client_manager.get_ai_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.is_user_authorized.return_value = True
            mock_client.get_me.return_value = MagicMock(
                id=987654321,
                phone="+9876543210",
                first_name="AI",
                last_name="Bot"
            )
            mock_get_client.return_value = mock_client
            
            response = client.post("/api/ai/accounts", 
                                 headers=auth_headers,
                                 json={
                                     "phone_number": "+9876543210",
                                     "first_name": "AI",
                                     "last_name": "Bot",
                                     "session_string": "test_session"
                                 })
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_ai_account_success(self, client, auth_headers, test_ai_account):
        """Test successful AI account deletion."""
        response = client.delete(f"/api/ai/accounts/{test_ai_account.id}", 
                               headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_delete_ai_account_not_found(self, client, auth_headers):
        """Test AI account deletion for non-existent account."""
        response = client.delete("/api/ai/accounts/999999", 
                               headers=auth_headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND