import asyncio
import os
from telethon import events
from server.app.services.telegram import get_client
from server.app.core.logging import logger
from server.app.utils.helpers import write_message_to_file
from server.app.services.messenger_ai import MessengerAI
from server.app.services.db_helpers import get_user_keywords, get_user_selected_groups
from server.app.models.models import SelectedGroup
from sqlalchemy import select

from datetime import datetime
# Global variables
client = get_client()
monitoring_task = None
active_user_id = 2
monitored_group_ids = set()  # Store group IDs to filter messages
keywords = set()  # Store keywords to filter messages
messenger_ai = None  # MessengerAI instance


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
            logger.debug("No active user ID set, cannot process messages")
            return
            
        # Skip if message has no text
        if not hasattr(message, 'text') or not message.text:
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


async def _periodic_health_check():
    """
    Periodically check the health of messenger_ai and reinitialize if needed.
    """
    while True:
        try:
            # Wait for 5 minutes between checks
            await asyncio.sleep(300)
            
            # Check if messenger_ai is None and needs to be reinitialized
            global messenger_ai, active_user_id
            if active_user_id and messenger_ai is None:
                logger.warning("Periodic health check detected messenger_ai is None. Attempting to reinitialize...")
                await ensure_messenger_ai_initialized()
            elif messenger_ai:
                # Verify that messenger_ai is still functioning
                try:
                    ai_diagnostic = await messenger_ai.diagnostic_check()
                    logger.debug(f"Periodic health check: AI status is {ai_diagnostic['status']}")
                    
                    # If AI is not in a good state, reinitialize
                    if ai_diagnostic['status'] not in ['ready', 'partial']:
                        logger.warning(f"AI messenger in bad state: {ai_diagnostic['status']}. Reinitializing...")
                        await messenger_ai.cleanup()
                        messenger_ai = None
                        await ensure_messenger_ai_initialized()
                except Exception as e:
                    logger.error(f"Error during messenger_ai health check: {e}")
        except asyncio.CancelledError:
            # Allow the task to be cancelled cleanly
            break
        except Exception as e:
            logger.error(f"Unexpected error in periodic health check: {e}")
            # Wait a bit before trying again
            await asyncio.sleep(60)


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
        active_user_id = user_id
        logger.info(f"Setting active_user_id to {active_user_id}")
    elif active_user_id is None:
        logger.warning("No user_id provided and no active_user_id set. Using default user ID.")
        # You might want to set a default user ID here if appropriate
    
    monitored_group_ids = set()
    
    if user_id:
        # Load user's keywords
        await load_user_keywords(user_id)
        
        # Initialize MessengerAI for this user
        messenger_ai = MessengerAI()
        ai_initialized = await messenger_ai.initialize(user_id)
        logger.info(f"MessengerAI initialized: {ai_initialized}")
        
        if ai_initialized:
            logger.info(f"MessengerAI initialized for user {user_id}")
            # Log diagnostic information
            logger.debug(f"AI clients initialized: {list(messenger_ai.ai_clients.keys())}")
            logger.debug(f"Group-AI mappings: {messenger_ai.group_ai_map}")
            
            # Validate the mappings - ensure group IDs are strings for comparison
            if messenger_ai.group_ai_map:
                for group_id, ai_id in list(messenger_ai.group_ai_map.items()):  # Use list to avoid modifying during iteration
                    if not isinstance(group_id, str):
                        logger.warning(f"Group ID {group_id} is not a string in group-AI mapping, converting to string")
                        
                        del messenger_ai.group_ai_map[group_id]
                        messenger_ai.group_ai_map[str(group_id)] = ai_id
            else:
                logger.warning(f"No group-AI mappings found for user {user_id}. AI will not respond to any groups.")
        else:
            logger.warning(f"Failed to initialize MessengerAI for user {user_id}")
            messenger_ai = None  # Set to None on failure
            
        # Double check that messenger_ai is properly initialized
        if messenger_ai is None:
            logger.error(f"MessengerAI is None after initialization attempt for user {user_id}")
        else:
            logger.info(f"MessengerAI is properly initialized and ready to handle messages")
         # Fetch selected groups for the user
        monitored_group_ids = await get_user_selected_groups(user_id)
        if not monitored_group_ids:
            logger.warning(f"No selected groups found for user {user_id}. No messages will be monitored.")
        else:
            logger.info(f"Found {len(monitored_group_ids)} groups to monitor for user {user_id}: {monitored_group_ids}")
    
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
        await messenger_ai.cleanup()
        messenger_ai = None
    
    # Reset user and groups
    active_user_id = None
    monitored_group_ids = set()
    keywords = set()
    
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
    messenger_ai = MessengerAI()
    ai_initialized = await messenger_ai.initialize(active_user_id)
    
    if ai_initialized:
        logger.info(f"Successfully reinitialized MessengerAI for user {active_user_id}")
        return True
    else:
        logger.error(f"Failed to reinitialize MessengerAI for user {active_user_id}")
        messenger_ai = None
        return False

async def diagnostic_check():
    """
    Perform a diagnostic check of the monitoring system and AI messenger.
    Returns information about the current state.
    """
    global active_user_id, monitored_group_ids, keywords, messenger_ai
    
    result = {
        "active_user_id": active_user_id,
        "monitored_groups_count": len(monitored_group_ids) if monitored_group_ids else 0,
        "monitored_groups": list(monitored_group_ids) if monitored_group_ids else [],
        "keywords_count": len(keywords) if keywords else 0,
        "keywords": list(keywords) if keywords else [],
        "messenger_ai_initialized": messenger_ai is not None,
        "client_connected": False,
        "client_authorized": False,
        "ai_status": "not_initialized"
    }
    
    # Check telegram client status
    try:
        if client:
            result["client_connected"] = client.is_connected()
            if result["client_connected"]:
                result["client_authorized"] = await client.is_user_authorized()
    except Exception as e:
        logger.error(f"Error checking client status: {e}")
    
    # Check messenger AI status
    if messenger_ai:
        try:
            ai_diagnostic = await messenger_ai.diagnostic_check()
            result["ai_diagnostic"] = ai_diagnostic
            result["ai_status"] = ai_diagnostic["status"]
        except Exception as e:
            logger.error(f"Error checking AI messenger status: {e}")
            result["ai_status"] = "error"
    else:
        # Try to reinitialize messenger_ai if it's None and we have an active user
        if active_user_id:
            result["ai_status"] = "attempting_reinit"
            ai_initialized = await ensure_messenger_ai_initialized()
            if ai_initialized and messenger_ai:
                try:
                    ai_diagnostic = await messenger_ai.diagnostic_check()
                    result["ai_diagnostic"] = ai_diagnostic
                    result["ai_status"] = ai_diagnostic["status"]
                    result["messenger_ai_initialized"] = True
                    result["messenger_ai_reinitialized"] = True
                except Exception as e:
                    logger.error(f"Error checking reinitialized AI messenger status: {e}")
                    result["ai_status"] = "error_after_reinit"
            else:
                result["ai_status"] = "reinit_failed"
        else:
            result["ai_status"] = "no_active_user"
    
    return result