"""
Class for managing conversations with users in direct messages.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from server.app.core.logging import logger


class ConversationManager:
    """
    Manages AI conversations with users in direct messages,
    including conversation history and tracking.
    """

    def __init__(self):
        """Initialize an empty conversation manager."""
        # Structure: {user_id: {
        #   "history": [{role, content, timestamp}],
        #   "last_message": datetime,
        #   "ai_account_id": int
        # }}
        self.conversations = {}
        self.dm_errors = {}  # Track DM errors by user_id

    def get_or_create_conversation(
        self, user_id: int, ai_account_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get an existing conversation or create a new one if it doesn't exist.

        Args:
            user_id: The user's Telegram ID
            ai_account_id: The AI account ID to use for this conversation

        Returns:
            List of conversation history messages
        """
        user_id_str = str(user_id)

        if user_id_str not in self.conversations:
            self.conversations[user_id_str] = {
                "history": [],
                "last_message": datetime.now(),
                "ai_account_id": ai_account_id,
            }
            logger.debug(
                f"Created new conversation for user {user_id} with AI account {ai_account_id}"
            )

        return self.conversations[user_id_str]["history"]

    def get_all_conversations(self):
        """
        Get all conversations currently being tracked, formatted for diagnostics.

        Returns:
            dict: Dictionary of all conversations, keyed by composite ID
        """
        result = {}

        # Convert conversations to the format expected by DiagnosticsView
        for user_id, data in self.conversations.items():
            # Skip conversations with no AI account
            if "ai_account_id" not in data:
                continue

            ai_account_id = data["ai_account_id"]

            # Create a composite key for this conversation
            conversation_id = f"{user_id}-{ai_account_id}"

            # Format the conversation data
            conversation = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "ai_account_id": ai_account_id,
                "user_name": data.get("user_name", f"User {user_id}"),
                "history": data.get("history", []),
                "start_time": data.get("start_time", datetime.now().isoformat()),
                "last_message_time": (
                    data.get("last_message", datetime.now()).isoformat()
                    if isinstance(data.get("last_message"), datetime)
                    else data.get("last_message")
                ),
                "message_count": len(data.get("history", [])),
                "status": "active",
                "chat_type": data.get("chat_type", "direct"),
            }

            result[conversation_id] = conversation

        return result

    def add_user_message(
        self,
        user_id,
        message_text,
        ai_account_id=None,
        sender_name=None,
        chat_type="direct",
        group_id=None,
        group_name=None,
    ):
        """
        Add a user message to a conversation.

        Args:
            user_id: User ID
            message_text: The message text
            ai_account_id: AI account ID
            sender_name: Optional sender name for display
            chat_type: Type of chat ("direct" or "group")
            group_id: Optional group ID if from a group
            group_name: Optional group name if from a group
        """
        user_id_str = str(user_id)

        # Initialize conversation if it doesn't exist
        if user_id_str not in self.conversations:
            self.conversations[user_id_str] = {
                "ai_account_id": ai_account_id,
                "history": [],
                "user_name": sender_name or f"User {user_id}",
                "start_time": datetime.now(),
                "last_message": datetime.now(),
                "chat_type": chat_type,
                "dm_errors": {},
            }

            # Add group info if available
            if chat_type == "group" and group_id:
                self.conversations[user_id_str]["group_id"] = group_id
                self.conversations[user_id_str]["group_name"] = group_name
        elif ai_account_id is not None:
            # Update AI account ID if provided
            self.conversations[user_id_str]["ai_account_id"] = ai_account_id

        # Update sender name if provided
        if sender_name:
            self.conversations[user_id_str]["user_name"] = sender_name

        # Add message to history
        message = {
            "role": "user",
            "content": message_text,
            "timestamp": datetime.now().isoformat(),
            "is_ai_message": False,
        }

        # Add group info to message if from a group
        if chat_type == "group" and group_id:
            message["from_group"] = True
            message["group_id"] = group_id
            message["group_name"] = group_name

            # Also update conversation chat_type
            self.conversations[user_id_str]["chat_type"] = "group"
            self.conversations[user_id_str]["group_id"] = group_id
            self.conversations[user_id_str]["group_name"] = group_name

        self.conversations[user_id_str]["history"].append(message)
        self.conversations[user_id_str]["last_message"] = datetime.now()

    def add_assistant_message(
        self, user_id: int, message_text: str, ai_account_id: int = None
    ) -> None:
        """
        Add an AI assistant message to the conversation history.

        Args:
            user_id: The user's Telegram ID
            message_text: The message content
            ai_account_id: Optional AI account ID (for compatibility with MessengerAI)
        """
        user_id_str = str(user_id)

        if user_id_str not in self.conversations:
            logger.warning(
                f"Trying to add assistant message to non-existent conversation for user {user_id}"
            )
            return

        self.conversations[user_id_str]["history"].append(
            {
                "role": "assistant",
                "content": message_text,
                "timestamp": datetime.now().isoformat(),
            }
        )

        self.conversations[user_id_str]["last_message"] = datetime.now()

    def add_ai_response(
        self, sender_id: int, ai_account_id: int, response_text: str
    ) -> bool:
        """
        Add an AI response to the conversation history.
        This is an alias for add_assistant_message for compatibility with MessengerAI.

        Args:
            sender_id: The user's Telegram ID
            ai_account_id: The AI account ID
            response_text: The AI response content

        Returns:
            True if added successfully
        """
        try:
            self.add_assistant_message(sender_id, response_text, ai_account_id)
            return True
        except Exception as e:
            logger.error(f"Error adding AI response to conversation: {e}")
            return False

    def get_conversation_history(self, user_id, ai_account_id=None):
        """
        Get conversation history for a user and specific AI account.

        Args:
            user_id: The user's ID
            ai_account_id: The AI account's ID (optional)

        Returns:
            list: List of message objects in the conversation
        """
        user_id_str = str(user_id)

        if user_id_str not in self.conversations:
            return []

        conversation = self.conversations[user_id_str]

        # If ai_account_id is provided, verify it matches
        if (
            ai_account_id is not None
            and conversation.get("ai_account_id") != ai_account_id
        ):
            return []

        return conversation.get("history", [])

    def get_ai_account_for_user(self, user_id: int) -> Optional[int]:
        """
        Get the AI account ID associated with a user's conversation.

        Args:
            user_id: The user's Telegram ID

        Returns:
            AI account ID or None if no conversation exists
        """
        user_id_str = str(user_id)

        if user_id_str not in self.conversations:
            return None

        return self.conversations[user_id_str]["ai_account_id"]

    def is_new_conversation(self, user_id: int, ai_account_id: int = None) -> bool:
        """
        Check if this is a new conversation with the user.

        Args:
            user_id: The user's Telegram ID
            ai_account_id: Optional AI account ID (for compatibility with MessengerAI)

        Returns:
            True if this is a new conversation, False otherwise
        """
        user_id_str = str(user_id)

        if user_id_str not in self.conversations:
            return True

        return len(self.conversations[user_id_str]["history"]) == 0

    def clean_old_conversations(self, hours: int = 24) -> int:
        """
        Remove conversations older than the specified hours.

        Args:
            hours: Number of hours of inactivity before removing a conversation

        Returns:
            Number of conversations removed
        """
        current_time = datetime.now()
        keys_to_remove = []

        for user_id, data in self.conversations.items():
            last_message_time = data["last_message"]
            if (current_time - last_message_time) > timedelta(hours=hours):
                keys_to_remove.append(user_id)

        for key in keys_to_remove:
            del self.conversations[key]

        if keys_to_remove:
            logger.info(f"Cleaned up {len(keys_to_remove)} old conversations")

        return len(keys_to_remove)

    def record_dm_error(self, user_id: int, error_type: str) -> None:
        """
        Record an error that occurred when trying to send a DM to a user.

        Args:
            user_id: The user's Telegram ID
            error_type: The type of error that occurred
        """
        user_id_str = str(user_id)

        if user_id_str not in self.dm_errors:
            self.dm_errors[user_id_str] = {"count": 0, "last_error": None, "types": {}}

        self.dm_errors[user_id_str]["count"] += 1
        self.dm_errors[user_id_str]["last_error"] = datetime.now()

        if error_type not in self.dm_errors[user_id_str]["types"]:
            self.dm_errors[user_id_str]["types"][error_type] = 0

        self.dm_errors[user_id_str]["types"][error_type] += 1

        logger.warning(
            f"DM error to user {user_id}: {error_type} "
            + f"(total: {self.dm_errors[user_id_str]['count']})"
        )

    def can_send_dm(self, user_id: int) -> bool:
        """
        Check if we can attempt to send a DM to this user based on past errors.
        Implements backoff for users with repeated errors.

        Args:
            user_id: The user's Telegram ID

        Returns:
            True if we should attempt to send a DM, False otherwise
        """
        user_id_str = str(user_id)

        if user_id_str not in self.dm_errors:
            return True

        error_count = self.dm_errors[user_id_str]["count"]
        last_error = self.dm_errors[user_id_str]["last_error"]

        # Implement exponential backoff
        # For 1 error, wait 5 minutes
        # For 2 errors, wait 30 minutes
        # For 3+ errors, wait 3 hours
        if error_count == 1 and datetime.now() - last_error > timedelta(minutes=5):
            return True
        elif error_count == 2 and datetime.now() - last_error > timedelta(minutes=30):
            return True
        elif error_count >= 3 and datetime.now() - last_error > timedelta(hours=3):
            return True
        elif error_count >= 10:  # Too many errors, stop trying
            return False

        return False

    def clear_all(self, user_id: Optional[int] = None) -> None:
        """
        Clear all conversations or a specific user's conversations.

        Args:
            user_id: Optional user ID to clear only that user's conversation
        """
        if user_id is not None:
            user_id_str = str(user_id)
            if user_id_str in self.conversations:
                del self.conversations[user_id_str]
                logger.info(f"Cleared conversation for user {user_id}")
        else:
            self.conversations.clear()
            logger.info("Cleared all conversations")
            self.dm_errors.clear()
            logger.info("Cleared all DM errors")
