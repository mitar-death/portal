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
from server.app.services.redis_client import init_redis, is_redis_available
from typing import Dict, Optional
from threading import RLock

config_session_dir = settings.TELEGRAM_SESSION_FOLDER_DIR
config_session_name = settings.TELEGRAM_SESSION_NAME

# Global session directory
base_session_dir = Path(os.path.expanduser(config_session_dir))
base_session_dir.mkdir(exist_ok=True)

class ClientManager:
    """
    Thread-safe manager for user-specific Telegram clients.
    Handles session isolation and concurrent access for multiple users.
    """
    
    def __init__(self):
        self._clients: Dict[int, TelegramClient] = {}
        self._locks: Dict[int, asyncio.Lock] = {}
        self._global_lock = RLock()  # For thread safety when modifying dictionaries
        
    def _get_user_session_dir(self, user_id: int) -> Path:
        """Get user-specific session directory."""
        user_session_dir = base_session_dir / f"user_{user_id}"
        user_session_dir.mkdir(exist_ok=True)
        return user_session_dir
        
    def _get_user_session_path(self, user_id: int) -> str:
        """Get user-specific session file path."""
        user_session_dir = self._get_user_session_dir(user_id)
        return str(user_session_dir / "user_session")
        
    def _get_user_metadata_file(self, user_id: int) -> Path:
        """Get user-specific metadata file path."""
        user_session_dir = self._get_user_session_dir(user_id)
        return user_session_dir / "session_metadata.json"
        
    def _get_session_name_for_user(self, user_id: int) -> str:
        """
        Generate or retrieve a session name for a specific user.
        """
        metadata_file = self._get_user_metadata_file(user_id)
        
        # Check if we already have a stored session name for this user
        if metadata_file.exists():
            try:
                with open(metadata_file, "r") as f:
                    metadata = json.load(f)
                    if "session_name" in metadata:
                        logger.info(f"Using existing session name for user {user_id}: {metadata['session_name']}")
                        return metadata["session_name"]
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Error reading session metadata for user {user_id}: {e}")
        
        # Generate a new random session name
        chars = string.ascii_lowercase + string.digits
        random_id = ''.join(random.choice(chars) for _ in range(8))
        session_name = f"tgportal_user_{user_id}_{random_id}"
        
        # Store the session name for future use
        try:
            with open(metadata_file, "w") as f:
                json.dump({
                    "session_name": session_name,
                    "user_id": user_id,
                    "created_at": asyncio.get_event_loop().time(),
                    "user_info": {}
                }, f)
            logger.info(f"Generated and stored new session name for user {user_id}: {session_name}")
        except IOError as e:
            logger.error(f"Failed to save session metadata for user {user_id}: {e}")
        
        return session_name
        
    async def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Get or create an async lock for a specific user."""
        with self._global_lock:
            if user_id not in self._locks:
                self._locks[user_id] = asyncio.Lock()
            return self._locks[user_id]
            
    async def get_guest_client(self) -> TelegramClient:
        """
        Get a guest client for initial authentication (before user exists).
        This client is used for sending verification codes during login.
        
        Returns:
            TelegramClient: A temporary client for authentication
        """
        guest_session_path = str(base_session_dir / "guest_session")
        
        # Create a temporary client with a guest session
        guest_client = TelegramClient(guest_session_path, int(settings.TELEGRAM_API_ID), settings.TELEGRAM_API_HASH)
        await guest_client.connect()
        
        logger.info("Guest client created for initial authentication")
        return guest_client
            
    async def initialize_user_client(self, user_id: int, force_new_session: bool = False) -> TelegramClient:
        """
        Initialize a Telegram client for a specific user.
        
        Args:
            user_id: The user ID for which to create the client
            force_new_session: If True, creates a new session even if one exists
            
        Returns:
            TelegramClient: The initialized client for this user
        """
        user_lock = await self._get_user_lock(user_id)
        
        async with user_lock:
            # Check if client already exists and is connected (unless forcing new session)
            if (not force_new_session and 
                user_id in self._clients and 
                self._clients[user_id] is not None and 
                self._clients[user_id].is_connected()):
                return self._clients[user_id]
                
            # Disconnect existing client if any
            if user_id in self._clients and self._clients[user_id] is not None:
                try:
                    if self._clients[user_id].is_connected():
                        await self._clients[user_id].disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting old client for user {user_id}: {e}")
                    
            # Determine session type based on Redis availability
            use_redis = is_redis_available()
            
            try:
                if use_redis:
                    logger.info(f"Initializing Telegram client with Redis session for user {user_id}")
                    redis_connection = init_redis(decode_responses=False)
                    
                    if redis_connection is None:
                        logger.warning(f"Redis connection returned None for user {user_id}, falling back to file-based session")
                        use_redis = False
                    else:
                        # Check for transferred session string first
                        session_string = None
                        metadata_file = self._get_user_metadata_file(user_id)
                        if metadata_file.exists():
                            try:
                                with open(metadata_file, "r") as f:
                                    metadata = json.load(f)
                                    session_string = metadata.get("session_string")
                            except Exception as e:
                                logger.warning(f"Failed to read session metadata for user {user_id}: {e}")
                        
                        # If forcing new session, clear the old Redis session and metadata
                        if force_new_session:
                            session_name = self._get_session_name_for_user(user_id)
                            try:
                                redis_connection.delete(session_name)
                                logger.info(f"Cleared Redis session for user {user_id}: {session_name}")
                            except Exception as e:
                                logger.warning(f"Failed to clear Redis session for user {user_id}: {e}")
                            
                            if metadata_file.exists():
                                metadata_file.unlink()
                            logger.info(f"Forced new session for user {user_id}, cleared previous session metadata")
                            session_string = None  # Clear transferred session too
                        
                        # Get (or generate) a session name for this user
                        session_name = self._get_session_name_for_user(user_id)
                        
                        # Use StringSession if we have transferred session data
                        if session_string:
                            from telethon.sessions import StringSession
                            logger.info(f"Using transferred StringSession for user {user_id}")
                            session = StringSession(session_string)
                        else:
                            session = RedisSession(session_name, redis_connection=redis_connection)
                        
                        # Create new client instance
                        new_client = TelegramClient(session, int(settings.TELEGRAM_API_ID), settings.TELEGRAM_API_HASH)
                        
                        # Connect the client
                        await new_client.connect()
                        logger.info(f"Telegram client initialized with Redis session for user {user_id}: {session_name}")
                        
                        # Store the client
                        with self._global_lock:
                            self._clients[user_id] = new_client
                        
                        # Store user info when available
                        if await new_client.is_user_authorized():
                            try:
                                me = await new_client.get_me()
                                if me:
                                    self._update_user_session_metadata(user_id, {
                                        "telegram_user_id": me.id,
                                        "username": me.username,
                                        "phone": me.phone
                                    })
                            except Exception as e:
                                logger.warning(f"Failed to update user info in session metadata for user {user_id}: {e}")
                
                if not use_redis:
                    logger.info(f"Initializing Telegram client with StringSession/file-based session for user {user_id}")
                    
                    # Check for transferred session string first
                    session_string = None
                    metadata_file = self._get_user_metadata_file(user_id)
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, "r") as f:
                                metadata = json.load(f)
                                session_string = metadata.get("session_string")
                        except Exception as e:
                            logger.warning(f"Failed to read session metadata for user {user_id}: {e}")
                    
                    # If forcing new session, clear everything EXCEPT transferred session data
                    if force_new_session:
                        user_session_path = self._get_user_session_path(user_id)
                        if os.path.exists(user_session_path):
                            os.remove(user_session_path)
                            logger.info(f"Cleared file session for user {user_id}: {user_session_path}")
                        
                        # Only clear metadata if we don't have a transferred session
                        if not session_string and metadata_file.exists():
                            metadata_file.unlink()
                            logger.info(f"Forced new session for user {user_id}, cleared previous session metadata")
                        elif session_string:
                            logger.info(f"Keeping transferred session string for user {user_id} despite force_new_session=True")
                    
                    # Use StringSession if we have transferred session data
                    if session_string:
                        from telethon.sessions import StringSession
                        logger.info(f"Using transferred StringSession for user {user_id}")
                        session = StringSession(session_string)
                        new_client = TelegramClient(session, int(settings.TELEGRAM_API_ID), settings.TELEGRAM_API_HASH)
                    else:
                        # Fall back to file-based session
                        user_session_path = self._get_user_session_path(user_id)
                        new_client = TelegramClient(user_session_path, int(settings.TELEGRAM_API_ID), settings.TELEGRAM_API_HASH)
                    await new_client.connect()
                    logger.info(f"Telegram client initialized with file-based session for user {user_id}: {user_session_path}")
                    
                    # Store the client
                    with self._global_lock:
                        self._clients[user_id] = new_client
                    
                    # Store user info when available
                    if await new_client.is_user_authorized():
                        try:
                            me = await new_client.get_me()
                            if me:
                                self._update_user_session_metadata(user_id, {
                                    "telegram_user_id": me.id,
                                    "username": me.username,
                                    "phone": me.phone
                                })
                        except Exception as e:
                            logger.warning(f"Failed to update user info in session metadata for user {user_id}: {e}")
                
            except Exception as e:
                logger.error(f"Failed to initialize Telegram client for user {user_id}: {str(e)}")
                
                # Last resort: try file-based session if we haven't already
                if use_redis:
                    logger.info(f"Falling back to file-based session as last resort for user {user_id}")
                    try:
                        user_session_path = self._get_user_session_path(user_id)
                        new_client = TelegramClient(user_session_path, int(settings.TELEGRAM_API_ID), settings.TELEGRAM_API_HASH)
                        await new_client.connect()
                        with self._global_lock:
                            self._clients[user_id] = new_client
                        logger.info(f"Successfully fell back to file-based session for user {user_id}")
                    except Exception as fallback_error:
                        logger.error(f"Failed to fall back to file-based session for user {user_id}: {fallback_error}")
                        raise e  # Re-raise original error
                else:
                    raise e  # Re-raise if we were already trying file-based
                
            return self._clients[user_id]
            
    def _update_user_session_metadata(self, user_id: int, user_info=None):
        """
        Update the session metadata for a specific user.
        
        Args:
            user_id: The user ID
            user_info: User information to store
        """
        metadata_file = self._get_user_metadata_file(user_id)
        
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
                
            logger.debug(f"Updated session metadata for user {user_id}")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error updating session metadata for user {user_id}: {e}")
            
    async def get_user_client(self, user_id: int, new_session: bool = False) -> Optional[TelegramClient]:
        """
        Get the Telegram client for a specific user.
        
        Args:
            user_id: The user ID
            new_session: If True, creates a new session
            
        Returns:
            TelegramClient or None: The client for this user
        """
        # Force new session if requested
        if new_session:
            return await self.initialize_user_client(user_id, force_new_session=True)
        
        # Check if client exists
        with self._global_lock:
            if user_id not in self._clients or self._clients[user_id] is None:
                # Initialize the client if it doesn't exist
                return await self.initialize_user_client(user_id)
        
        client = self._clients[user_id]
        
        # If client exists but disconnected, reconnect
        if not client.is_connected():
            logger.info(f"Client disconnected for user {user_id}, reconnecting")
            await client.connect()
            
        # Update last used timestamp
        self._update_user_session_metadata(user_id)
        
        return client
        
    async def disconnect_user_client(self, user_id: int) -> bool:
        """
        Disconnect and remove the client for a specific user.
        
        Args:
            user_id: The user ID
            
        Returns:
            bool: True if disconnection was successful
        """
        user_lock = await self._get_user_lock(user_id)
        
        async with user_lock:
            try:
                with self._global_lock:
                    if user_id in self._clients and self._clients[user_id] is not None:
                        client = self._clients[user_id]
                        
                        if client.is_connected():
                            await client.disconnect()
                            logger.info(f"Disconnected Telegram client for user {user_id}")
                            
                        # Remove from clients dict
                        del self._clients[user_id]
                        
                        # Remove lock as well
                        if user_id in self._locks:
                            del self._locks[user_id]
                            
                return True
                
            except Exception as e:
                logger.error(f"Error disconnecting client for user {user_id}: {e}")
                return False
                
    async def cleanup_user_session(self, user_id: int) -> bool:
        """
        Clean up all session data for a specific user.
        
        Args:
            user_id: The user ID
            
        Returns:
            bool: True if cleanup was successful
        """
        try:
            # First disconnect the client
            await self.disconnect_user_client(user_id)
            
            # Clean up session files
            user_session_dir = self._get_user_session_dir(user_id)
            user_session_path = self._get_user_session_path(user_id)
            metadata_file = self._get_user_metadata_file(user_id)
            
            # Remove session file
            if os.path.exists(user_session_path):
                os.remove(user_session_path)
                logger.info(f"Deleted session file for user {user_id}: {user_session_path}")
                
            # Remove metadata file
            if metadata_file.exists():
                metadata_file.unlink()
                logger.info(f"Deleted session metadata for user {user_id}: {metadata_file}")
                
            # Clean up Redis session if available
            try:
                session_name = f"tgportal_user_{user_id}_*"  # Pattern matching
                redis_connection = init_redis(decode_responses=False)
                if redis_connection:
                    # Get all keys matching the pattern
                    keys = redis_connection.keys(f"tgportal_user_{user_id}_*")
                    if keys:
                        redis_connection.delete(*keys)
                        logger.info(f"Cleared {len(keys)} Redis session(s) for user {user_id}")
            except Exception as e:
                logger.warning(f"Error clearing Redis sessions for user {user_id}: {e}")
                
            # Remove empty user directory if it exists
            try:
                if user_session_dir.exists() and not any(user_session_dir.iterdir()):
                    user_session_dir.rmdir()
                    logger.info(f"Removed empty session directory for user {user_id}")
            except Exception as e:
                logger.warning(f"Could not remove session directory for user {user_id}: {e}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up session for user {user_id}: {e}")
            return False
            
    async def get_all_connected_users(self) -> Dict[int, bool]:
        """
        Get the connection status of all users.
        
        Returns:
            Dict[int, bool]: Mapping of user_id to connection status
        """
        status = {}
        with self._global_lock:
            for user_id, client in self._clients.items():
                if client:
                    status[user_id] = client.is_connected()
                else:
                    status[user_id] = False
        return status
        
    async def disconnect_all_clients(self):
        """Disconnect all clients (used for cleanup)."""
        with self._global_lock:
            user_ids = list(self._clients.keys())
            
        for user_id in user_ids:
            try:
                await self.disconnect_user_client(user_id)
            except Exception as e:
                logger.error(f"Error disconnecting client for user {user_id}: {e}")


# Global client manager instance
client_manager = ClientManager()

# Legacy compatibility functions removed - use client_manager directly
# All client operations now require explicit user context via request parameters


async def transfer_session_to_user(guest_client, user_id: int):
    """
    Transfer the authenticated session from guest client to user-specific client.
    Uses StringSession export/import instead of file copying to prevent SQLite corruption.
    
    Args:
        guest_client: The authenticated guest TelegramClient
        user_id: The user ID to transfer the session to
    """
    from telethon.sessions import StringSession
    
    try:
        # Export the guest session as a string
        if not await guest_client.is_user_authorized():
            logger.warning(f"Guest client is not authorized, cannot transfer session to user {user_id}")
            return False
            
        # Export session string from guest client using StringSession format
        try:
            from telethon.sessions import StringSession
            # Convert the guest client's session to StringSession format
            session_string = StringSession.save(guest_client.session)
            if not session_string:
                # Fallback: Try to extract auth key directly
                if hasattr(guest_client.session, 'auth_key') and guest_client.session.auth_key:
                    # Create a temporary StringSession with auth key data
                    temp_string_session = StringSession()
                    temp_string_session.set_dc(
                        guest_client.session.dc_id, 
                        guest_client.session.server_address, 
                        guest_client.session.port
                    )
                    temp_string_session.auth_key = guest_client.session.auth_key
                    session_string = temp_string_session.save()
                    logger.info(f"Used fallback method to export session for user {user_id}")
                
            if not session_string:
                logger.warning(f"Failed to export session string from guest client for user {user_id}")
                return False
        except Exception as export_error:
            logger.error(f"Error during session export for user {user_id}: {export_error}")
            return False
            
        logger.info(f"Successfully exported session string from guest client for user {user_id}")
        
        # Determine session type for user client
        use_redis = is_redis_available()
        
        if use_redis:
            # Store session string in Redis
            try:
                redis_connection = init_redis(decode_responses=False)
                if redis_connection:
                    user_session_name = client_manager._get_session_name_for_user(user_id)
                    
                    # Create a StringSession and save it to Redis format
                    string_session = StringSession(session_string)
                    redis_session = RedisSession(user_session_name, redis_connection=redis_connection)
                    
                    # Transfer session data to Redis using RedisSession directly
                    string_session_obj = StringSession(session_string)
                    redis_session.set_dc(string_session_obj.dc_id, string_session_obj.server_address, string_session_obj.port)
                    redis_session.auth_key = string_session_obj.auth_key
                    await redis_session.save()
                    
                    logger.info(f"Transferred session to Redis for user {user_id}: {user_session_name}")
                else:
                    logger.warning("Redis connection failed during session transfer")
                    use_redis = False
            except Exception as e:
                logger.warning(f"Redis session transfer failed: {e}, falling back to StringSession storage")
                use_redis = False
        
        if not use_redis:
            # Store session string in metadata for file-based fallback
            try:
                metadata_file = client_manager._get_user_metadata_file(user_id)
                metadata = {}
                
                if metadata_file.exists():
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)
                
                metadata.update({
                    "session_string": session_string,
                    "transferred_at": asyncio.get_event_loop().time(),
                    "user_id": user_id
                })
                
                with open(metadata_file, "w") as f:
                    json.dump(metadata, f)
                    
                logger.info(f"Stored session string in metadata for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to store session string for user {user_id}: {e}")
                return False
        
        # CRITICAL: Initialize user client with transferred session to ensure immediate authorization
        try:
            user_client = await client_manager.initialize_user_client(user_id, force_new_session=True)
            if user_client:
                # Verify the transferred session is working
                if await user_client.is_user_authorized():
                    logger.info(f"Successfully verified transferred session authorization for user {user_id}")
                    return True
                else:
                    logger.warning(f"Transferred session for user {user_id} is not authorized - may need manual re-login")
                    return False
            else:
                logger.warning(f"Failed to initialize user client after session transfer for user {user_id}")
                return False
        except Exception as e:
            logger.warning(f"Failed to verify transferred session for user {user_id}: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Session transfer failed for user {user_id}: {e}")
        return False


# Backward compatibility exports for session paths
session_dir = base_session_dir  # For backward compatibility
session_path = str(base_session_dir / config_session_name)  # For backward compatibility 
metadata_file = base_session_dir / "session_metadata.json"  # For backward compatibility