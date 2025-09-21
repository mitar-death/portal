"""
Tests for message analyzer service.
"""
import pytest
from unittest.mock import patch, AsyncMock
from server.app.services.message_analyzer import MessageAnalyzer


class TestMessageAnalyzer:
    """Test MessageAnalyzer functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create MessageAnalyzer instance."""
        return MessageAnalyzer()

    @pytest.mark.asyncio
    async def test_contains_keywords_simple_match(self, analyzer):
        """Test simple keyword matching."""
        keywords = ["hello", "world"]
        message = "Hello there, this is a test world!"
        
        result = analyzer.contains_keywords(message, keywords)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_contains_keywords_case_insensitive(self, analyzer):
        """Test case insensitive keyword matching."""
        keywords = ["HELLO", "WORLD"]
        message = "hello there, this is a test world!"
        
        result = analyzer.contains_keywords(message, keywords)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_contains_keywords_no_match(self, analyzer):
        """Test when no keywords match."""
        keywords = ["python", "programming"]
        message = "Hello there, this is a test message!"
        
        result = analyzer.contains_keywords(message, keywords)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_contains_keywords_empty_keywords(self, analyzer):
        """Test with empty keywords list."""
        keywords = []
        message = "Hello there, this is a test message!"
        
        result = analyzer.contains_keywords(message, keywords)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_contains_keywords_empty_message(self, analyzer):
        """Test with empty message."""
        keywords = ["hello", "world"]
        message = ""
        
        result = analyzer.contains_keywords(message, keywords)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_contains_keywords_partial_match(self, analyzer):
        """Test partial word matching."""
        keywords = ["test"]
        message = "This is testing message"
        
        result = analyzer.contains_keywords(message, keywords)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_extract_keywords_found(self, analyzer):
        """Test extracting found keywords from message."""
        keywords = ["hello", "world", "python"]
        message = "Hello there, this is a test world!"
        
        found_keywords = analyzer.extract_keywords(message, keywords)
        
        assert "hello" in found_keywords
        assert "world" in found_keywords
        assert "python" not in found_keywords
        assert len(found_keywords) == 2

    @pytest.mark.asyncio
    async def test_extract_keywords_none_found(self, analyzer):
        """Test extracting keywords when none are found."""
        keywords = ["python", "programming"]
        message = "Hello there, this is a test message!"
        
        found_keywords = analyzer.extract_keywords(message, keywords)
        
        assert len(found_keywords) == 0

    @pytest.mark.asyncio
    async def test_should_respond_to_message_with_keywords(self, analyzer):
        """Test response decision with keyword match."""
        with patch.object(analyzer, 'contains_keywords', return_value=True):
            message_data = {
                "text": "Hello there!",
                "sender_id": 123,
                "group_id": -456
            }
            keywords = ["hello"]
            
            should_respond = analyzer.should_respond_to_message(message_data, keywords)
            
            assert should_respond is True

    @pytest.mark.asyncio
    async def test_should_respond_to_message_without_keywords(self, analyzer):
        """Test response decision without keyword match."""
        with patch.object(analyzer, 'contains_keywords', return_value=False):
            message_data = {
                "text": "Random message",
                "sender_id": 123,
                "group_id": -456
            }
            keywords = ["hello"]
            
            should_respond = analyzer.should_respond_to_message(message_data, keywords)
            
            assert should_respond is False

    @pytest.mark.asyncio
    async def test_should_respond_to_message_empty_text(self, analyzer):
        """Test response decision with empty message text."""
        message_data = {
            "text": "",
            "sender_id": 123,
            "group_id": -456
        }
        keywords = ["hello"]
        
        should_respond = analyzer.should_respond_to_message(message_data, keywords)
        
        assert should_respond is False

    @pytest.mark.asyncio
    async def test_analyze_message_sentiment(self, analyzer):
        """Test message sentiment analysis."""
        positive_message = "I love this! It's amazing!"
        negative_message = "This is terrible and I hate it."
        neutral_message = "This is a regular message."
        
        # Note: This is a simplified test - real sentiment analysis would need actual implementation
        pos_sentiment = analyzer.analyze_sentiment(positive_message)
        neg_sentiment = analyzer.analyze_sentiment(negative_message)
        neu_sentiment = analyzer.analyze_sentiment(neutral_message)
        
        # Assuming sentiment analysis returns a score between -1 and 1
        assert isinstance(pos_sentiment, (int, float))
        assert isinstance(neg_sentiment, (int, float))
        assert isinstance(neu_sentiment, (int, float))