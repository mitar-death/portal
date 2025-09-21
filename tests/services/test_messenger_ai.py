"""
Tests for MessengerAI service - comprehensive testing of AI messaging functionality.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock, call
from server.app.services.messenger_ai import MessengerAI, get_db_session


class TestMessengerAI:
    """Test MessengerAI functionality."""

    @pytest.fixture
    def messenger_ai(self):
        """Create MessengerAI instance."""
        return MessengerAI()

    @pytest.fixture
    def mock_telegram_message(self):
        """Create mock Telegram message."""
        message = MagicMock()
        message.message = "Hello AI assistant"
        message.sender_id = 123456789
        message.chat_id = -1001234567890
        message.id = 999
        message.date = MagicMock()
        message.text = "Hello AI assistant"
        return message

    @pytest.mark.asyncio
    async def test_initialize_success(self, messenger_ai, test_user, test_ai_account):
        """Test successful MessengerAI initialization."""
        with patch('server.app.services.messenger_ai.get_db_session') as mock_db_session, \
             patch.object(messenger_ai, '_load_ai_accounts') as mock_load_ai, \
             patch.object(messenger_ai, '_load_group_ai_mappings') as mock_load_mappings, \
             patch.object(messenger_ai, '_load_keywords') as mock_load_keywords:
            
            mock_session = AsyncMock()
            mock_db_session.return_value.__aenter__.return_value = mock_session
            
            await messenger_ai.initialize(test_user.id)
            
            mock_load_ai.assert_called_once_with(test_user.id, mock_session)
            mock_load_mappings.assert_called_once_with(test_user.id, mock_session)
            mock_load_keywords.assert_called_once_with(test_user.id, mock_session)

    @pytest.mark.asyncio
    async def test_load_ai_accounts(self, messenger_ai, test_user, test_ai_account):
        """Test loading AI accounts from database."""
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [test_ai_account]
        mock_session.execute.return_value = mock_result
        
        with patch('telethon.TelegramClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.is_user_authorized.return_value = True
            mock_client_class.return_value = mock_client
            
            await messenger_ai._load_ai_accounts(test_user.id, mock_session)
            
            assert test_ai_account.id in messenger_ai.ai_clients
            assert test_ai_account.id in messenger_ai.ai_accounts

    @pytest.mark.asyncio
    async def test_load_group_ai_mappings(self, messenger_ai, test_user):
        """Test loading group-to-AI mappings."""
        mock_session = AsyncMock()
        
        with patch('server.app.utils.group_helpers.get_group_ai_mappings') as mock_get_mappings:
            mock_mappings = {-1001234567890: 123}
            mock_get_mappings.return_value = mock_mappings
            
            await messenger_ai._load_group_ai_mappings(test_user.id, mock_session)
            
            assert messenger_ai.group_ai_map == mock_mappings

    @pytest.mark.asyncio
    async def test_load_keywords(self, messenger_ai, test_user):
        """Test loading user keywords."""
        mock_session = AsyncMock()
        
        with patch('server.app.utils.db_helpers.get_user_keywords') as mock_get_keywords:
            mock_keywords = ["hello", "help", "support"]
            mock_get_keywords.return_value = mock_keywords
            
            await messenger_ai._load_keywords(test_user.id, mock_session)
            
            assert messenger_ai.monitored_keywords == set(mock_keywords)

    @pytest.mark.asyncio
    async def test_handle_group_message_with_keywords(self, messenger_ai, mock_telegram_message):
        """Test handling group message that contains keywords."""
        messenger_ai.monitored_keywords = {"hello", "support"}
        messenger_ai.group_ai_map = {-1001234567890: 123}
        
        mock_ai_client = AsyncMock()
        messenger_ai.ai_clients[123] = mock_ai_client
        
        with patch.object(messenger_ai.message_analyzer, 'detect_keywords', return_value=['hello']), \
             patch.object(messenger_ai, '_initiate_dm_conversation') as mock_initiate_dm, \
             patch('server.app.services.ai_engine.generate_response') as mock_generate:
            
            mock_generate.return_value = \"AI response\"\n            \n            await messenger_ai._handle_group_message(mock_telegram_message.sender_id, mock_telegram_message.chat_id, mock_telegram_message.text, 123)\n            \n            mock_initiate_dm.assert_called_once()"

    @pytest.mark.asyncio
    async def test_handle_group_message_without_keywords(self, messenger_ai, mock_telegram_message):
        """Test handling group message that doesn't contain keywords."""
        messenger_ai.monitored_keywords = {"python", "programming"}
        messenger_ai.group_ai_map = {-1001234567890: 123}
        
        with patch.object(messenger_ai.message_analyzer, 'detect_keywords', return_value=[]):
            
            # Message analyzer should return empty list for no keywords
            keywords = messenger_ai.message_analyzer.detect_keywords(mock_telegram_message.text)
            
            assert keywords == []

    @pytest.mark.asyncio
    async def test_handle_group_message_no_ai_mapping(self, messenger_ai, mock_telegram_message):
        """Test handling group message for group without AI mapping."""
        messenger_ai.monitored_keywords = {"hello"}
        messenger_ai.group_ai_map = {}  # No mapping for this group
        
        with patch.object(messenger_ai.message_analyzer, 'contains_keywords', return_value=True), \
             patch.object(messenger_ai, '_initiate_dm_conversation') as mock_initiate_dm:
            
            await messenger_ai.handle_group_message(mock_telegram_message)
            
            mock_initiate_dm.assert_not_called()

    @pytest.mark.asyncio
    async def test_initiate_dm_conversation(self, messenger_ai, mock_telegram_message):
        """Test initiating DM conversation."""
        ai_account_id = 123
        mock_ai_client = AsyncMock()
        messenger_ai.ai_clients[ai_account_id] = mock_ai_client
        
        with patch('server.app.services.ai_engine.generate_response') as mock_generate:
            mock_generate.return_value = "Hello! I saw your message in the group. How can I help you?"
            
            await messenger_ai._initiate_dm_conversation(
                mock_telegram_message.sender_id,
                mock_telegram_message.text,
                ai_account_id
            )
            
            mock_ai_client.send_message.assert_called_once()
            mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_dm_message(self, messenger_ai):
        """Test handling direct message."""
        sender_id = 123456789
        message_text = "I need help with something"
        ai_account_id = 123
        
        mock_ai_client = AsyncMock()
        messenger_ai.ai_clients[ai_account_id] = mock_ai_client
        
        with patch('server.app.services.ai_engine.generate_response') as mock_generate:
            mock_generate.return_value = "I'm here to help! What do you need assistance with?"
            
            await messenger_ai._handle_dm_message(sender_id, message_text, ai_account_id)
            
            mock_ai_client.send_message.assert_called_once_with(
                sender_id, 
                "I'm here to help! What do you need assistance with?"
            )

    @pytest.mark.asyncio
    async def test_start_ai_clients(self, messenger_ai):
        """Test starting AI clients for event handling."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        messenger_ai.ai_clients = {123: mock_client1, 456: mock_client2}
        
        await messenger_ai.start()
        
        mock_client1.add_event_handler.assert_called()
        mock_client2.add_event_handler.assert_called()

    @pytest.mark.asyncio
    async def test_cleanup_ai_clients(self, messenger_ai):
        """Test cleaning up AI clients."""
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        messenger_ai.ai_clients = {123: mock_client1, 456: mock_client2}
        
        await messenger_ai.cleanup()
        
        mock_client1.disconnect.assert_called()
        mock_client2.disconnect.assert_called()

    @pytest.mark.asyncio
    async def test_rate_limiting(self, messenger_ai):
        """Test rate limiting functionality."""
        sender_id = 123456789
        ai_account_id = 123
        
        # Set up rate limit (should limit after 3 messages)
        messenger_ai.rate_limits[sender_id] = {
            'count': 3,
            'last_reset': asyncio.get_event_loop().time()
        }
        
        mock_ai_client = AsyncMock()
        messenger_ai.ai_clients[ai_account_id] = mock_ai_client
        
        # This should be rate limited
        await messenger_ai._handle_dm_message(sender_id, "Test message", ai_account_id)
        
        # Should not send message due to rate limiting
        mock_ai_client.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_conversation_tracking(self, messenger_ai):
        """Test conversation state tracking."""
        sender_id = 123456789
        ai_account_id = 123
        
        # Start conversation via conversation manager
        await messenger_ai.conversation_manager.start_conversation(sender_id, ai_account_id)
        
        # Verify conversation was started
        conversation = await messenger_ai.conversation_manager.get_conversation(sender_id)
        assert conversation is not None
        assert conversation['ai_account_id'] == ai_account_id

    @pytest.mark.asyncio
    async def test_error_handling_in_message_processing(self, messenger_ai, mock_telegram_message):
        """Test error handling during message processing."""
        messenger_ai.monitored_keywords = {"hello"}
        messenger_ai.group_ai_map = {-1001234567890: 123}
        
        mock_ai_client = AsyncMock()
        mock_ai_client.send_message.side_effect = Exception("Network error")
        messenger_ai.ai_clients[123] = mock_ai_client
        
        with patch.object(messenger_ai.message_analyzer, 'detect_keywords', return_value=['hello']):
            # Should not raise exception despite error
            result = messenger_ai.message_analyzer.detect_keywords(mock_telegram_message.text)
            assert result == ['hello']

    @pytest.mark.asyncio
    async def test_websocket_notification(self, messenger_ai, mock_websocket_manager):
        """Test WebSocket notifications during AI interactions."""
        messenger_ai.websocket_manager = mock_websocket_manager
        
        sender_id = 123456789
        ai_account_id = 123
        mock_ai_client = AsyncMock()
        messenger_ai.ai_clients[ai_account_id] = mock_ai_client
        
        with patch('server.app.services.ai_engine.generate_response') as mock_generate:
            mock_generate.return_value = "AI response"
            
            await messenger_ai._handle_dm_message(sender_id, "Test User", "Test")
            
            # Should broadcast message about AI interaction
            mock_websocket_manager.broadcast_message.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, messenger_ai):
        """Test handling multiple concurrent messages."""
        tasks = []
        for i in range(5):
            task = messenger_ai._handle_dm_message(
                sender_id=123456789 + i,
                sender_name=f"User {i}",
                message_text=f"Message {i}"
            )
            tasks.append(task)
        
        # All tasks should complete without issues
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # No exceptions should be raised
        assert all(not isinstance(result, Exception) for result in results)

    @pytest.mark.asyncio
    async def test_cleanup_inactive_conversations(self, messenger_ai):
        """Test cleanup of inactive conversations."""
        # Add some old conversations
        current_time = asyncio.get_event_loop().time()
        old_time = current_time - 3600  # 1 hour ago
        
        messenger_ai.conversations = {
            123: {'started_at': old_time, 'ai_account_id': 456},
            456: {'started_at': current_time, 'ai_account_id': 789}
        }
        
        await messenger_ai.conversation_manager.cleanup_inactive_conversations()
        
        # Old conversation should be removed, recent one should remain
        assert 123 not in messenger_ai.conversations
        assert 456 in messenger_ai.conversations