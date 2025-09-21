"""
Tests for Telegram service.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock, mock_open
from server.app.services.telegram import ClientManager


class TestClientManager:
    """Test ClientManager functionality."""

    @pytest.fixture
    def client_manager(self, temp_session_dir):
        """Create ClientManager instance with temp directory."""
        with patch('server.app.services.telegram.base_session_dir', Path(temp_session_dir)):
            return ClientManager()

    @pytest.mark.asyncio
    async def test_get_user_session_path(self, client_manager, temp_session_dir):
        """Test user session path generation."""
        user_id = 123
        session_path = client_manager._get_user_session_path(user_id)
        
        expected_path = f"{temp_session_dir}/user_{user_id}/user_session"
        assert str(session_path) == expected_path

    @pytest.mark.asyncio
    async def test_get_user_session_dir(self, client_manager, temp_session_dir):
        """Test user session directory creation."""
        user_id = 123
        session_dir = client_manager._get_user_session_dir(user_id)
        
        expected_dir = f"{temp_session_dir}/user_{user_id}"
        assert str(session_dir) == expected_dir
        assert session_dir.exists()
        
        # Check directory permissions
        stat = session_dir.stat()
        assert oct(stat.st_mode)[-3:] == "700"

    @pytest.mark.asyncio
    async def test_get_user_metadata_file(self, client_manager, temp_session_dir):
        """Test user metadata file path generation."""
        user_id = 123
        metadata_file = client_manager._get_user_metadata_file(user_id)
        
        expected_file = f"{temp_session_dir}/user_{user_id}/session_metadata.json"
        assert str(metadata_file) == expected_file

    @pytest.mark.asyncio
    async def test_initialize_user_client_new_user(self, client_manager, temp_session_dir):
        """Test initializing client for new user."""
        user_id = 123
        
        with patch('telethon.TelegramClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.is_connected.return_value = False
            mock_client.connect.return_value = None
            mock_client.is_user_authorized.return_value = False
            mock_client_class.return_value = mock_client
            
            # Mock telethon session as well
            with patch('server.app.services.telegram.RedisSession') as mock_redis_session:
                mock_redis_session.return_value = None  # Use file session
                client = await client_manager.initialize_user_client(user_id)
            
                assert client == mock_client
                mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_client_existing(self, client_manager):
        """Test getting existing user client."""
        user_id = 123
        mock_client = AsyncMock()
        client_manager._clients[user_id] = mock_client
        
        client = await client_manager.get_user_client(user_id)
        
        assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_user_client_new(self, client_manager, temp_session_dir):
        """Test getting new user client."""
        user_id = 123
        
        with patch.object(client_manager, 'initialize_user_client') as mock_init:
            mock_client = AsyncMock()
            mock_init.return_value = mock_client
            
            client = await client_manager.get_user_client(user_id)
            
            assert client == mock_client
            mock_init.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_get_guest_client_unique_sessions(self, client_manager, temp_session_dir):
        """Test that guest clients get unique session files."""
        phone1 = "+1234567890"
        phone2 = "+9876543210"
        
        with patch('telethon.TelegramClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            client1 = await client_manager.get_guest_client(phone1)
            client2 = await client_manager.get_guest_client(phone2)
            
            # Should have different session files
            assert len(mock_client_class.call_args_list) == 2
            session_path1 = mock_client_class.call_args_list[0][0][0]
            session_path2 = mock_client_class.call_args_list[1][0][0]
            
            assert session_path1 != session_path2

    @pytest.mark.asyncio
    async def test_disconnect_user_client(self, client_manager):
        """Test disconnecting user client."""
        user_id = 123
        mock_client = AsyncMock()
        client_manager._clients[user_id] = mock_client
        
        await client_manager.disconnect_user_client(user_id)
        
        mock_client.disconnect.assert_called_once()
        assert user_id not in client_manager._clients

    @pytest.mark.asyncio
    async def test_disconnect_all_clients(self, client_manager):
        """Test disconnecting all clients."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        client_manager.clients[1] = mock_client1
        client_manager.clients[2] = mock_client2
        
        await client_manager.disconnect_all_clients()
        
        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_called_once()
        assert len(client_manager.clients) == 0

    @pytest.mark.asyncio
    async def test_get_ai_client_from_session_string(self, client_manager):
        """Test creating AI client from session string."""
        ai_account_id = 456
        session_string = "test_session_string"
        
        with patch('telethon.sessions.StringSession') as mock_string_session, \
             patch('telethon.TelegramClient') as mock_client_class:
            
            mock_session = MagicMock()
            mock_string_session.return_value = mock_session
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            client = await client_manager.get_ai_client(ai_account_id, session_string)
            
            assert client == mock_client
            mock_string_session.assert_called_once_with(session_string)
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_client_locks(self, client_manager):
        """Test that user clients use proper locking."""
        user_id = 123
        
        # First call should create lock
        lock1 = client_manager._get_user_lock(user_id)
        lock2 = client_manager._get_user_lock(user_id)
        
        # Should be the same lock object
        assert lock1 is lock2
        assert user_id in client_manager.user_locks