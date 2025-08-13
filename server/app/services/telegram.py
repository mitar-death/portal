import os
from telethon.sync import TelegramClient
from pathlib import Path
from server.app.core.config import settings
from teleredis import RedisSession
from server.app.services.redis_client import init_redis
from init_db import logger

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

def initialize_client():
    """Initialize the Telegram client with appropriate session storage"""
    global client
    
    # If client is already initialized, return
    if client is not None:
        return client
        
    try:
        # Always prefer Redis for consistent auth state
        logger.info("Initializing Telegram client with Redis session")
        redis_connection = init_redis(decode_responses=False)
        session_name = get_session_name()
        redis_session = RedisSession(session_name, redis_connection=redis_connection)
        
        client = TelegramClient(redis_session, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
        
        # Connect the client right away
        client.connect()
        logger.info(f"Telegram client initialized with Redis session: {session_name}")
        
    except Exception as e:
        logger.error(f"Failed to initialize Telegram client with Redis: {str(e)}")
        logger.info("Falling back to file-based session")
        
        client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
        client.connect()
        
    return client

def get_client():
    """
    Get the Telegram client instance.
    
    Returns:
        TelegramClient: The initialized Telegram client.
    """
    global client
    
    # Initialize client if not already done
    if client is None:
        client = initialize_client()
    
    # Ensure client is connected
    if not client.is_connected():
        client.connect()
        logger.info("Reconnected disconnected Telegram client")
    
    return client

def reset_client():
    """Force reinitialize the client - useful after logout"""
    global client
    
    # Disconnect existing client if any
    if client and client.is_connected():
        client.disconnect()
    
    client = None
    return initialize_client()