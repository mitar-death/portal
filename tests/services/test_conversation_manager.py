"""
Tests for ConversationManager service.
"""
import pytest
from unittest.mock import patch, AsyncMock
from server.app.services.conversation_manager import ConversationManager


class TestConversationManager:
    """Test ConversationManager functionality."""

    @pytest.fixture
    def conversation_manager(self):
        """Create ConversationManager instance."""
        return ConversationManager()

    @pytest.mark.asyncio
    async def test_start_conversation(self, conversation_manager):
        """Test starting a new conversation."""
        user_id = 123456789
        ai_account_id = 456
        
        conversation_manager.start_conversation(user_id, ai_account_id)
        
        assert user_id in conversation_manager.conversations
        conversation = conversation_manager.conversations[user_id]
        assert conversation['ai_account_id'] == ai_account_id
        assert 'started_at' in conversation
        assert 'messages' in conversation

    @pytest.mark.asyncio
    async def test_add_message_to_conversation(self, conversation_manager):
        """Test adding message to existing conversation."""
        user_id = 123456789
        ai_account_id = 456
        
        conversation_manager.start_conversation(user_id, ai_account_id)
        conversation_manager.add_message(user_id, "Hello", "user")
        conversation_manager.add_message(user_id, "Hi there!", "ai")
        
        messages = conversation_manager.conversations[user_id]['messages']
        assert len(messages) == 2
        assert messages[0]['content'] == "Hello"
        assert messages[0]['sender'] == "user"
        assert messages[1]['content'] == "Hi there!"
        assert messages[1]['sender'] == "ai"

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, conversation_manager):
        """Test getting conversation history."""
        user_id = 123456789
        ai_account_id = 456
        
        conversation_manager.start_conversation(user_id, ai_account_id)
        conversation_manager.add_message(user_id, "Message 1", "user")
        conversation_manager.add_message(user_id, "Response 1", "ai")
        
        history = conversation_manager.get_conversation_history(user_id)
        
        assert len(history) == 2
        assert history[0]['content'] == "Message 1"
        assert history[1]['content'] == "Response 1"

    @pytest.mark.asyncio
    async def test_get_conversation_history_nonexistent(self, conversation_manager):
        """Test getting history for non-existent conversation."""
        user_id = 999999999
        
        history = conversation_manager.get_conversation_history(user_id)
        
        assert history == []

    @pytest.mark.asyncio
    async def test_end_conversation(self, conversation_manager):
        """Test ending a conversation."""
        user_id = 123456789
        ai_account_id = 456
        
        conversation_manager.start_conversation(user_id, ai_account_id)
        conversation_manager.add_message(user_id, "Hello", "user")
        
        conversation_manager.end_conversation(user_id)
        
        assert user_id not in conversation_manager.conversations

    @pytest.mark.asyncio
    async def test_is_conversation_active(self, conversation_manager):
        """Test checking if conversation is active."""
        user_id = 123456789
        ai_account_id = 456
        
        # No conversation yet
        assert conversation_manager.is_conversation_active(user_id) is False
        
        # Start conversation
        conversation_manager.start_conversation(user_id, ai_account_id)
        assert conversation_manager.is_conversation_active(user_id) is True
        
        # End conversation
        conversation_manager.end_conversation(user_id)
        assert conversation_manager.is_conversation_active(user_id) is False

    @pytest.mark.asyncio
    async def test_get_conversation_context(self, conversation_manager):
        """Test getting conversation context for AI."""
        user_id = 123456789
        ai_account_id = 456
        
        conversation_manager.start_conversation(user_id, ai_account_id)
        conversation_manager.add_message(user_id, "I need help with Python", "user")
        conversation_manager.add_message(user_id, "I'd be happy to help with Python!", "ai")
        conversation_manager.add_message(user_id, "How do I create a list?", "user")
        
        context = conversation_manager.get_conversation_context(user_id, max_messages=5)
        
        # Should return formatted context string
        assert isinstance(context, str)
        assert "Python" in context
        assert "list" in context

    @pytest.mark.asyncio
    async def test_get_conversation_context_limit(self, conversation_manager):
        """Test conversation context with message limit."""
        user_id = 123456789
        ai_account_id = 456
        
        conversation_manager.start_conversation(user_id, ai_account_id)
        
        # Add more messages than the limit
        for i in range(10):
            conversation_manager.add_message(user_id, f"Message {i}", "user")
            conversation_manager.add_message(user_id, f"Response {i}", "ai")
        
        context = conversation_manager.get_conversation_context(user_id, max_messages=4)
        
        # Should only include the last 4 messages
        lines = context.strip().split('\n')
        assert len(lines) <= 4

    @pytest.mark.asyncio
    async def test_cleanup_old_conversations(self, conversation_manager):
        """Test cleanup of old conversations."""
        import time
        
        user_id_1 = 123456789
        user_id_2 = 987654321
        ai_account_id = 456
        
        # Start conversations
        conversation_manager.start_conversation(user_id_1, ai_account_id)
        conversation_manager.start_conversation(user_id_2, ai_account_id)
        
        # Make one conversation appear old
        old_time = time.time() - 7200  # 2 hours ago
        conversation_manager.conversations[user_id_1]['started_at'] = old_time
        
        conversation_manager.cleanup_old_conversations(max_age_hours=1)
        
        # Old conversation should be removed
        assert user_id_1 not in conversation_manager.conversations
        assert user_id_2 in conversation_manager.conversations

    @pytest.mark.asyncio
    async def test_get_active_conversations_count(self, conversation_manager):
        """Test getting count of active conversations."""
        assert conversation_manager.get_active_conversations_count() == 0
        
        # Start some conversations
        for i in range(3):
            conversation_manager.start_conversation(123456789 + i, 456)
        
        assert conversation_manager.get_active_conversations_count() == 3

    @pytest.mark.asyncio
    async def test_get_conversation_summary(self, conversation_manager):
        """Test getting conversation summary."""
        user_id = 123456789
        ai_account_id = 456
        
        conversation_manager.start_conversation(user_id, ai_account_id)
        conversation_manager.add_message(user_id, "Help with coding", "user")
        conversation_manager.add_message(user_id, "Sure, what language?", "ai")
        conversation_manager.add_message(user_id, "Python please", "user")
        
        summary = conversation_manager.get_conversation_summary(user_id)
        
        assert 'user_id' in summary
        assert 'ai_account_id' in summary
        assert 'message_count' in summary
        assert 'started_at' in summary
        assert summary['message_count'] == 3