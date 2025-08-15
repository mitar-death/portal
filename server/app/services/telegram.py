import os
import asyncio
import random
import string
import json
from telethon import TelegramClient
from pathlib import Path
from server.app.core.logging import logger
from server.app.core.config import settings
from teleredis import RedisSession
from server.app.services.redis_client import init_redis

config_session_dir = settings.TELEGRAM_SESSION_FOLDER_DIR
config_session_name = settings.TELEGRAM_SESSION_NAME

session_dir = Path(os.path.expanduser(config_session_dir))
session_dir.mkdir(exist_ok=True)
session_path = str(session_dir / config_session_name)

# Global client variable
client: TelegramClient = None
client_init_lock = asyncio.Lock()
metadata_file = session_dir / "session_metadata.json"

# Generate and remember session names
def get_session_name():
    """
    Generate a random session name if one doesn't exist, 
    or retrieve the previously generated one.
    
    The session name is stored in a JSON file in the session folder
    for persistence across application restarts.
    
    Returns:
        str: The session name to use
    """
    # Generate a new random session name
    chars = string.ascii_lowercase + string.digits
    random_id = ''.join(random.choice(chars) for _ in range(8))
    session_name = f"tgportal_session_{random_id}"
    
    # Check if we already have a stored session name
    if metadata_file.exists():
        try:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
                if "session_name" in metadata:
                    logger.info(f"Using existing session name: {metadata['session_name']}")
                    return metadata["session_name"]
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error reading session metadata: {e}")
    
  
    # Store the session name for future use
    try:
        with open(metadata_file, "w") as f:
            json.dump({
                "session_name": session_name,
                "created_at": asyncio.get_event_loop().time(),
                "user_info": {}  # Can store additional user info once logged in
            }, f)
        logger.info(f"Generated and stored new session name: {session_name}")
    except IOError as e:
        logger.error(f"Failed to save session metadata: {e}")
    
    return session_name


async def initialize_client(force_new_session=False):
    """
    Initialize the Telegram client with appropriate session storage
    
    Args:
        force_new_session (bool): If True, generates a new session
                                 regardless of existing session
    """
    global client

    # Use a lock to prevent multiple initializations
    async with client_init_lock:
        # If client is already initialized and we don't want a new session, return
        if client is not None and client.is_connected() and not force_new_session:
            return client
            
        try:
            # Always prefer Redis for consistent auth state
            logger.info("Initializing Telegram client with Redis session")
            redis_connection = init_redis(decode_responses=False)
            
            # If forcing new session, clear the old metadata first
            if force_new_session:
                metadata_file = Path(os.path.expanduser(config_session_dir)) / "session_metadata.json"
                if metadata_file.exists():
                    metadata_file.unlink()
                logger.info("Forced new session, cleared previous session metadata")
            
            # Get (or generate) a session name
            session_name = get_session_name()
            redis_session = RedisSession(session_name, redis_connection=redis_connection)
            
            # Create new client instance
            new_client = TelegramClient(redis_session, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
            
            # Connect the client right away
            await new_client.connect()
            logger.info(f"Telegram client initialized with Redis session: {session_name}")
            
            # Set the global client variable
            client = new_client
            
            # Store user info when available
            if await new_client.is_user_authorized():
                try:
                    me = await new_client.get_me()
                    if me:
                        update_session_metadata({
                            "user_id": me.id,
                            "username": me.username,
                            "phone": me.phone
                        })
                except Exception as e:
                    logger.warning(f"Failed to update user info in session metadata: {e}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram client with Redis: {str(e)}")
            logger.info("Falling back to file-based session")
            
            # Create new client with file-based session
            new_client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
            await new_client.connect()
            
            # Set the global client variable
            client = new_client
            
        return client

def update_session_metadata(user_info=None):
    """
    Update the session metadata with additional information
    
    Args:
        user_info (dict, optional): User information to store
    """
    session_dir = Path(os.path.expanduser(settings.TELEGRAM_SESSION_FOLDER_DIR))
    metadata_file = session_dir / "session_metadata.json"
    
    if not metadata_file.exists():
        return
        
    try:
        with open(metadata_file, "r") as f:
            metadata = json.load(f)
            
        if user_info:
            metadata["user_info"] = user_info
            
        metadata["last_used"] = asyncio.get_event_loop().time()
            
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)
            
        logger.debug("Updated session metadata")
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error updating session metadata: {e}")

async def get_client(new_session=False):
    """
    Get the Telegram client instance.
    
    Args:
        new_session (bool): If True, creates a new random session
    
    Returns:
        TelegramClient: The initialized Telegram client.
    """
    global client
    
    # Force new session if requested
    if new_session:
        return await initialize_client(force_new_session=True)
    
    # If client already exists but disconnected, reconnect
    if client is not None:
        if not client.is_connected():
            logger.info("Client disconnected, reconnecting")
            await client.connect()
            
        # Update last used timestamp
        update_session_metadata()
        
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
    return await initialize_client(force_new_session=True)