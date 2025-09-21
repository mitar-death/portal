import os
import random
import string
from enum import Enum
from datetime import datetime
import sqlalchemy as sa
from server.app.core.config import settings
from loguru import logger
import aiofiles
import json


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


async def write_message_to_file(message_data, message_type="unknown"):
    """
    Write message data to a file for persistence and analysis.

    Args:
        message_data: The message data to write
        message_type: The type of message (group, dm, etc.)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        logs_dir = os.path.join("storage", "logs", "messages")
        os.makedirs(logs_dir, exist_ok=True)

        # Generate filename based on date
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = os.path.join(logs_dir, f"{message_type}_{date_str}.jsonl")

        # Write the message data as a JSON line
        async with aiofiles.open(filename, "a") as f:
            # Add timestamp if not present
            if "timestamp" not in message_data:
                message_data["timestamp"] = datetime.now().isoformat()

            # Add message type
            message_data["message_type"] = message_type

            # Write as JSON line
            await f.write(json.dumps(message_data) + "\n")

        return True

    except Exception as e:
        logger.error(f"Error writing message to file: {e}")
        return False
