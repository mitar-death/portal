import asyncio
import os
import psutil
from telethon import events
from server.app.services.telegram import get_client
from server.app.core.logging import logger
from server.app.utils.helpers import write_message_to_file
from server.app.services.messenger_ai import MessengerAI
from server.app.services.messenger_ai import initialize_messenger_ai, get_messenger_ai
from server.app.utils.db_helpers import get_user_keywords, get_user_selected_groups
from server.app.models.models import SelectedGroup
from sqlalchemy import select
from server.app.services.messenger_ai import get_messenger_ai
from server.app.services.websocket_manager import websocket_manager
from datetime import datetime, timedelta
from collections import deque

# Add a new class to track recent errors
class ErrorTracker:
    def __init__(self, max_errors=20):
        self.recent_errors = deque(maxlen=max_errors)
        
    def add_error(self, message, details=None):
        self.recent_errors.append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "details": details
        })
        
    def get_recent_errors(self):
        return list(self.recent_errors)
    
# Create a singleton instance
error_tracker = ErrorTracker()


# Global variables
client = get_client()
monitoring_task = None
active_user_id = None  # Initialize to None, will be set during authentication
monitored_group_ids = set()  # Store group IDs to filter messages
keywords = set()  # Store keywords to filter messages
messenger_ai = None  # MessengerAI instance


async def set_active_user_id(user_id):
    """
    Set the active user ID for monitoring.
    This function is called by the AuthMiddleware when a user is authenticated.
    
    Args:
        user_id: The ID of the authenticated user.
    """
    global active_user_id
    
    # Ensure user_id is properly converted to integer
    try:
        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)
        elif not isinstance(user_id, int):
            logger.warning(f"Invalid user_id type: {type(user_id)}. Value: {user_id}")
    except Exception as e:
        logger.error(f"Error converting user_id to int: {e}. Original value: {user_id}")
    
    if active_user_id != user_id:
        logger.info(f"Setting active user ID from {active_user_id} to {user_id}")
        active_user_id = user_id
        
        # Reload user-specific data
        await load_user_keywords(user_id)
        
        # Reload monitored groups
        monitored_ids = await get_user_selected_groups(user_id)
        if monitored_ids:
            global monitored_group_ids
            monitored_group_ids = monitored_ids
            logger.info(f"Updated monitored groups for user {user_id}: {monitored_group_ids}")
            
        # Reinitialize AI if needed
        await ensure_messenger_ai_initialized()
    return active_user_id


async def ensure_messenger_ai_initialized():
    """
    Ensure that the messenger_ai is properly initialized for the current active user.
    """
    global messenger_ai, active_user_id
    
    if not active_user_id:
        logger.warning("Cannot initialize messenger_ai: No active user ID set")
        return False
        
    # Check if messenger_ai is already initialized
    if messenger_ai is not None:
        logger.debug(f"MessengerAI already initialized for user {active_user_id}")
        return True
        
    # Initialize MessengerAI for this user
    
    try:
        ai_initialized = await initialize_messenger_ai(active_user_id)
        if ai_initialized:
            messenger_ai = await get_messenger_ai()
            logger.info(f"MessengerAI initialized for user {active_user_id}")
            return True
        else:
            logger.warning(f"Failed to initialize MessengerAI for user {active_user_id}")
            return False
    except Exception as e:
        logger.error(f"Error initializing MessengerAI: {e}")
        error_tracker.add_error("Failed to initialize MessengerAI", str(e))
        return False


async def load_user_keywords(user_id):
    """
    Load keywords from the database for the specified user.
    
    Args:
        user_id: The ID of the user whose keywords to load.
    """
    global keywords
    keywords = await get_user_keywords(user_id)
    if keywords:
        logger.info(f"Loaded {len(keywords)} keywords for user {user_id}: {keywords}")
    else:
        logger.info(f"No keywords found for user {user_id}")
        keywords = set()


@client.on(events.NewMessage(incoming=True))
async def handle_new_message(event):
    """
    Handle incoming messages.
    This function will be called whenever a new message is received.
    Messages can come from either groups or direct messages.
    """
    global active_user_id, monitored_group_ids, keywords, messenger_ai
    try:
        message = event.message
        chat_id = str(message.chat_id)  # Convert to string for comparison
        
        # If no active user is set, we can't process messages
        if not active_user_id:
            logger.warning(f"No active user ID set, cannot process messages. Current ID: {active_user_id}")
            return
            
        # Skip if message has no text
        if not hasattr(message, 'text') or not message.text:
            return
            
        # Check if this group is being monitored
        if monitored_group_ids and chat_id not in monitored_group_ids:
            logger.debug(f"Skipping message from unmonitored group: {chat_id}")
            return
            
        # Try to get chat info
        chat_title = None
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', None)
        except Exception as e:
            logger.error(f"Error getting chat info: {e}")
            
        # Try to get sender info
        sender_name = None
        sender_id = None
        try:
            sender = await event.get_sender()
            first_name = getattr(sender, 'first_name', '')
            last_name = getattr(sender, 'last_name', '')
            sender_name = f"{first_name} {last_name}".strip() or f"User {sender.id}"
            sender_id = sender.id  # Store the sender's ID for conversation tracking
        except Exception as e:
            logger.error(f"Error getting sender info: {e}")
            sender_name = f"Unknown"
            
        # Determine if this is a group message or a direct message
        is_group_message = bool(chat_title)  # Groups have titles, DMs don't
        
        # For group messages, we need to check if it's a monitored group
        if is_group_message:
            # Initialize monitored groups if not already done
            if not monitored_group_ids:
                monitored_group_ids = await get_user_selected_groups(active_user_id)
                logger.info(f"Initialized monitored groups for user {active_user_id}: {monitored_group_ids}")
                
            # Handle the Telegram ID format difference
            # Telegram sends negative IDs for groups/channels with the format -100{group_id}
            short_chat_id = chat_id.replace('-100', '')
            
            # Skip if not a monitored group
            if chat_id not in monitored_group_ids and short_chat_id not in monitored_group_ids:
                logger.debug(f"Message from group {chat_id} not in monitored groups, skipping")
                return
        else:
            # This is a direct message - we should handle it if we have an active AI conversation
            # No need to check for keywords in DMs, as they will be handled by the MessengerAI component
            logger.debug(f"Received direct message from {sender_name} (ID: {sender_id})")
        
        # Log basic info
        logger.info(f"New message received: {message.id} in {chat_id}")
        
        # Prepare message data dictionary
        message_data = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'message_id': message.id,
            'chat_id': chat_id,
            'chat_title': chat_title,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'text': message.text
        }
        
        # Ensure active_user_id is set and valid
        if not active_user_id or not isinstance(active_user_id, int) or active_user_id <= 0:
            logger.error(f"Invalid active_user_id: {active_user_id}. Cannot initialize MessengerAI.")
            return
            
        # Initialize messenger_ai if needed
        if not messenger_ai:
            logger.info(f"Initializing MessengerAI with user_id: {active_user_id}")
            messenger_ai = MessengerAI()
            ai_initialized = await messenger_ai.initialize(active_user_id)
            if not ai_initialized:
                logger.error(f"Failed to initialize MessengerAI with user_id: {active_user_id}")
                messenger_ai = None
                return
                
        # Ensure we have keywords loaded
        if not keywords and active_user_id:
            await load_user_keywords(active_user_id)
            
        # If this is a group message, we only write to file if it contains keywords
        # If this is a DM, we always handle it
        if is_group_message:
            # Check if message contains any keywords
            message_text_lower = message.text.lower()
            matched_keywords = [keyword for keyword in keywords if keyword in message_text_lower]
            
            # Add matched keywords to the message data
            message_data['matched_keywords'] = matched_keywords
            
            # Only record group messages that contain keywords
            if matched_keywords or not keywords:
                write_message_to_file(message_data, active_user_id)
        else:
            # Always record DMs
            write_message_to_file(message_data, active_user_id)
            
        # Send the message to the WebSocket manager for real-time monitoring
        try:
            # Add additional contextual information to the message data
            websocket_message = message_data.copy()
            websocket_message.update({
                "is_group_message": is_group_message,
                "matched_keywords": message_data.get('matched_keywords', []),
                "monitored": True,
                "processed_time": datetime.now().isoformat()
            })
            
            # Send to WebSocket clients
            asyncio.create_task(websocket_manager.add_chat_message(websocket_message))
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            
        # Always send the message to MessengerAI for processing
        # The MessengerAI component will decide whether to respond based on:
        # - For group messages: only if they contain keywords
        # - For DMs: always, to continue conversations
        if messenger_ai:
            logger.debug(f"Sending message to MessengerAI for processing")
            asyncio.create_task(messenger_ai.handle_message(message_data))
        else:
            logger.warning(f"MessengerAI not initialized, cannot process message")
            # Try to reinitialize
            await ensure_messenger_ai_initialized()
            if messenger_ai:
                asyncio.create_task(messenger_ai.handle_message(message_data))
                
    except Exception as e:
        logger.error(f"Error in handle_new_message: {e}")


async def _run_client():
    """
    Internal function to run the client until disconnected.
    Also sets up a periodic health check for the messenger_ai.
    """
    logger.info("Starting Telegram client event loop")
    
    # Start a background task to periodically check messenger_ai health
    health_check_task = asyncio.create_task(_periodic_health_check())
    
    try:
        await client.run_until_disconnected()
    finally:
        # Cancel the health check task when the client disconnects
        if health_check_task and not health_check_task.done():
            health_check_task.cancel()
            try:
                await health_check_task
            except asyncio.CancelledError:
                pass



async def start_monitoring(user_id=None):
    """
    Start monitoring for new messages.
    This function will be called to initiate the message monitoring process.
    """
    global monitoring_task, active_user_id, monitored_group_ids, messenger_ai
    
    # Validate and set the active user ID
    if user_id is not None:
        if not isinstance(user_id, int) or user_id <= 0:
            logger.error(f"Invalid user_id provided to start_monitoring: {user_id}")
            return False
        await set_active_user_id(user_id)
        logger.info(f"Active user ID set to {active_user_id} in start_monitoring")
    elif active_user_id is None:
        logger.warning("No user_id provided and no active_user_id set. Monitoring will wait for user authentication.")
    
    if active_user_id:
        # Initialize AI and load user data using the helper function
        await ensure_messenger_ai_initialized()
        
        # Fetch selected groups for the user if we don't have them yet
        if not monitored_group_ids:
            monitored_group_ids = await get_user_selected_groups(active_user_id)
            if not monitored_group_ids:
                logger.warning(f"No selected groups found for user {active_user_id}. No messages will be monitored.")
            else:
                logger.info(f"Found {len(monitored_group_ids)} groups to monitor for user {active_user_id}: {monitored_group_ids}")
    
    logger.info("Starting message monitoring...")
    
    # Ensure client is connected
    if not client.is_connected():
        await client.connect()
        logger.info("Connected to Telegram")
    
    if not await client.is_user_authorized():
        logger.warning("Telegram client is not authorized. Login required before monitoring.")
        return False
    
    # Create the monitoring task if it doesn't exist or is done
    if not monitoring_task or monitoring_task.done():
        monitoring_task = asyncio.create_task(_run_client())
        logger.info(f"Created monitoring task: {monitoring_task}")
    else:
        logger.info("Monitoring task already running")
    
    return True


async def stop_monitoring():
    """
    Stop the monitoring process.
    """
    global monitoring_task, active_user_id, monitored_group_ids, keywords, messenger_ai
    
    logger.info("Stopping message monitoring...")
    
    # Clean up messenger AI if it exists
    if messenger_ai:
        try:
            await messenger_ai.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up messenger_ai: {e}")
    
    # Reset user and groups
    old_user_id = active_user_id
    active_user_id = None
    monitored_group_ids = set()
    keywords = set()
    
    logger.info(f"Cleared active user ID (was {old_user_id})")
    
    if monitoring_task and not monitoring_task.done():
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
        monitoring_task = None
        logger.info("Monitoring task cancelled")
    
    if client and client.is_connected():
        await client.disconnect()
        logger.info("Disconnected from Telegram")
    
    return True


# Function to reload keywords for the active user
async def reload_keywords():
    """
    Reload keywords for the currently active user.
    Call this when keywords are updated.
    """
    global active_user_id
    
    if active_user_id:
        await load_user_keywords(active_user_id)
        return True
    return False


async def ensure_messenger_ai_initialized():
    """
    Ensure that the messenger_ai is initialized.
    If it's None, try to reinitialize it.
    
    Returns:
        bool: True if messenger_ai is initialized, False otherwise
    """
    global messenger_ai, active_user_id
    
    # Use the get_messenger_ai and initialize_messenger_ai functions
    from server.app.services.messenger_ai import get_messenger_ai, initialize_messenger_ai
    
    # First, check if the singleton is initialized
    messenger_ai = await get_messenger_ai()
    if messenger_ai is not None:
        return True
        
    # Validate active_user_id
    if active_user_id is None:
        logger.warning("Cannot initialize MessengerAI: No active user ID")
        return False
        
    if not isinstance(active_user_id, int) or active_user_id <= 0:
        logger.error(f"Invalid active_user_id: {active_user_id}. Cannot initialize MessengerAI.")
        return False
    
    logger.warning(f"MessengerAI is None. Attempting to reinitialize for user {active_user_id}...")
    success = await initialize_messenger_ai(active_user_id)
    
    if success:
        # Update local reference to the global singleton
        messenger_ai = await get_messenger_ai()
        logger.info(f"Successfully reinitialized MessengerAI for user {active_user_id}")
        return True
    else:
        logger.error(f"Failed to reinitialize MessengerAI for user {active_user_id}")
        messenger_ai = None
        return False

async def diagnostic_check():
    """
    Check the status of the AI messenger and related services
    Returns a dictionary with diagnostic information
    """
    
    messenger_ai = await get_messenger_ai()
    
    diagnostics = {
        "ai_status": {
            "is_initialized": messenger_ai is not None,
            "connected_clients": 0,
            "active_listeners": 0,
            "monitored_groups_count": 0,
            "monitored_keywords_count": 0
        },
        "conversations": [],
        "recent_errors": error_tracker.get_recent_errors()
    }
    
    if messenger_ai:
        # Get more detailed information
        clients_info = messenger_ai.get_clients_info()
        diagnostics["ai_status"]["connected_clients"] = len(clients_info["connected_clients"])
        diagnostics["ai_status"]["active_listeners"] = clients_info["active_listeners"]
        
        # Get monitored groups information
        groups_info = messenger_ai.get_monitored_groups_info()
        diagnostics["ai_status"]["monitored_groups_count"] = len(groups_info["groups"])
        diagnostics["ai_status"]["monitored_keywords_count"] = groups_info["keywords_count"]
        
        # Get active conversations
        conversations = messenger_ai.get_active_conversations()
        diagnostics["conversations"] = conversations
    
    return diagnostics
    
# Add a periodic task to update WebSocket clients with the latest diagnostics
async def _periodic_health_check():
    """
    Periodically check system health and update connected WebSocket clients
    """
    while True:
        try:
            # Get the latest diagnostics
            diagnostics = await diagnostic_check()
            
            # Add timestamp
            diagnostics["timestamp"] = datetime.now().isoformat()
            diagnostics["health_check_time"] = datetime.now().isoformat()
            
            # Add system resource information
            try:
                cpu_percent = psutil.cpu_percent()
                memory_percent = psutil.virtual_memory().percent
                disk_percent = psutil.disk_usage('/').percent
                
                diagnostics["system_resources"] = {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "disk_usage_percent": disk_percent,
                    "process_memory_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                }
                
                # Log resource warnings
                if cpu_percent > 90:
                    logger.warning(f"High CPU usage detected: {cpu_percent}%")
                    error_tracker.add_error(f"High CPU usage: {cpu_percent}%", 
                                          "System performance may be degraded")
                    
                if memory_percent > 90:
                    logger.warning(f"High memory usage detected: {memory_percent}%")
                    error_tracker.add_error(f"High memory usage: {memory_percent}%", 
                                          "System may experience out-of-memory errors")
            except Exception as e:
                logger.error(f"Error checking system resources: {e}")
                diagnostics["system_resources"] = {"error": str(e)}
            
            # Update all connected WebSocket clients
            try:
                await websocket_manager.update_diagnostics(diagnostics)
            except Exception as e:
                logger.error(f"Error updating WebSocket clients with diagnostics: {e}")
            
            # Log any critical issues
            if not diagnostics["ai_status"]["is_initialized"]:
                logger.warning("AI messenger is not initialized during health check")
                error_tracker.add_error("AI messenger is not initialized", 
                                      "The AI messenger system is not properly initialized and may not be functioning correctly")
                
        except Exception as e:
            logger.error(f"Error in periodic health check: {e}", exc_info=True)
            error_tracker.add_error("Health check failed", str(e))
            
        # Wait before the next check
        await asyncio.sleep(30)  # Check every 30 seconds

# Function to start the health check background task
async def start_health_check_task():
    """
    Start the background task for periodic health checks
    """
    asyncio.create_task(_periodic_health_check())

async def get_active_user_id():
    """
    Get the currently active user ID.
    
    Returns:
        int or None: The active user ID, or None if not set.
    """
    global active_user_id
    return active_user_id