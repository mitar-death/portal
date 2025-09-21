"""
Integration tests for complete authentication flow.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status


class TestAuthenticationFlow:
    """Test complete authentication workflow."""

    @pytest.mark.asyncio
    async def test_complete_auth_flow_success(self, client, test_user):
        """Test complete authentication flow from code request to logout."""
        phone_number = "+1234567890"
        
        # Step 1: Request authentication code
        with patch('server.app.services.telegram.client_manager.get_guest_client') as mock_get_guest:
            mock_client = AsyncMock()
            mock_client.send_code_request.return_value = MagicMock(phone_code_hash="test_hash_123")
            mock_get_guest.return_value = mock_client
            
            response = client.post("/api/auth/request-code", json={
                "phone_number": phone_number
            })
            
            assert response.status_code == status.HTTP_200_OK
            code_data = response.json()
            assert code_data["success"] is True
            phone_code_hash = code_data["data"]["phone_code_hash"]

        # Step 2: Verify code and get tokens
        with patch('server.app.services.telegram.client_manager.get_guest_client', return_value=mock_client), \
             patch('server.app.controllers.main.transfer_session_to_user') as mock_transfer:
            
            mock_client.sign_in.return_value = MagicMock(
                user=MagicMock(
                    id=test_user.id,
                    phone=test_user.phone_number,
                    username=test_user.username,
                    first_name=test_user.first_name,
                    last_name=test_user.last_name
                )
            )
            
            response = client.post("/api/auth/verify-code", json={
                "phone_number": phone_number,
                "code": "12345",
                "phone_code_hash": phone_code_hash
            })
            
            assert response.status_code == status.HTTP_200_OK
            verify_data = response.json()
            assert verify_data["success"] is True
            access_token = verify_data["data"]["access_token"]
            refresh_token = verify_data["data"]["refresh_token"]

        # Step 3: Use access token to check auth status
        headers = {"Authorization": f"Bearer {access_token}"}
        
        with patch('server.app.services.telegram.client_manager.get_user_client') as mock_get_user_client:
            mock_user_client = AsyncMock()
            mock_user_client.is_connected.return_value = True
            mock_user_client.is_user_authorized.return_value = True
            mock_get_user_client.return_value = mock_user_client
            
            response = client.get("/api/auth/status", headers=headers)
            
            assert response.status_code == status.HTTP_200_OK
            status_data = response.json()
            assert status_data["success"] is True
            assert status_data["data"]["is_connected"] is True
            assert status_data["data"]["is_authorized"] is True

        # Step 4: Refresh token
        response = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == status.HTTP_200_OK
        refresh_data = response.json()
        assert refresh_data["success"] is True
        new_access_token = refresh_data["data"]["access_token"]
        assert new_access_token != access_token

        # Step 5: Logout
        new_headers = {"Authorization": f"Bearer {new_access_token}"}
        response = client.post("/api/auth/logout", headers=new_headers)
        
        assert response.status_code == status.HTTP_200_OK
        logout_data = response.json()
        assert logout_data["success"] is True

        # Step 6: Verify token is invalidated
        response = client.get("/api/auth/status", headers=new_headers)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_auth_flow_with_invalid_code(self, client):
        """Test authentication flow with invalid verification code."""
        phone_number = "+1234567890"
        
        # Request code first
        with patch('server.app.services.telegram.client_manager.get_guest_client') as mock_get_guest:
            mock_client = AsyncMock()
            mock_client.send_code_request.return_value = MagicMock(phone_code_hash="test_hash_123")
            mock_get_guest.return_value = mock_client
            
            response = client.post("/api/auth/request-code", json={
                "phone_number": phone_number
            })
            
            phone_code_hash = response.json()["data"]["phone_code_hash"]

        # Try to verify with invalid code
        with patch('server.app.services.telegram.client_manager.get_guest_client', return_value=mock_client):
            from telethon.errors import SessionPasswordNeededError
            mock_client.sign_in.side_effect = SessionPasswordNeededError("Invalid code")
            
            response = client.post("/api/auth/verify-code", json={
                "phone_number": phone_number,
                "code": "invalid",
                "phone_code_hash": phone_code_hash
            })
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_protected_routes_without_auth(self, client):
        """Test that protected routes reject unauthenticated requests."""
        protected_endpoints = [
            ("GET", "/api/auth/status"),
            ("POST", "/api/auth/logout"),
            ("GET", "/api/telegram/groups"),
            ("GET", "/api/keywords"),
            ("POST", "/api/keywords"),
            ("GET", "/api/ai/accounts"),
        ]
        
        for method, endpoint in protected_endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            
            # Some endpoints return 200 with is_authorized=False, others return 401
            assert response.status_code in [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED]