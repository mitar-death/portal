"""
Tests for groups routes.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status


class TestGroupsRoutes:
    """Test groups route endpoints."""

    @pytest.mark.asyncio
    async def test_get_groups_success(self, client, auth_headers, test_user):
        """Test successful groups retrieval."""
        with patch('server.app.services.telegram.client_manager.get_user_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_dialogs = [
                MagicMock(
                    entity=MagicMock(
                        id=-1001234567890,
                        title="Test Group",
                        username="testgroup",
                        participants_count=100
                    ),
                    is_group=True,
                    is_channel=False
                )
            ]
            mock_client.iter_dialogs.return_value.__aiter__ = lambda: iter(mock_dialogs)
            mock_get_client.return_value = mock_client
            
            response = client.get("/api/telegram/groups", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert len(data["data"]) == 1
            assert data["data"][0]["title"] == "Test Group"

    @pytest.mark.asyncio
    async def test_get_groups_unauthenticated(self, client):
        """Test groups retrieval without authentication."""
        response = client.get("/api/telegram/groups")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_groups_telegram_error(self, client, auth_headers):
        """Test groups retrieval with Telegram error."""
        with patch('server.app.services.telegram.client_manager.get_user_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.iter_dialogs.side_effect = Exception("Telegram error")
            mock_get_client.return_value = mock_client
            
            response = client.get("/api/telegram/groups", headers=auth_headers)
            
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_update_group_monitoring_success(self, client, auth_headers, test_group):
        """Test successful group monitoring update."""
        response = client.post(f"/api/groups/{test_group.group_id}/monitor", 
                             headers=auth_headers,
                             json={"is_monitored": False})
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_update_group_monitoring_not_found(self, client, auth_headers):
        """Test group monitoring update for non-existent group."""
        response = client.post("/api/groups/999999/monitor", 
                             headers=auth_headers,
                             json={"is_monitored": False})
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_group_details_success(self, client, auth_headers, test_group):
        """Test successful group details retrieval."""
        with patch('server.app.services.telegram.client_manager.get_user_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_entity = MagicMock(
                id=test_group.group_id,
                title=test_group.title,
                username=test_group.username,
                participants_count=test_group.member_count
            )
            mock_client.get_entity.return_value = mock_entity
            mock_get_client.return_value = mock_client
            
            response = client.get(f"/api/groups/{test_group.group_id}", headers=auth_headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["data"]["title"] == test_group.title

    @pytest.mark.asyncio
    async def test_get_group_details_not_found(self, client, auth_headers):
        """Test group details retrieval for non-existent group."""
        response = client.get("/api/groups/999999", headers=auth_headers)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND