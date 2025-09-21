import asyncio
import os
import psutil
from telethon import events
from server.app.services.telegram import client_manager
from server.app.core.logging import logger
from server.app.utils.helpers import write_message_to_file
from server.app.services.messenger_ai import initialize_messenger_ai, get_messenger_ai
from server.app.utils.db_helpers import get_user_keywords, get_user_selected_groups
from server.app.services.websocket_manager import websocket_manager
from server.app.services.redis_client import check_redis_health
from datetime import datetime
from collections import deque
from typing import Dict, Any


# Semaphore to limit concurrent operations
API_SEMAPHORE = asyncio.Semaphore(5)

# Global variables
active_user_id = None
monitoring_active = False
health_check_task = None
message_handler_task = None


# Add a class to track recent errors
class ErrorTracker:
    def __init__(self, max_errors=100):
        self.errors = deque(maxlen=max_errors)

    def add_error(self, error_type, error_message, details=None):
        self.errors.append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": error_type,
                "message": error_message,
                "details": details or {},
            }
        )

    def get_recent_errors(self, count=None):
        if count is None:
            return list(self.errors)
        return list(self.errors)[-count:]

    def clear_errors(self):
        self.errors.clear()


# Create a singleton instance
error_tracker = ErrorTracker()


async def set_active_user_id(user_id):
    """Set the active user ID for monitoring."""
    global active_user_id
    active_user_id = user_id
    logger.info(f"Set active user ID to {user_id}")
    return active_user_id


async def get_active_user_id():
    """Get the current active user ID."""
    return active_user_id


async def start_monitoring(user_id=None):
    """
    Start monitoring Telegram messages.

    Args:
        user_id: Optional user ID to override the active user

    Returns:
        bool: True if monitoring was started successfully
    """
    global monitoring_active, message_handler_task, active_user_id

    if user_id:
        active_user_id = user_id

    if not active_user_id:
        logger.info("Cannot start monitoring: No active user ID set")
        return False

    # If already monitoring, stop first
    if monitoring_active:
        await stop_monitoring()

    try:
        client = await client_manager.get_user_client(active_user_id)

        if not client:
            logger.error(f"Could not get Telegram client for user {active_user_id}")
            return False

        # Connect if not already connected
        if not client.is_connected():
            try:
                async with API_SEMAPHORE:
                    await asyncio.wait_for(client.connect(), timeout=5)
            except asyncio.TimeoutError:
                logger.error(
                    f"Timeout connecting to Telegram for user {active_user_id}"
                )
                return False

        # Check if authorized
        try:
            async with API_SEMAPHORE:
                is_authorized = await asyncio.wait_for(
                    client.is_user_authorized(), timeout=5
                )
            if not is_authorized:
                logger.info(
                    f"Telegram client is not authorized for user {active_user_id}"
                )
                return False
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"Error checking authorization for user {active_user_id}: {e}")
            return False

        # Initialize AI messenger in background
        await initialize_messenger_ai(active_user_id)

        # Start message handler task
        message_handler_task = asyncio.create_task(
            _setup_message_handler(client, active_user_id)
        )

        monitoring_active = True
        logger.info(f"Started monitoring for user {active_user_id}")

        # Broadcast status update
        await websocket_manager.broadcast(
            {"monitoring_active": True, "active_user_id": active_user_id}
        )

        return True

    except Exception as e:
        logger.error(f"Error starting monitoring: {e}")
        error_tracker.add_error("monitoring_start", str(e))
        return False


async def stop_monitoring():
    """
    Stop monitoring Telegram messages.

    Returns:
        bool: True if monitoring was stopped successfully
    """
    global monitoring_active, message_handler_task

    if not monitoring_active:
        logger.info("Monitoring is already stopped")
        return True

    try:
        # Cancel message handler task
        if message_handler_task and not message_handler_task.done():
            message_handler_task.cancel()
            try:
                await message_handler_task
            except asyncio.CancelledError:
                pass

        monitoring_active = False
        logger.info("Stopped message monitoring")

        # Broadcast status update
        await websocket_manager.broadcast({"monitoring_active": False})

        return True

    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
        error_tracker.add_error("monitoring_stop", str(e))
        return False


async def _setup_message_handler(client, user_id):
    """
    Set up the message handler for monitoring.
    This runs as a background task.

    Args:
        client: The Telegram client
        user_id: The user ID to monitor for
    """
    try:
        # Get user's selected groups
        selected_groups = await get_user_selected_groups(user_id)
        logger.info(f"Monitoring {len(selected_groups)} selected groups")

        # Get user's keywords
        keywords = await get_user_keywords(user_id)
        logger.info(f"Monitoring for {len(keywords)} keywords")

        # Set up event handler for new messages
        @client.on(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            # Process in a separate task to avoid blocking
            task = asyncio.create_task(
                _process_message(event, selected_groups, keywords)
            )
            # No need to await the task here, it will run in the background

        # Keep the task alive
        while True:
            if not monitoring_active:
                logger.info("Monitoring no longer active, exiting handler task")
                break

            # Ping to keep the connection alive
            try:
                async with API_SEMAPHORE:
                    await asyncio.wait_for(client.get_me(), timeout=5)
            except Exception as e:
                logger.warning(f"Error in connection check: {e}")

            # Wait before next check
            await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"Error in message handler setup: {e}")
        error_tracker.add_error("message_handler_setup", str(e))


async def _process_message(event, selected_groups, keywords):
    """
    Process a new message event.

    Args:
        event: The Telegram event
        selected_groups: List of selected groups to monitor
        keywords: List of keywords to match
    """
    try:
        # Skip outgoing messages
        if event.out:
            return

        # Process the message based on type
        chat = await event.get_chat()
        if not chat:
            logger.warning("No chat found for message, skipping")
            return
        sender = await event.get_sender()
        if not sender:
            logger.warning("No sender found for message, skipping")
            return

        # Check if it's a group or a DM
        if hasattr(chat, "title"):  # It's a group/channel
            # Check if this group is being monitored
            if str(chat.id) not in selected_groups:
                return

            await _process_group_message(event, chat, sender, keywords)
        else:  # It's a private chat (DM)
            await _process_direct_message(event, chat, sender)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        error_tracker.add_error("message_processing", str(e))


async def _process_group_message(event, chat, sender, keywords):
    """
    Process a message from a group.

    Args:
        event: The Telegram event
        chat: The chat entity
        sender: The sender entity
        keywords: List of keywords to match
    """
    try:
        message = event.message

        # Skip if no text
        if not hasattr(message, "text") or not message.text:
            return

        # Format names
        sender_name = getattr(sender, "first_name", "")
        if hasattr(sender, "last_name") and sender.last_name:
            sender_name += f" {sender.last_name}"

        if not sender_name:
            sender_name = f"User {sender.id}"

        # Create message data
        message_data = {
            "message_id": message.id,
            "chat_id": chat.id,
            "chat_title": chat.title,
            "sender_id": sender.id,
            "sender_name": sender_name,
            "text": message.text,
            "date": message.date.isoformat(),
            "matched_keywords": [],
        }

        # Check for keyword matches
        matched_keywords = _match_keywords(message.text, keywords)
        if matched_keywords:
            message_data["matched_keywords"] = matched_keywords

        # Write to file for logging
        _ = asyncio.create_task(write_message_to_file(message_data, "group"))

        # Forward to AI messenger if keywords matched
        if matched_keywords:
            messenger = await get_messenger_ai()
            if messenger:
                await messenger.handle_message(message_data)

        # Send to WebSocket
        await websocket_manager.add_chat_message(message_data)

    except Exception as e:
        logger.error(f"Error processing group message: {e}")
        error_tracker.add_error("group_message_processing", str(e))


async def _process_direct_message(event, chat, sender):
    """
    Process a direct message.

    Args:
        event: The Telegram event
        chat: The chat entity
        sender: The sender entity
    """
    try:
        message = event.message

        # Skip if no text
        if not hasattr(message, "text") or not message.text:
            return

        # Format names
        sender_name = getattr(sender, "first_name", "")
        if hasattr(sender, "last_name") and sender.last_name:
            sender_name += f" {sender.last_name}"

        if not sender_name:
            sender_name = f"User {sender.id}"

        # Create message data
        message_data = {
            "message_id": message.id,
            "chat_id": chat.id,
            "sender_id": sender.id,
            "sender_name": sender_name,
            "text": message.text,
            "date": message.date.isoformat(),
        }

        # Write to file for logging
        _ = asyncio.create_task(write_message_to_file(message_data, "group"))

        # Forward to AI messenger (always process DMs)
        messenger = await get_messenger_ai()
        if messenger:
            await messenger.handle_message(message_data)

        # Send to WebSocket
        await websocket_manager.add_chat_message(message_data)

    except Exception as e:
        logger.error(f"Error processing direct message: {e}")
        error_tracker.add_error("dm_processing", str(e))


def _match_keywords(text, keywords_list):
    """
    Enhanced keyword matching with word boundaries and partial matches.

    Args:
        text: The message text to check
        keywords_list: List of keywords to match

    Returns:
        list: List of matched keywords
    """
    if not keywords_list:
        return []

    text_lower = text.lower()
    matched = []

    # Split text into words for word boundary checking
    words = set(text_lower.split())

    for keyword in keywords_list:
        keyword_lower = keyword.lower()

        # Check for exact word matches (with word boundaries)
        if keyword_lower in words:
            matched.append(keyword)
            continue

        # Check for phrases (multiple words)
        if " " in keyword_lower and keyword_lower in text_lower:
            matched.append(keyword)
            continue

        # Check for partial matches within words (more than 3 chars to avoid false positives)
        if len(keyword_lower) > 3 and keyword_lower in text_lower:
            matched.append(keyword)

    return matched


async def start_health_check_task():
    """
    Start a background task to monitor system health.

    Returns:
        bool: True if the task was started successfully
    """
    global health_check_task

    # Cancel existing task if running
    if health_check_task and not health_check_task.done():
        health_check_task.cancel()
        try:
            await health_check_task
        except asyncio.CancelledError:
            pass

    # Start new task
    health_check_task = asyncio.create_task(_run_health_check())
    logger.info("Started health check task")

    return True


async def _run_health_check():
    """
    Run continuous health checks in the background.
    This monitors system components and reports status.
    """
    """
    Run continuous health checks in the background.
    This monitors system components and reports status.
    """
    try:
        while True:
            try:
                # Get the client and check its status - skip if no active user
                if not active_user_id:
                    await asyncio.sleep(30)
                    continue

                client = await client_manager.get_user_client(active_user_id)

                # Check client connection
                if client and client.is_connected():
                    client_status = {"is_connected": True}

                    # Check authorization
                    try:
                        async with API_SEMAPHORE:
                            is_authorized = await asyncio.wait_for(
                                client.is_user_authorized(), timeout=5
                            )
                        client_status["is_authorized"] = is_authorized
                    except Exception as e:
                        client_status["is_authorized"] = False
                        client_status["auth_error"] = str(e)
                else:
                    client_status = {"is_connected": False, "is_authorized": False}

                # Check AI messenger status
                ai_messenger = await get_messenger_ai()
                ai_status = {
                    "initialized": ai_messenger is not None,
                    "ai_accounts": (
                        len(getattr(ai_messenger, "ai_clients", {}))
                        if ai_messenger
                        else 0
                    ),
                }

                # Get system resource info
                system_status = {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "active_tasks": (
                        len(asyncio.all_tasks()) if hasattr(asyncio, "all_tasks") else 0
                    ),
                }

                # Check Redis health
                redis_health = await check_redis_health()

                # Build health status
                health_status = {
                    "timestamp": datetime.now().isoformat(),
                    "client": client_status,
                    "ai_messenger": ai_status,
                    "system": system_status,
                    "redis": redis_health,
                    "monitoring_active": monitoring_active,
                    "active_user_id": active_user_id,
                    "recent_errors": error_tracker.get_recent_errors(5),
                }

                # Use broadcast instead of broadcast_health since it doesn't exist
                await websocket_manager.broadcast(
                    {"type": "health_update", "data": health_status}
                )

            except Exception as e:
                logger.error(f"Error in health check: {e}")
                error_tracker.add_error("health_check", str(e))

            # Wait before next check
            await asyncio.sleep(30)

    except asyncio.CancelledError:
        logger.info("Health check task cancelled")
    except Exception as e:
        logger.error(f"Health check task failed: {e}")
        error_tracker.add_error("health_check_task", str(e))


# Add the diagnostic_check function
async def diagnostic_check():
    """
    Perform a diagnostic check of the system and return the results.

    Returns:
        dict: Diagnostic information about the system
    """
    try:
        # Get the client and check its status - skip if no active user
        if not active_user_id:
            return {
                "timestamp": datetime.now().isoformat(),
                "client": {"is_connected": False, "is_authorized": False},
                "monitoring_active": monitoring_active,
                "active_user_id": active_user_id,
                "recent_errors": error_tracker.get_recent_errors(10),
                "error": "No active user set",
            }

        client = await client_manager.get_user_client(active_user_id)

        # Check client connection
        client_status = {
            "is_connected": client.is_connected() if client else False,
            "is_authorized": False,
        }

        # Check authorization
        if client and client.is_connected():
            try:
                async with API_SEMAPHORE:
                    is_authorized = await asyncio.wait_for(
                        client.is_user_authorized(), timeout=5
                    )
                client_status["is_authorized"] = is_authorized
            except Exception as e:
                logger.error(f"Error checking authorization: {e}")
                client_status["auth_error"] = str(e)

        # Get AI messenger status
        ai_messenger = await get_messenger_ai()
        ai_diagnostics = {}

        if ai_messenger:
            try:
                # Use the diagnostic_check method if available
                if hasattr(ai_messenger, "diagnostic_check"):
                    ai_diagnostics = await ai_messenger.diagnostic_check()
                else:
                    # Fallback to basic info
                    ai_diagnostics = {
                        "ai_status": {
                            "is_initialized": bool(
                                getattr(ai_messenger, "ai_clients", {})
                            ),
                            "ai_clients_count": len(
                                getattr(ai_messenger, "ai_clients", {})
                            ),
                            "active_tasks_count": len(
                                getattr(ai_messenger, "active_tasks", set())
                            ),
                        }
                    }
            except Exception as e:
                logger.error(f"Error getting AI diagnostics: {e}")
                ai_diagnostics = {
                    "ai_status": {"is_initialized": False, "error": str(e)}
                }
        else:
            ai_diagnostics = {
                "ai_status": {
                    "is_initialized": False,
                    "error": "AI messenger not initialized",
                }
            }

        # Combine client status with AI diagnostics
        diagnostics = {
            "timestamp": datetime.now().isoformat(),
            "client": client_status,
            "monitoring_active": monitoring_active,
            "active_user_id": active_user_id,
            "recent_errors": error_tracker.get_recent_errors(10),
        }

        # Merge AI diagnostics
        diagnostics.update(ai_diagnostics)

        # Add Redis health check
        try:
            redis_health = await check_redis_health()
            diagnostics["redis"] = redis_health
        except Exception as e:
            logger.error(f"Error checking Redis health: {e}")
            diagnostics["redis"] = {
                "status": "error",
                "available": False,
                "error": str(e),
            }

        # Add system resource information
        try:
            import psutil

            diagnostics["system_resources"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage("/").percent,
                "process_memory_mb": psutil.Process(os.getpid()).memory_info().rss
                / 1024
                / 1024,
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            diagnostics["system_resources"] = {"error": str(e)}

        return diagnostics

    except Exception as e:
        logger.error(f"Error in diagnostic_check: {e}")
        error_tracker.add_error("diagnostic_check", str(e))
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "status": "error",
        }


async def get_system_health() -> Dict[str, Any]:
    """
    Get comprehensive system health information.

    Returns:
        dict: System health information including resources, services, and status
    """
    try:
        health_info = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": None,
            "process_info": {},
            "system_resources": {},
            "active_connections": 0,
            "background_tasks": 0,
            "recent_errors": error_tracker.get_recent_errors(10),
        }

        # Get process information
        try:
            current_process = psutil.Process(os.getpid())
            with current_process.oneshot():
                health_info["process_info"] = {
                    "pid": current_process.pid,
                    "memory_info_mb": current_process.memory_info().rss / 1024 / 1024,
                    "cpu_percent": current_process.cpu_percent(),
                    "num_threads": current_process.num_threads(),
                    "status": current_process.status(),
                    "create_time": current_process.create_time(),
                }
                health_info["uptime_seconds"] = current_process.create_time()
        except Exception as e:
            health_info["process_info"] = {"error": str(e)}

        # Get system resources
        try:
            health_info["system_resources"] = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory": {
                    "percent": psutil.virtual_memory().percent,
                    "available_mb": psutil.virtual_memory().available / 1024 / 1024,
                    "total_mb": psutil.virtual_memory().total / 1024 / 1024,
                },
                "disk": {
                    "percent": psutil.disk_usage("/").percent,
                    "free_mb": psutil.disk_usage("/").free / 1024 / 1024,
                    "total_mb": psutil.disk_usage("/").total / 1024 / 1024,
                },
            }
        except Exception as e:
            health_info["system_resources"] = {"error": str(e)}

        # Get active connections from websocket manager
        try:
            health_info["active_connections"] = websocket_manager.get_connection_count()
        except Exception as e:
            health_info["active_connections"] = 0
            logger.debug(f"Error getting connection count: {e}")

        # Get background task count
        try:
            if hasattr(asyncio, "all_tasks"):
                health_info["background_tasks"] = len(asyncio.all_tasks())
            else:
                # Fallback for older Python versions
                health_info["background_tasks"] = len(asyncio.Task.all_tasks())
        except Exception as e:
            health_info["background_tasks"] = 0
            logger.debug(f"Error getting task count: {e}")

        # Add monitoring status
        health_info["monitoring"] = {
            "active": monitoring_active,
            "active_user_id": active_user_id,
        }

        return health_info

    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        error_tracker.add_error("system_health", str(e))
        return {
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "status": "error",
        }
