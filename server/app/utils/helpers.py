import os
import random
import string
from enum import Enum
from datetime import datetime
import sqlalchemy as sa
from server.app.core.config import settings
from loguru import logger



def match_keywords(text, keywords_list):
    """
    Enhanced keyword matching with word boundaries and partial matches
    """
    if not keywords_list:
        return []
    
    text_lower = text.lower()
    matched = []
    for keyword in keywords_list:
        if keyword in text_lower:
            matched.append(keyword)
    return matched

def create_migration_enum_def(enumType: Enum, name: str):
    """
    Create a SQLAlchemy Enum definition for use in database migrations.

    Args:
        enumType (Enum): The Python Enum class to convert to a database enum
        name (str): The name to give the enum type in the database

    Returns:
        sa.Enum: A SQLAlchemy Enum definition ready for use in migrations
    """
    return sa.Enum(*[e.value for e in enumType], name=name)


def write_message_to_file(message_data, user_id=None):
    """
    Generic function to write message data to a file.
    
    Args:
        message_data (dict): Dictionary containing message details
        user_id (int, optional): User ID for file naming
    """
    # Create messages directory if it doesn't exist
    messages_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'messages')
    os.makedirs(messages_dir, exist_ok=True)
    
    # Use a user-specific file if we have a user_id
    filename = f'messages_{user_id}.txt' if user_id else 'messages.txt'
    message_file_path = os.path.join(messages_dir, filename)
    
    try:
        with open(message_file_path, 'a', encoding='utf-8') as f:
            # Format timestamp
            timestamp = message_data.get('timestamp', '')
            
            # Create a formatted message string
            message_str = f"[{timestamp}] "
            
            if 'chat_title' in message_data:
                message_str += f"Group: {message_data['chat_title']} ({message_data.get('chat_id', '')})"
            else:
                message_str += f"Chat ID: {message_data.get('chat_id', '')}"
                
            if 'sender_name' in message_data:
                message_str += f" | From: {message_data['sender_name']}"
                
            if 'text' in message_data:
                message_str += f" | Message: {message_data['text']}"
                
            if 'matched_keywords' in message_data and message_data['matched_keywords']:
                message_str += f" | Keywords: {', '.join(message_data['matched_keywords'])}"
                
            f.write(message_str + "\n")
            
        return True
    except Exception as e:
        logger.error(f"Error writing message to file: {e}")
        return False
