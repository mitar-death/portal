"""
Tests for authentication routes.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status


class TestAuthRoutes:
    """Test authentication route endpoints."""

    @pytest.mark.asyncio
    async def test_request_code_success(self, client, mock_telegram_client):
        """Test successful code request."""
        with patch('server.app.services.telegram.client_manager.get_guest_client', return_value=mock_telegram_client):
            mock_telegram_client.send_code_request.return_value = MagicMock(phone_code_hash="test_hash")
            
            response = client.post("/api/auth/request-code", json={
                "phone_number": "+1234567890"
            })
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "phone_code_hash" in data["data"]

    @pytest.mark.asyncio  
    async def test_request_code_invalid_phone(self, client):
        """Test code request with invalid phone number."""
        response = client.post("/api/auth/request-code", json={
            "phone_number": "invalid"
        })
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_request_code_missing_phone(self, client):
        """Test code request without phone number."""
        response = client.post("/api/auth/request-code", json={})
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_verify_code_success(self, client, mock_telegram_client, test_user):
        """Test successful code verification."""
        with patch('server.app.services.telegram.client_manager.get_guest_client', return_value=mock_telegram_client), \
             patch('server.app.controllers.main.transfer_session_to_user') as mock_transfer:
            
            mock_telegram_client.sign_in.return_value = MagicMock(
                user=MagicMock(
                    id=test_user.id,
                    phone=test_user.phone_number,
                    username=test_user.username,
                    first_name=test_user.first_name,
                    last_name=test_user.last_name
                )
            )
            
            response = client.post("/api/auth/verify-code", json={
                "phone_number": "+1234567890",
                "code": "12345",
                "phone_code_hash": "test_hash"
            })
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert "access_token" in data["data"]
            assert "refresh_token" in data["data"]

    @pytest.mark.asyncio
    async def test_verify_code_invalid(self, client, mock_telegram_client):
        """Test code verification with invalid code."""
        with patch('server.app.services.telegram.client_manager.get_guest_client', return_value=mock_telegram_client):
            from telethon.errors import SessionPasswordNeededError
            mock_telegram_client.sign_in.side_effect = SessionPasswordNeededError("Invalid code")
            
            response = client.post("/api/auth/verify-code", json={
                "phone_number": "+1234567890",
                "code": "invalid",
                "phone_code_hash": "test_hash"
            })
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, test_user):
        """Test successful token refresh."""
        from server.app.core.jwt_utils import create_token_pair
        
        tokens = create_token_pair(test_user.id)
        refresh_token = tokens["refresh_token"]
        
        response = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client):
        """Test token refresh with invalid token."""
        response = client.post("/api/auth/refresh", json={
            "refresh_token": "invalid_token"
        })
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_auth_status_authenticated(self, client, auth_headers, test_user):
        """Test auth status for authenticated user."""
        with patch('server.app.services.telegram.client_manager.get_user_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.is_connected.return_value = True
            mock_client.is_user_authorized.return_value = True
            mock_get_client.return_value = mock_client
            
            response = client.get("/api/auth/status", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["data"]["is_connected"] is True
            assert data["data"]["is_authorized"] is True

    @pytest.mark.asyncio
    async def test_auth_status_unauthenticated(self, client):
        """Test auth status for unauthenticated user."""
        response = client.get("/api/auth/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["is_connected"] is False
        assert data["data"]["is_authorized"] is False

    @pytest.mark.asyncio
    async def test_logout_success(self, client, auth_headers):
        """Test successful logout."""
        response = client.post("/api/auth/logout", headers=auth_headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_logout_unauthenticated(self, client):
        """Test logout without authentication."""
        response = client.post("/api/auth/logout")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED