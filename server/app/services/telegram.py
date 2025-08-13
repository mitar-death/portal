import os
import asyncio
from telethon import TelegramClient
from pathlib import Path
from server.app.core.logging import logger
from server.app.core.config import settings
from teleredis import RedisSession
from server.app.services.redis_client import init_redis

# Use a user-specific session name format
def get_session_name():
    return f"tgportal_session"  # Keep a single consistent session

config_session_dir = settings.TELEGRAM_SESSION_FOLDER_DIR
config_session_name = settings.TELEGRAM_SESSION_NAME

session_dir = Path(os.path.expanduser(config_session_dir))
session_dir.mkdir(exist_ok=True)
session_path = str(session_dir / config_session_name)

# Global client variable
client = None
client_init_lock = asyncio.Lock()

async def initialize_client():
    """Initialize the Telegram client with appropriate session storage"""
    global client
    
    # Use a lock to prevent multiple initializations
    async with client_init_lock:
        # If client is already initialized, return
        if client is not None and client.is_connected():
            return client
            
        try:
            # Always prefer Redis for consistent auth state
            logger.info("Initializing Telegram client with Redis session")
            redis_connection = init_redis(decode_responses=False)
            session_name = get_session_name()
            redis_session = RedisSession(session_name, redis_connection=redis_connection)
            
            # Create new client instance
            new_client = TelegramClient(redis_session, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
            
            # Connect the client right away
            await new_client.connect()
            logger.info(f"Telegram client initialized with Redis session: {session_name}")
            
            # Set the global client variable
            client = new_client
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram client with Redis: {str(e)}")
            logger.info("Falling back to file-based session")
            
            # Create new client with file-based session
            new_client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
            await new_client.connect()
            
            # Set the global client variable
            client = new_client
            
        return client

async def get_client():
    """
    Get the Telegram client instance.
    
    Returns:
        TelegramClient: The initialized Telegram client.
    """
    global client
    
    # If client already exists but disconnected, reconnect
    if client is not None:
        if not client.is_connected():
            logger.info("Client disconnected, reconnecting")
            await client.connect()
        return client
            
    # Initialize the client if it doesn't exist
    return await initialize_client()

async def reset_client():
    """Force reinitialize the client - useful after logout"""
    global client
    
    # Disconnect existing client if any
    if client and client.is_connected():
        await client.disconnect()
    
    client = None
    return await initialize_client()