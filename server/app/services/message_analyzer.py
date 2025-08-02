"""
Class for analyzing messages and detecting keywords in group messages.
"""
from typing import Set, List, Dict, Any
from server.app.core.logging import logger
from server.app.services.ai_engine import analyze_message

class MessageAnalyzer:
    """
    Analyzes messages from groups to detect keywords and determine if an AI response is needed.
    """
    
    def __init__(self, keywords: Set[str] = None):
        """
        Initialize the message analyzer with a set of keywords to match.
        
        Args:
            keywords: Set of keywords to match in messages (case-insensitive)
        """
        self.keywords = keywords or set()
    
    def set_keywords(self, keywords: Set[str]):
        """
        Update the keywords set.
        
        Args:
            keywords: New set of keywords to match
        """
        self.keywords = keywords or set()
        logger.debug(f"Updated keywords: {self.keywords}")
    
    def detect_keywords(self, message_text: str) -> List[str]:
        """
        Detect if any keywords are present in the message text.
        
        Args:
            message_text: The text message to analyze
            
        Returns:
            List of matched keywords found in the message
        """
        if not message_text or not self.keywords:
            return []
            
        message_text_lower = message_text.lower()
        matched_keywords = [
            keyword for keyword in self.keywords 
            if keyword in message_text_lower
        ]
        
        return matched_keywords
    
    async def should_respond(self, message_text: str) -> Dict[str, Any]:
        """
        Determine if an AI response should be triggered based on keyword matching
        and message analysis.
        
        Args:
            message_text: The text message to analyze
            
        Returns:
            Dictionary with:
                - should_respond: Boolean indicating if AI should respond
                - matched_keywords: List of matched keywords
                - analysis: Message analysis results from AI engine
        """
        if not message_text:
            return {"should_respond": False, "matched_keywords": [], "analysis": None}
            
        # First check for keyword matches
        matched_keywords = self.detect_keywords(message_text)
        
        # Only analyze the message if we found keywords
        analysis = None
        if matched_keywords:
            try:
                analysis = await analyze_message(message_text)
            except Exception as e:
                logger.error(f"Error analyzing message: {e}")
                analysis = {
                    "sentiment": "neutral",
                    "category": "general_chat",
                    "urgency": False,
                    "summary": "Message analysis failed",
                    "keywords": matched_keywords
                }
        
        # Determine if we should respond based on matched keywords
        should_respond = len(matched_keywords) > 0
        
        return {
            "should_respond": should_respond,
            "matched_keywords": matched_keywords,
            "analysis": analysis
        }
