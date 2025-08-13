import os
import asyncio
import traceback
from datetime import datetime, timedelta
from telethon import TelegramClient, errors as telethon_errors, events
from server.app.core.logging import logger
from server.app.core.databases import AsyncSessionLocal
from server.app.models.models import AIAccount
from sqlalchemy import select, and_
from server.app.services.ai_engine import generate_response
from server.app.utils.db_helpers import  get_user_keywords
from server.app.utils.group_helpers import get_group_ai_mappings
from server.app.services.message_analyzer import MessageAnalyzer
from server.app.services.conversation_manager import ConversationManager
from server.app.services.websocket_manager import websocket_manager
from contextlib import asynccontextmanager

# Global semaphores for concurrency control
DB_SEMAPHORE = asyncio.Semaphore(5)  # Limit concurrent DB operations
API_SEMAPHORE = asyncio.Semaphore(10)  # Limit concurrent Telegram API calls

@asynccontextmanager
async def get_db_session():
    """
    Context manager to safely get and release a database session.
    This helps prevent the "database is locked" errors by ensuring
    proper session handling.
    """
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()

class MessengerAI:
    """
    A class that maintains automated chats with users when messages match keywords.
    Uses a Telegram user account (not a bot) to respond to messages via DM.
    Responds to messages in groups only if they contain specific keywords,
    and then continues the conversation in direct messages.
    """
    def __init__(self):
        self.ai_clients = {}    # Dictionary of Telethon clients for AI accounts
        self.ai_accounts = {}   # Dictionary of AI account info
        self.group_ai_map = {}  # Maps group_ids to AI account ids
        
        # New components for refactored messaging system
        self.message_analyzer = MessageAnalyzer()  # For analyzing messages and detecting keywords
        self.conversation_manager = ConversationManager()  # For tracking DM conversations
        
        # Task management
        self.active_tasks = set()
        self.rate_limits = {}   # Track rate limits for senders
        
        # Track monitored keywords
        self.monitored_keywords = set()
        
        # Store conversations
        self.conversations = {}

    async def initialize(self, user_id):
        """
        Initialize the AI messenger with all active accounts for this user.
        Also loads the group-to-AI account mappings and keywords.
        
        Args:
            user_id: The ID of the user who owns this AI messenger
        
        Returns:
            bool: True if at least one account was initialized successfully
        """
        try:
            # Clean up any existing clients first
            await self.cleanup()
            
            # Initialize empty dictionaries
            self.ai_clients = {}
            self.ai_accounts = {}
            self.group_ai_map = {}
            self.active_tasks = set()
            
            # Initialize new components
            self.message_analyzer = MessageAnalyzer()
            self.conversation_manager = ConversationManager()
            
            # Load user's keywords in background
            keywords_task = asyncio.create_task(self._load_keywords(user_id))
            
            # Get all active AI accounts for this user with concurrent safe DB access
            ai_accounts = await self._get_ai_accounts(user_id)
            
            if not ai_accounts:
                logger.warning(f"No active AI accounts found for user {user_id}")
                return False
                
            # Initialize accounts concurrently
            init_tasks = []
            for account in ai_accounts:
                task = asyncio.create_task(self._initialize_account(account))
                init_tasks.append(task)
                
            # Wait for all initialization tasks
            results = await asyncio.gather(*init_tasks, return_exceptions=True)
            success_count = sum(1 for result in results if result is True)
            
            # Wait for keywords to load and set them
            keywords = await keywords_task
            self.message_analyzer.set_keywords(keywords)
            
            # Load group mappings in background
            mapping_task = asyncio.create_task(self._load_group_mappings(user_id))
            self.active_tasks.add(mapping_task)
            mapping_task.add_done_callback(lambda t: self.active_tasks.discard(t))
            
            return success_count > 0
                
        except Exception as e:
            logger.error(f"Error initializing AI messenger: {e}")
            logger.error(traceback.format_exc())
            # Clean up any connected clients
            await self.cleanup()
            return False
            
    async def _load_keywords(self, user_id):
        """Load keywords with database connection protection"""
        async with DB_SEMAPHORE:
            try:
                return await get_user_keywords(user_id)
            except Exception as e:
                logger.error(f"Error loading keywords: {e}")
                return []
                
    async def _get_ai_accounts(self, user_id):
        """Get AI accounts with database connection protection"""
        async with DB_SEMAPHORE:
            try:
                async with get_db_session() as session:
                    stmt = select(AIAccount).where(AIAccount.user_id == user_id, AIAccount.is_active == True)
                    result = await session.execute(stmt)
                    return result.scalars().all()
            except Exception as e:
                logger.error(f"Error getting AI accounts: {e}")
                return []
                
    async def _initialize_account(self, ai_account):
        """Initialize a single AI account with proper error handling"""
        try:
            # Create path for file-based session
            sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
            os.makedirs(sessions_dir, exist_ok=True)
            session_path = os.path.join(sessions_dir, f"ai_account_{ai_account.id}")
            
            # Convert API ID to int with proper error handling
            try:
                api_id = int(ai_account.api_id.strip() if isinstance(ai_account.api_id, str) else ai_account.api_id)
            except (ValueError, TypeError, AttributeError):
                logger.error(f"Invalid API ID format for account {ai_account.id}")
                return False
                
            # Get API hash
            api_hash = ai_account.api_hash.strip() if isinstance(ai_account.api_hash, str) else ai_account.api_hash
            
            # Create client with file-based session
            client = TelegramClient(session_path, api_id, api_hash)
            
            # Connect with timeout protection
            try:
                async with API_SEMAPHORE:
                    await asyncio.wait_for(client.connect(), timeout=10)
            except asyncio.TimeoutError:
                logger.error(f"Timeout connecting client for account {ai_account.id}")
                await client.disconnect()
                return False
                
            # Check authorization with timeout protection
            try:
                async with API_SEMAPHORE:
                    authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=5)
            except (asyncio.TimeoutError, Exception) as e:
                logger.error(f"Error checking authorization for account {ai_account.id}: {e}")
                await client.disconnect()
                return False
                
            if not authorized:
                logger.error(f"Account {ai_account.id} is not authorized")
                await client.disconnect()
                return False
                
            # Successfully initialized
            self.ai_clients[ai_account.id] = client
            self.ai_accounts[ai_account.id] = ai_account
            logger.info(f"AI account {ai_account.id} initialized successfully")
            
            # Set up event handler using task-based approach
            @client.on(events.NewMessage(incoming=True))
            async def handle_ai_dm_reply(event):
                # Create a background task for handling the event
                task = asyncio.create_task(self._handle_event_message(event, ai_account.id))
                self.active_tasks.add(task)
                task.add_done_callback(lambda t: self.active_tasks.discard(t))
                
            return True
            
        except Exception as e:
            logger.error(f"Error initializing account {ai_account.id}: {e}")
            logger.error(traceback.format_exc())
            return False
            
    async def _handle_event_message(self, event, ai_account_id):
        """Handle incoming event messages in a non-blocking way"""
        try:
            message = event.message
            
            # Skip if not a text message
            if not hasattr(message, 'text') or not message.text:
                return
                
            # Check if it's a direct message
            try:
                chat = await event.get_chat()
                chat_title = getattr(chat, 'title', None)
                if chat_title:  # Skip if it's a group/channel
                    return
            except Exception:
                pass
                
            # Get sender info with error handling
            try:
                sender = await event.get_sender()
                first_name = getattr(sender, 'first_name', '')
                last_name = getattr(sender, 'last_name', '')
                sender_name = f"{first_name} {last_name}".strip() or f"User {sender.id}"
                sender_id = sender.id
            except Exception as e:
                logger.error(f"Error getting sender info: {e}")
                return
                
            logger.info(f"AI account {ai_account_id} received DM from {sender_name} (ID: {sender_id})")
            
            # Handle DM in a background task
            dm_task = asyncio.create_task(
                self._handle_dm_message(sender_id, sender_name, message.text)
            )
            self.active_tasks.add(dm_task)
            dm_task.add_done_callback(lambda t: self.active_tasks.discard(t))
            
        except Exception as e:
            logger.error(f"Error handling event message: {e}")
            logger.error(traceback.format_exc())
            
    async def _load_group_mappings(self, user_id):
        """Load group mappings with database connection protection"""
        async with DB_SEMAPHORE:
            try:
                group_mappings = await get_group_ai_mappings(user_id)
                self.group_ai_map = {}
                
                # Process mappings
                for group_id, mapping_info in group_mappings.items():
                    self.group_ai_map[group_id] = mapping_info['ai_account_id']
                    
                logger.info(f"Loaded {len(self.group_ai_map)} group-AI mappings")
                return group_mappings
            except Exception as e:
                logger.error(f"Error loading group mappings: {e}")
                return {}
                
    async def handle_message(self, message_data):
        """
        Process a message in a non-blocking way using a background task
        
        Args:
            message_data: Dictionary containing message information
        """
        # Create a task for message processing
        task = asyncio.create_task(self._process_message(message_data))
        self.active_tasks.add(task)
        task.add_done_callback(lambda t: self.active_tasks.discard(t))
        
    async def _process_message(self, message_data):
        """Process a message with rate limiting and error handling"""
        try:
            # Extract message data
            chat_id = message_data.get('chat_id')
            message_id = message_data.get('message_id')
            chat_title = message_data.get('chat_title')
            sender_name = message_data.get('sender_name', 'Unknown User')
            sender_id = message_data.get('sender_id')
            message_text = message_data.get('text')
            
            # Validate required fields
            if not chat_id or not message_text or not sender_id:
                logger.error(f"Missing required fields in message data")
                return
                
            # Apply rate limiting
            if not await self._check_rate_limit(sender_id):
                logger.warning(f"Rate limit exceeded for sender {sender_id}")
                return
                
            # Determine message type
            is_group_message = bool(chat_title)
            
            # Process based on message type
            if is_group_message:
                await self._handle_group_message(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=message_text,
                    message_id=message_id
                )
            else:
                await self._handle_dm_message(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=message_text
                )
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.error(traceback.format_exc())
            
    async def _check_rate_limit(self, sender_id):
        """Check if sender has exceeded rate limits"""
        now = datetime.now()
        sender_key = str(sender_id)
        
        if sender_key not in self.rate_limits:
            self.rate_limits[sender_key] = {
                "count": 1,
                "reset_time": now + timedelta(minutes=1)
            }
            return True
            
        # Reset counter if time has passed
        if now > self.rate_limits[sender_key]["reset_time"]:
            self.rate_limits[sender_key] = {
                "count": 1,
                "reset_time": now + timedelta(minutes=1)
            }
            return True
            
        # Increment counter and check limit
        self.rate_limits[sender_key]["count"] += 1
        if self.rate_limits[sender_key]["count"] > 10:  # Max 10 messages per minute
            return False
            
        return True
        
    async def _handle_group_message(self, chat_id, chat_title, sender_id, sender_name, message_text, message_id):
        """Handle a group message with improved non-blocking approach"""
        try:
            # Find the appropriate AI account
            str_chat_id = str(chat_id)
            short_chat_id = str_chat_id.replace('-100', '')
            
            ai_account_id = None
            if str_chat_id in self.group_ai_map:
                ai_account_id = self.group_ai_map[str_chat_id]
            elif short_chat_id in self.group_ai_map:
                ai_account_id = self.group_ai_map[short_chat_id]
                
            if not ai_account_id:
                logger.debug(f"No AI account mapped to group {chat_id}")
                return
                
            # Check if message contains keywords - early check
            analysis_task = asyncio.create_task(self.message_analyzer.should_respond(message_text))
            analysis = await analysis_task
            
            if not analysis["should_respond"]:
                logger.debug(f"No keywords matched in message from {sender_name}")
                return
                
            matched_keywords = analysis["matched_keywords"]
            logger.info(f"Message from {sender_name} in {chat_title} matched keywords: {matched_keywords}")
            
            # Get the client and account info
            ai_client = self.ai_clients.get(ai_account_id)
            ai_account = self.ai_accounts.get(ai_account_id)
            
            if not ai_client or not ai_account:
                logger.warning(f"AI account {ai_account_id} not initialized")
                return
                
            # Ensure client is connected
            if not await self._ensure_client_connected(ai_account_id):
                logger.error(f"Failed to ensure client connection for account {ai_account_id}")
                return
                
            # Check if we can send a DM to this user
            if not self.conversation_manager.can_send_dm(sender_id):
                logger.warning(f"Cannot send DM to user {sender_id} due to previous errors")
                return
                
            # Update conversation in background - specify this is from a group
            conversation_task = asyncio.create_task(
                self._update_conversation(
                    sender_id, 
                    sender_name, 
                    message_text, 
                    ai_account_id,
                    chat_type="group",
                    group_id=chat_id,
                    group_name=chat_title
                )
            )
            
            # Get conversation state
            is_new = self.conversation_manager.is_new_conversation(sender_id, ai_account_id)
            
            # Wait for conversation update
            await conversation_task
            
            # Get conversation history
            history = self.conversation_manager.get_conversation_history(sender_id, ai_account_id)
            
            # Generate and send response in background
            response_task = asyncio.create_task(
                self._generate_and_send_response(
                    ai_client=ai_client,
                    ai_account=ai_account,
                    ai_account_id=ai_account_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=message_text,
                    matched_keywords=matched_keywords,
                    is_new_conversation=is_new,
                    conversation_history=history,
                    from_group=True,
                    group_name=chat_title
                )
            )
            
            self.active_tasks.add(response_task)
            response_task.add_done_callback(lambda t: self.active_tasks.discard(t))
            
            # Send a WebSocket notification about this conversation
            await self._send_conversation_update(sender_id, ai_account_id)
            
        except Exception as e:
            logger.error(f"Error handling group message: {e}")
            logger.error(traceback.format_exc())
    
    async def _update_conversation(self, sender_id, sender_name, message_text, ai_account_id, chat_type="direct", group_id=None, group_name=None):
        """Update conversation history without blocking"""
        try:
            self.conversation_manager.add_user_message(
                user_id=sender_id,
                message_text=message_text,
                ai_account_id=ai_account_id,
                sender_name=sender_name,
                chat_type=chat_type,
                group_id=group_id,
                group_name=group_name
            )
            
            # Send WebSocket notification in background
            ws_task = asyncio.create_task(self._send_ws_notification(
                sender_id, sender_name, message_text, ai_account_id, is_ai=False,
                group_name=group_name, group_id=group_id, chat_type=chat_type
            ))
            
            self.active_tasks.add(ws_task)
            ws_task.add_done_callback(lambda t: self.active_tasks.discard(t))
            
        except Exception as e:
            logger.error(f"Error updating conversation: {e}")

    async def _send_ws_notification(self, sender_id, sender_name, message, ai_account_id, is_ai=False, group_name=None, group_id=None, chat_type="direct"):
        """Send WebSocket notification without blocking"""
        try:
            conversation_id = f"{sender_id}-{ai_account_id}"
            
            # Create conversation data
            chat_message = {
                "conversation_id": conversation_id,
                "sender_id": sender_id,
                "sender_name": sender_name,
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "ai_account_id": ai_account_id,
                "is_ai_message": is_ai,
                "chat_type": chat_type
            }
            
            # Add group info if available
            if chat_type == "group":
                chat_message["from_group"] = True
                chat_message["group_id"] = group_id
                chat_message["group_name"] = group_name
                
            # Send to WebSocket
            await websocket_manager.add_chat_message(chat_message)
            
            # Also update the conversation
            await self._send_conversation_update(sender_id, ai_account_id)
            
        except Exception as e:
            logger.error(f"Error sending WebSocket notification: {e}")

    async def _send_conversation_update(self, user_id, ai_account_id):
        """Send an updated conversation to the WebSocket manager"""
        try:
            # Format the conversation ID as expected by the frontend
            conversation_id = f"{user_id}-{ai_account_id}"
            
            # Get conversation history
            history = self.conversation_manager.get_conversation_history(user_id, ai_account_id)
            
            # Get the raw conversation data
            user_id_str = str(user_id)
            if user_id_str not in self.conversation_manager.conversations:
                return
                
            conv_data = self.conversation_manager.conversations[user_id_str]
            
            # Get AI account info for display
            ai_account = self.ai_accounts.get(ai_account_id)
            ai_account_name = getattr(ai_account, 'name', f"AI Account {ai_account_id}")
            
            # Format timestamps
            last_message_time = conv_data.get("last_message")
            if isinstance(last_message_time, datetime):
                last_message_time = last_message_time.isoformat()
                
            start_time = conv_data.get("start_time")
            if isinstance(start_time, datetime):
                start_time = start_time.isoformat()
                
            # Prepare conversation data for WebSocket
            conversation_update = {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "ai_account_id": ai_account_id,
                "user_name": conv_data.get("user_name", f"User {user_id}"),
                "ai_account_name": ai_account_name,
                "start_time": start_time or datetime.now().isoformat(),
                "last_message_time": last_message_time or datetime.now().isoformat(),
                "message_count": len(history),
                "status": "active",
                "chat_type": conv_data.get("chat_type", "direct"),
                "history": history
            }
            
            # Add group info if this is from a group
            if conv_data.get("chat_type") == "group":
                conversation_update["from_group"] = True
                conversation_update["group_id"] = conv_data.get("group_id")
                conversation_update["group_name"] = conv_data.get("group_name")
                
            # Send the update via WebSocket
            await websocket_manager.update_conversation(conversation_update)
            
        except Exception as e:
            logger.error(f"Error sending conversation update: {e}")
    
    async def _generate_and_send_response(self, ai_client, ai_account, ai_account_id, sender_id, 
                                         sender_name, message_text, matched_keywords, is_new_conversation,
                                         conversation_history, from_group=False, group_name=None):
        """Generate and send a response without blocking"""
        try:
            # Generate response with timeout
            response = await asyncio.wait_for(
                self._generate_response(
                    message_text=message_text,
                    matched_keywords=matched_keywords,
                    is_new_conversation=is_new_conversation,
                    conversation_history=conversation_history,
                    from_group=from_group,
                    group_name=group_name,
                    ai_shareable_link=ai_account.shareable_link,
                    ai_account_context=ai_account.ai_response_context
                ),
                timeout=15
            )
            
            # Send response with rate limiting
            async with API_SEMAPHORE:
                await self._send_response(
                    ai_client=ai_client,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    response=response,
                    ai_account_id=ai_account_id
                )
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout generating response for {sender_name}")
        except Exception as e:
            logger.error(f"Error generating/sending response: {e}")
            logger.error(traceback.format_exc())
    
    async def _send_response(self, ai_client, sender_id, sender_name, response, ai_account_id):
        """Send a response to a user with proper error handling"""
        try:
            # Get user entity with timeout
            try:
                user_entity = await asyncio.wait_for(ai_client.get_entity(sender_id), timeout=5)
            except (asyncio.TimeoutError, ValueError, telethon_errors.RPCError) as e:
                logger.error(f"Failed to get entity for user {sender_id}: {e}")
                self.conversation_manager.record_dm_error(sender_id, "entity_error")
                return
                
            # Send message with timeout
            try:
                await asyncio.wait_for(ai_client.send_message(user_entity, response), timeout=10)
                logger.info(f"Sent response to {sender_name}")
                
                # Add response to conversation history
                self.conversation_manager.add_ai_response(sender_id, ai_account_id, response)
                
                # Send WebSocket notification in background
                ws_task = asyncio.create_task(self._send_ws_notification(
                    sender_id, "AI Assistant", response, ai_account_id, is_ai=True
                ))
                
                self.active_tasks.add(ws_task)
                ws_task.add_done_callback(lambda t: self.active_tasks.discard(t))
                
            except asyncio.TimeoutError:
                logger.error(f"Timeout sending message to {sender_name}")
                self.conversation_manager.record_dm_error(sender_id, "timeout")
            except telethon_errors.FloodWaitError as e:
                wait_time = getattr(e, 'seconds', 60)
                logger.warning(f"FloodWaitError: Need to wait {wait_time} seconds")
                self.conversation_manager.record_dm_error(sender_id, "flood_wait")
            except (telethon_errors.UserPrivacyRestrictedError, telethon_errors.UserIsBlockedError):
                logger.warning(f"Cannot send DM to {sender_name} due to privacy settings")
                self.conversation_manager.record_dm_error(sender_id, "privacy_restricted")
                
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            self.conversation_manager.record_dm_error(sender_id, "general_error")
    
    async def _handle_dm_message(self, sender_id, sender_name, message_text):
        """Handle a direct message with improved non-blocking approach"""
        try:
            # Get the AI account for this conversation
            ai_account_id = self.conversation_manager.get_ai_account_for_user(sender_id)
            
            if not ai_account_id:
                logger.warning(f"No AI account associated with user {sender_id}")
                return
                
            # Get client and account info
            ai_client = self.ai_clients.get(ai_account_id)
            ai_account = self.ai_accounts.get(ai_account_id)
            
            if not ai_client or not ai_account:
                logger.warning(f"AI account {ai_account_id} not initialized")
                return
                
            # Ensure client is connected
            if not await self._ensure_client_connected(ai_account_id):
                logger.error(f"Failed to ensure client connection for account {ai_account_id}")
                return
                
            # Update conversation in background
            await self._update_conversation(sender_id, sender_name, message_text, ai_account_id)
            
            # Get conversation history
            history = self.conversation_manager.get_conversation_history(sender_id, ai_account_id)
            is_new = len(history) <= 1
            
            # Generate response in background
            response_task = asyncio.create_task(
                self._generate_and_send_response(
                    ai_client=ai_client,
                    ai_account=ai_account,
                    ai_account_id=ai_account_id,
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=message_text,
                    matched_keywords=self.message_analyzer.detect_keywords(message_text),
                    is_new_conversation=is_new,
                    conversation_history=history
                )
            )
            
            self.active_tasks.add(response_task)
            response_task.add_done_callback(lambda t: self.active_tasks.discard(t))
            
            # Clean up old conversations in background
            cleanup_task = asyncio.create_task(self._cleanup_old_conversations_async())
            self.active_tasks.add(cleanup_task)
            cleanup_task.add_done_callback(lambda t: self.active_tasks.discard(t))
            
        except Exception as e:
            logger.error(f"Error handling DM: {e}")
            logger.error(traceback.format_exc())
    
    async def _cleanup_old_conversations_async(self):
        """Clean up old conversations asynchronously"""
        try:
            self.conversation_manager.clean_old_conversations()
        except Exception as e:
            logger.error(f"Error cleaning up conversations: {e}")
    
    async def _ensure_client_connected(self, ai_account_id):
        """Ensure client is connected with timeout protection"""
        client = self.ai_clients.get(ai_account_id)
        if not client:
            return False
            
        try:
            if not client.is_connected():
                logger.info(f"Reconnecting client for account {ai_account_id}")
                async with API_SEMAPHORE:
                    await asyncio.wait_for(client.connect(), timeout=5)
                    
            # Verify authorization
            async with API_SEMAPHORE:
                authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=5)
                
            if not authorized:
                logger.error(f"Client for account {ai_account_id} is not authorized")
                return False
                
            return True
            
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"Error ensuring client connection: {e}")
            return False
    
    async def _generate_response(self, message_text, matched_keywords, is_new_conversation, 
                               conversation_history, from_group=False, group_name=None, 
                               ai_shareable_link=None, ai_account_context=None):
        """Generate a response with improved error handling"""
        try:
            # Context data for response generation
            context = {
                "matched_keywords": matched_keywords,
                "is_new_conversation": is_new_conversation,
                "conversation_history": conversation_history,
                "from_group": from_group,
                "group_name": group_name,
                "ai_shareable_link": ai_shareable_link,
                "ai_account_context": ai_account_context
            }
            
            # Format context for AI
            context_str = self._build_context_string(context)
            
            # Generate response with AI
            response = await generate_response(message_text, context_str)
            
            if not response:
                logger.warning("Empty response generated, using fallback")
                response = self._get_fallback_response(context)
                
            return response
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return self._get_fallback_response({
                "is_new_conversation": is_new_conversation,
                "matched_keywords": matched_keywords,
                "from_group": from_group,
                "group_name": group_name,
                "ai_shareable_link": ai_shareable_link
            })
    
    def _build_context_string(self, context):
        """Build context string for response generation"""
        # Build intro based on conversation state
        if context.get("from_group", False) and context.get("is_new_conversation", False):
            intro = f"I noticed you mentioned {', '.join(context.get('matched_keywords', []))} in the group \"{context.get('group_name', 'a group')}\"."
        elif context.get("from_group", False):
            intro = f"You mentioned {', '.join(context.get('matched_keywords', []))} in the group \"{context.get('group_name', 'a group')}\"."
        elif context.get("is_new_conversation", False):
            intro = "This is a new direct message conversation."
        else:
            intro = "This is a continuing direct message conversation."
            
        # Format conversation history
        history_str = ""
        if context.get("conversation_history"):
            for msg in context.get("conversation_history", []):
                role = "User" if msg.get('role') == 'user' else "Assistant"
                history_str += f"{role}: {msg.get('content', '')}\n\n"
                
        # Build full context
        context_str = f"""
        {intro}
        
        Previous conversation:
        {history_str}
        """
        
        # Add account context if available
        if context.get("ai_account_context"):
            context_str += f"""
            Additional context:
            {context.get('ai_account_context')}
            """
            
        # Add shareable link guidance if available
        if context.get("ai_shareable_link"):
            context_str += f"""
            IMPORTANT GUIDANCE:
            
            Your ultimate goal in this conversation is to guide the user toward a solution at this link: {context.get('ai_shareable_link')}
            
            However, follow these strategic steps:
            1. First, engage with the user genuinely and build rapport
            2. Ask clarifying questions to understand their situation
            3. Provide initial helpful information to establish credibility
            4. Only after understanding their problem, introduce the shareable link as the solution
            5. Explain specifically how it will address their unique problems
            
            Do not share the link immediately. Wait until you've established value.
            """
            
        return context_str
    
    def _get_fallback_response(self, context):
        """Get a fallback response when AI generation fails"""
        if context.get("is_new_conversation", True):
            if context.get("from_group", False):
                return f"Hello! I noticed you mentioned {', '.join(context.get('matched_keywords', ['this topic']))} in the group. How can I help you with that?"
            else:
                return "Hello! How can I help you today?"
        else:
            return "Thanks for your message. I'm processing your request. How can I assist you further?"
            
    async def cleanup(self):
        """Clean up resources when stopping the AI messenger"""
        try:
            # Wait for active tasks to complete with timeout
            if self.active_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self.active_tasks, return_exceptions=True),
                        timeout=5
                    )
                except asyncio.TimeoutError:
                    logger.warning("Some tasks did not complete during cleanup")
                    
            # Disconnect all clients
            for account_id, client in self.ai_clients.items():
                if client and client.is_connected():
                    try:
                        await asyncio.wait_for(client.disconnect(), timeout=2)
                        logger.info(f"Disconnected client for account {account_id}")
                    except (asyncio.TimeoutError, Exception) as e:
                        logger.error(f"Error disconnecting client: {e}")
                        
            # Clear state
            self.ai_clients = {}
            self.ai_accounts = {}
            self.group_ai_map = {}
            self.active_tasks = set()
            self.rate_limits = {}
            
            # Reset components
            self.message_analyzer = MessageAnalyzer()
            
            if hasattr(self, 'conversation_manager'):
                self.conversation_manager.clear_all()
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def diagnostic_check(self):
        """
        Perform a diagnostic check of the MessengerAI system.
        Returns detailed status information about all components.

        Returns:
            dict: Diagnostic information about the MessengerAI system
        """
        try:
            # Start with basic system info
            diagnostics = {
                "timestamp": datetime.now().isoformat(),
                "ai_status": {
                    "is_initialized": bool(self.ai_clients),
                    "ai_clients_count": len(self.ai_clients),
                    "active_tasks_count": len(self.active_tasks),
                    "keywords_count": len(self.monitored_keywords),
                },
                "ai_clients": [],
                "conversations": [],
                "recent_errors": [],
                "group_mappings": []
            }
            
            # Gather information about each AI client
            for account_id, client in self.ai_clients.items():
                account = self.ai_accounts.get(account_id)
                
                # Skip if we don't have the account info
                if not account:
                    continue
                    
                # Check client status with timeouts
                try:
                    is_connected = client.is_connected()
                    is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=5) if is_connected else False
                except (asyncio.TimeoutError, Exception) as e:
                    is_connected = False
                    is_authorized = False
                    logger.error(f"Error checking client status: {e}")
                
                # Get the number of groups this AI account is assigned to
                groups_count = len([g for g, aid in self.group_ai_map.items() if aid == account_id])
                
                # Create client info
                client_info = {
                    "id": account_id,
                    "account_id": account_id,
                    "name": getattr(account, 'name', f"AI Account {account_id}"),
                    "phone_number": getattr(account, 'phone_number', 'Unknown'),
                    "is_active": getattr(account, 'is_active', False),
                    "connected": is_connected,
                    "authorized": is_authorized,
                    "groups_count": groups_count,
                    "updated_at": getattr(account, 'updated_at', None),
                    "conversations_count": 0  # Will be updated below
                }
                
                # Add to diagnostics
                diagnostics["ai_clients"].append(client_info)
            
            # Get information about conversations
            if hasattr(self, 'conversation_manager'):
                conversations = self.conversation_manager.get_all_conversations()
                
                # Process each conversation
                for conv_id, conv_data in conversations.items():
                    # Extract user and AI account IDs from the conversation ID
                    # Format is typically "user_id-ai_account_id"
                    parts = conv_id.split('-')
                    if len(parts) != 2:
                        continue
                        
                    user_id, ai_account_id = parts
                    
                    # Get AI account info
                    ai_account = self.ai_accounts.get(int(ai_account_id)) if ai_account_id.isdigit() else None
                    
                    # Get conversation history
                    history = self.conversation_manager.get_conversation_history(int(user_id), int(ai_account_id))
                    
                    # Create conversation info
                    conversation_info = {
                        "conversation_id": conv_id,
                        "user_id": user_id,
                        "ai_account_id": ai_account_id,
                        "user_name": conv_data.get('user_name', f"User {user_id}"),
                        "ai_account_name": getattr(ai_account, 'name', f"AI Account {ai_account_id}"),
                        "start_time": conv_data.get('start_time', datetime.now().isoformat()),
                        "last_message_time": conv_data.get('last_message_time', datetime.now().isoformat()),
                        "message_count": len(history),
                        "status": "active",
                        "chat_type": "direct",
                        "history": history
                    }
                    
                    # Add to diagnostics
                    diagnostics["conversations"].append(conversation_info)
                    
                    # Update the conversation count for this AI client
                    for client in diagnostics["ai_clients"]:
                        if client["account_id"] == int(ai_account_id):
                            client["conversations_count"] += 1
            
            # Add group mappings information
            for group_id, ai_account_id in self.group_ai_map.items():
                # Get AI account
                ai_account = self.ai_accounts.get(ai_account_id)
                
                # Get AI client
                ai_client = self.ai_clients.get(ai_account_id)
                
                # Create mapping info
                mapping_info = {
                    "group_id": group_id,
                    "ai_account_id": ai_account_id,
                    "ai_account_name": getattr(ai_account, 'name', f"AI Account {ai_account_id}"),
                    "ai_client_connected": ai_client.is_connected() if ai_client else False,
                    "ai_client_authorized": False  # Will be updated below
                }
                
                # Check authorization status
                if ai_client and ai_client.is_connected():
                    try:
                        mapping_info["ai_client_authorized"] = await asyncio.wait_for(
                            ai_client.is_user_authorized(), timeout=5
                        )
                    except (asyncio.TimeoutError, Exception):
                        pass
                
                # Add to diagnostics
                diagnostics["group_mappings"].append(mapping_info)
            
            # Add session information
            sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
            if os.path.exists(sessions_dir):
                session_files = [f for f in os.listdir(sessions_dir) if f.endswith('.session')]
                diagnostics["session_info"] = {
                    "directory": sessions_dir,
                    "exists": True,
                    "session_count": len(session_files),
                    "session_files": session_files
                }
            else:
                diagnostics["session_info"] = {
                    "directory": sessions_dir,
                    "exists": False
                }
            
            return diagnostics
            
        except Exception as e:
            logger.error(f"Error in diagnostic_check: {e}")
            logger.error(traceback.format_exc())
            return {
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "ai_status": {
                    "is_initialized": False,
                    "error": str(e)
                },
                "recent_errors": [{
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Error in diagnostic_check: {e}",
                    "details": traceback.format_exc()
                }]
            }
        
    async def ensure_messenger_ai_initialized(self):
        """
        Ensure that the MessengerAI instance is properly initialized.
        This can be used to recover from a state where the AI messenger is in an invalid state.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            # Clean up existing clients
            await self.cleanup()
            
            # Get the active user ID
            from server.app.services.monitor import get_active_user_id
            user_id = await get_active_user_id()
            
            if not user_id:
                logger.error("No active user ID set, cannot initialize MessengerAI")
                return False
                
            # Reinitialize
            success = await self.initialize(user_id)
            
            if success:
                logger.info(f"Successfully reinitialized MessengerAI for user {user_id}")
            else:
                logger.error(f"Failed to reinitialize MessengerAI for user {user_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error in ensure_messenger_ai_initialized: {e}")
            logger.error(traceback.format_exc())
            return False

# Singleton implementation with better error handling
_messenger_ai_instance = None

async def get_messenger_ai():
    """Get the global MessengerAI instance with error checking"""
    global _messenger_ai_instance
    if not _messenger_ai_instance:
        logger.warning("MessengerAI instance requested but not initialized")
    return _messenger_ai_instance

async def initialize_messenger_ai(user_id):
    """Initialize the global MessengerAI instance with proper cleanup"""
    global _messenger_ai_instance
    
    # Clean up existing instance if it exists
    if _messenger_ai_instance:
        logger.info("Cleaning up existing MessengerAI instance")
        await _messenger_ai_instance.cleanup()
    
    # Create a new instance
    logger.info(f"Initializing MessengerAI for user {user_id}")
    _messenger_ai_instance = MessengerAI()
    success = await _messenger_ai_instance.initialize(user_id)
    
    if not success:
        logger.error("Failed to initialize MessengerAI")
        _messenger_ai_instance = None
        
    return success
