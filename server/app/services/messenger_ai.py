import asyncio
import os
from datetime import datetime, timedelta
from telethon import TelegramClient, errors as telethon_errors, events
from server.app.core.logging import logger
from server.app.core.databases import db_context, AsyncSessionLocal
from server.app.models.models import AIAccount, Group, GroupAIAccount
from sqlalchemy import select, and_
from server.app.services.ai_engine import generate_response, analyze_message
from server.app.utils.db_helpers import get_user_selected_groups
from server.app.utils.group_helpers import get_group_ai_mappings
from server.app.services.message_analyzer import MessageAnalyzer
from server.app.services.conversation_manager import ConversationManager
from server.app.services.websocket_manager import websocket_manager
import traceback
        

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
        
        # Track monitored keywords
        self.monitored_keywords = set()
        
        # Store conversations
        self.conversations = {}
        
    async def load_group_ai_mappings(self, user_id):
        """
        Load group-to-AI account mappings from the database.
        """

        return await get_user_selected_groups(user_id)

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
            # Clean up any existing clients first to avoid resource conflicts
            await self.cleanup()
            
            # Initialize empty dictionaries
            self.ai_clients = {}
            self.ai_accounts = {}
            self.group_ai_map = {}
            
            # Initialize new components
            self.message_analyzer = MessageAnalyzer()
            self.conversation_manager = ConversationManager()
            
            # Load user's keywords
            from server.app.utils.db_helpers import get_user_keywords
            keywords = await get_user_keywords(user_id)
            self.message_analyzer.set_keywords(keywords)
            
            # Get all active AI accounts for this user
            async with AsyncSessionLocal() as session:
                # Query active AI accounts
                stmt = select(AIAccount).where(AIAccount.user_id == user_id, AIAccount.is_active == True)
                result = await session.execute(stmt)
                ai_accounts = result.scalars().all()
                
                if not ai_accounts:
                    logger.warning(f"No active AI accounts found for user {user_id}")
                    return False
                
                # Initialize each AI account with its own client
                success_count = 0
                # Create session directory for AI accounts
                import os
                sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
                os.makedirs(sessions_dir, exist_ok=True)
                
                for ai_account in ai_accounts:
                    # Create a new Telethon client for this AI account
                    session_path = os.path.join(sessions_dir, f"ai_account_{ai_account.id}")
                    client = TelegramClient(
                        session_path,
                        api_id=ai_account.api_id,
                        api_hash=ai_account.api_hash
                    )
                    
                    # Connect and verify authorization
                    await client.connect()
                    if await client.is_user_authorized():
                        # Store the client and account info
                        self.ai_clients[ai_account.id] = client
                        self.ai_accounts[ai_account.id] = ai_account
                        success_count += 1
                        logger.info(f"AI account {ai_account.id} initialized successfully")
                        
                        # Set up event handler for this AI client to listen for DM replies
                        @client.on(events.NewMessage(incoming=True))
                        async def handle_ai_dm_reply(event):
                            try:
                                message = event.message
                                chat_id = str(message.chat_id)
                                
                                # Only handle direct messages (not groups)
                                try:
                                    chat = await event.get_chat()
                                    chat_title = getattr(chat, 'title', None)
                                    if chat_title:  # Skip if it's a group/channel
                                        return
                                except:
                                    pass
                                
                                # Skip if no text
                                if not hasattr(message, 'text') or not message.text:
                                    return
                                
                                # Get sender info
                                try:
                                    sender = await event.get_sender()
                                    first_name = getattr(sender, 'first_name', '')
                                    last_name = getattr(sender, 'last_name', '')
                                    sender_name = f"{first_name} {last_name}".strip() or f"User {sender.id}"
                                    sender_id = sender.id
                                except Exception as e:
                                    logger.error(f"Error getting sender info in AI DM handler: {e}")
                                    return
                                
                                logger.info(f"AI account {ai_account.id} received DM reply from {sender_name} (ID: {sender_id})")
                                
                                # Handle this as a DM message
                                await self._handle_dm_message(
                                    sender_id=sender_id,
                                    sender_name=sender_name,
                                    message_text=message.text
                                )
                                
                            except Exception as e:
                                logger.error(f"Error handling AI DM reply: {e}")
                                logger.error(f"Traceback: {traceback.format_exc()}")
                        
                    else:
                        logger.error(f"AI account {ai_account.id} is not authorized")
                        await client.disconnect()
                
                # Now load the group-to-AI account mappings
                if success_count > 0:
                    try:
                        # Use our helper function to get mappings
                        group_mappings = await get_group_ai_mappings(user_id)
                        self.group_ai_map = group_mappings
                        # Convert to the format needed for self.group_ai_map
                        for group_id, mapping_info in group_mappings.items():
                            self.group_ai_map[group_id] = mapping_info['ai_account_id']
                            logger.debug(f"Added mapping: Group {mapping_info['group_name']} (ID: {group_id}) -> AI account {mapping_info['ai_account_id']}")
                        
                        # Diagnostic logging
                        if self.group_ai_map:
                            logger.info(f"Loaded {len(self.group_ai_map)} group-AI mappings for user {user_id}")
                            logger.debug(f"Group-AI mappings: {self.group_ai_map}")
                        else:
                            logger.warning(f"No group-AI mappings found for user {user_id}. AI will not respond to any messages.")
                    except Exception as e:
                        logger.error(f"Error loading group-AI mappings: {e}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        # Continue with initialization even if mappings fail
                
                return success_count > 0
                
        except Exception as e:
            logger.error(f"Error initializing AI messenger: {e}")
            # Clean up any connected clients
            for _, client in self.ai_clients.items():
                if client and client.is_connected():
                    await client.disconnect()
            
            self.ai_clients = {}
            self.ai_accounts = {}
            self.group_ai_map = {}
            return False

    async def handle_message(self, message_data):
        """
        Process a new message and decide if/how to respond.
        
        For group messages:
        - Only respond if the message contains keywords
        - Send response via DM to the user, not in the group
        
        For DM messages:
        - Continue existing conversations regardless of keywords
        
        Args:
            message_data: Dictionary containing message information
        """
        try:
            chat_id = message_data.get('chat_id')
            message_id = message_data.get('message_id')
            chat_title = message_data.get('chat_title')
            sender_name = message_data.get('sender_name', 'Unknown User')
            sender_id = message_data.get('sender_id')
            message_text = message_data.get('text')
            
            # Validate required fields are present
            if not chat_id or not message_text or not sender_id:
                logger.error(f"Missing required fields in message data: chat_id={chat_id}, sender_id={sender_id}")
                return
            
            # Ensure chat_id is a string for dictionary lookup
            str_chat_id = str(chat_id)
            short_chat_id = str_chat_id.replace('-100', '')
            
            # Determine if this is a group message or a direct message
            is_group_message = bool(chat_title)  # Groups and channels have titles, private chats don't
            
            # Handle differently based on message source
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
                # This is a direct message
                await self._handle_dm_message(
                    sender_id=sender_id,
                    sender_name=sender_name,
                    message_text=message_text
                )
                
        except Exception as e:
            logger.error(f"Error handling message with AI: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
    async def _handle_group_message(self, chat_id, chat_title, sender_id, sender_name, message_text, message_id):
        """
        Handle a message from a group chat.
        Only respond if the message contains keywords, and send the response via DM.
        
        Args:
            chat_id: The group chat ID
            chat_title: The title of the group chat
            sender_id: The ID of the message sender
            sender_name: The name of the message sender
            message_text: The text content of the message
            message_id: The ID of the message
        """
        logger.debug(f"Processing group message from {sender_name} in {chat_title}")
        
        # First, check if this message contains any keywords
        analysis = await self.message_analyzer.should_respond(message_text)
        if not analysis["should_respond"]:
            logger.debug(f"No keywords matched in message from {sender_name} in {chat_title}, ignoring")
            return
            
        matched_keywords = analysis["matched_keywords"]
        logger.info(f"Message from {sender_name} in {chat_title} matched keywords: {matched_keywords}")
        
        # Find the appropriate AI account for this group
        str_chat_id = str(chat_id)
        short_chat_id = str_chat_id.replace('-100', '')
        
        # Try both formats of the chat ID in the mapping
        ai_account_id = None
        if str_chat_id in self.group_ai_map:
            ai_account_id = self.group_ai_map.get(str_chat_id)
        elif short_chat_id in self.group_ai_map:
            ai_account_id = self.group_ai_map.get(short_chat_id)
        
        if not ai_account_id:
            logger.warning(f"No AI account mapped to group {chat_id}, cannot respond")
            return
        
        # Get the client for this AI account
        ai_client = self.ai_clients.get(ai_account_id)
        ai_account = self.ai_accounts.get(ai_account_id)
        
        if not ai_client or not ai_account:
            logger.warning(f"AI account {ai_account_id} not initialized, cannot respond")
            return
            
        # Verify client is connected
        if not ai_client.is_connected():
            try:
                await ai_client.connect()
                if not await ai_client.is_user_authorized():
                    logger.error(f"AI client for account {ai_account_id} is not authorized")
                    return
            except Exception as e:
                logger.error(f"Failed to connect AI client for account {ai_account_id}: {e}")
                return
        
        # Check if we can send a DM to this user
        if not self.conversation_manager.can_send_dm(sender_id):
            logger.warning(f"Not sending DM to user {sender_id} due to previous errors")
            return
        
        # Create or update the conversation
        is_new_conversation = self.conversation_manager.is_new_conversation(sender_id, ai_account_id)
        
        # Add this message to the conversation history
        self.conversation_manager.add_user_message(
            user_id=sender_id,
            message_text=message_text,
            ai_account_id=ai_account_id,
            sender_name=sender_name
        )
        
        # Get updated conversation history
        conversation_history = self.conversation_manager.get_conversation_history(sender_id, ai_account_id)
        
        # Generate a response
        try:
            response = await self._generate_response(
                message_text=message_text,
                matched_keywords=matched_keywords,
                is_new_conversation=is_new_conversation,
                conversation_history=conversation_history,
                from_group=True,
                group_name=chat_title
            )
            
            # Send the response directly to the user, not in the group
            try:
                # First, try to get the user entity to ensure we can message them
                try:
                    # Get the user entity (this will ensure we can message them)
                    user_entity = await ai_client.get_entity(sender_id)
                    logger.debug(f"Retrieved user entity for {sender_name} (ID: {sender_id})")
                except ValueError:
                    # If we can't get the entity, try looking up by username if available
                    logger.warning(f"Could not get entity for user {sender_id} directly, trying alternative methods")
                    # Try to get the user from the group member list
                    try:
                        # Get the chat entity (the group)
                        chat_entity = await ai_client.get_entity(int(chat_id))
                        # Get all the participants in the group
                        participants = await ai_client.get_participants(chat_entity)
                        # Find the user in the participants
                        user_entity = next((p for p in participants if p.id == sender_id), None)
                        if not user_entity:
                            raise ValueError(f"User {sender_id} not found in group participants")
                        logger.info(f"Found user {sender_name} (ID: {sender_id}) in group participants")
                    except Exception as e:
                        logger.error(f"Failed to get user from group participants: {e}")
                        self.conversation_manager.record_dm_error(sender_id, "entity_not_found")
                        return
                
                # Now send the message
                await ai_client.send_message(user_entity, response)
                logger.info(f"Sent AI response via DM to {sender_name} using account {ai_account_id}")
                
                # Add the response to the conversation history
                self.conversation_manager.add_ai_response(sender_id, ai_account_id, response)
                
                # Update WebSocket clients with conversation data
                try:
                    # Get the updated conversation history
                    conversation_history = self.conversation_manager.get_conversation_history(sender_id, ai_account_id)
                    conversation_id = f"convo_{sender_id}_{ai_account_id}"
                    
                    # Create conversation data for WebSocket
                    conversation_data = {
                        "id" : conversation_id,
                        "user_id": sender_id,
                        "sender_name": sender_name,
                        "ai_account_id": ai_account_id,
                        "ai_account_name": self.ai_accounts[ai_account_id].name if ai_account_id in self.ai_accounts else "Unknown",
                        "last_updated": datetime.now().isoformat(),
                        "history": conversation_history,
                        "message_count": len(conversation_history)
                    }
                    
                    # Send to WebSocket clients
                    asyncio.create_task(websocket_manager.update_conversation(conversation_data))
                except Exception as e:
                    logger.error(f"Error updating WebSocket with conversation data: {e}")
                
            except telethon_errors.FloodWaitError as e:
                wait_time = getattr(e, 'seconds', 60)
                logger.warning(f"FloodWaitError: Need to wait {wait_time} seconds before sending more messages")
                self.conversation_manager.record_dm_error(sender_id, "flood_wait")
                
            except (telethon_errors.UserPrivacyRestrictedError, telethon_errors.UserIsBlockedError):
                logger.warning(f"Cannot send DM to {sender_name} (ID: {sender_id}) due to privacy settings or block")
                self.conversation_manager.record_dm_error(sender_id, "privacy_restricted")
                
            except Exception as e:
                logger.error(f"Failed to send DM to {sender_name} (ID: {sender_id}): {e}")
                self.conversation_manager.record_dm_error(sender_id, "general_error")
                
        except Exception as e:
            logger.error(f"Error generating response for {sender_name}: {e}")
            
    async def _handle_dm_message(self, sender_id, sender_name, message_text):
        """
        Handle a direct message from a user.
        Continue the conversation regardless of keywords.
        
        Args:
            sender_id: The ID of the message sender
            sender_name: The name of the message sender
            message_text: The text content of the message
        """
        logger.debug(f"Processing DM from {sender_name}")
        
        # Get the AI account associated with this user's conversation
        ai_account_id = self.conversation_manager.get_ai_account_for_user(sender_id)
        
        # If no AI account is associated, try to use any available AI account
        if not ai_account_id:
            logger.info(f"No existing AI account associated with user {sender_id}, trying to assign one")
            
            # Use the first available AI account
            if self.ai_clients:
                ai_account_id = list(self.ai_clients.keys())[0]
                logger.info(f"Assigned AI account {ai_account_id} to handle DM from user {sender_id}")
                
                # Create a new conversation with this AI account
                self.conversation_manager.get_or_create_conversation(sender_id, ai_account_id)
            else:
                logger.warning(f"No AI accounts available to respond to DM from user {sender_id}")
                return
        
        # Get the client for this AI account
        ai_client = self.ai_clients.get(ai_account_id)
        if not ai_client:
            logger.warning(f"AI client {ai_account_id} not found, cannot respond to DM")
            return
            
        # Verify client is connected
        if not ai_client.is_connected():
            try:
                await ai_client.connect()
                if not await ai_client.is_user_authorized():
                    logger.error(f"AI client for account {ai_account_id} is not authorized")
                    return
            except Exception as e:
                logger.error(f"Failed to connect AI client for account {ai_account_id}: {e}")
                return
        
        # Add user message to conversation history
        self.conversation_manager.add_user_message(
            user_id=sender_id, 
            message_text=message_text,
            ai_account_id=ai_account_id,
            sender_name=sender_name
        )
        
        # Get conversation history
        conversation_history = self.conversation_manager.get_conversation_history(sender_id, ai_account_id)
        is_new_conversation = len(conversation_history) <= 1  # Should be false for DMs
        
        # Generate and send a response
        try:
            # Get any keywords that match in this message (just for context)
            matched_keywords = self.message_analyzer.detect_keywords(message_text)
            
            # If this is a brand new conversation with no prior context, use a generic greeting
            if is_new_conversation and not matched_keywords:
                matched_keywords = ["assistance"]
            
            response = await self._generate_response(
                message_text=message_text,
                matched_keywords=matched_keywords,
                is_new_conversation=is_new_conversation,
                conversation_history=conversation_history,
                from_group=False
            )
            
            # Send the response
            try:
                # First, try to get the user entity to ensure we can message them
                try:
                    user_entity = await ai_client.get_entity(sender_id)
                    logger.debug(f"Retrieved user entity for DM from {sender_name} (ID: {sender_id})")
                except ValueError as e:
                    logger.error(f"Could not get entity for user {sender_id} in DM: {e}")
                    self.conversation_manager.record_dm_error(sender_id, "entity_not_found")
                    return
                
                # Now send the message
                await ai_client.send_message(user_entity, response)
                logger.info(f"Sent AI response to DM from {sender_name}")
                
                # Add the response to the conversation history
                self.conversation_manager.add_ai_response(sender_id, ai_account_id, response)
                
            except Exception as e:
                logger.error(f"Failed to send DM response to {sender_name}: {e}")
                self.conversation_manager.record_dm_error(sender_id, "general_error")
                
        except Exception as e:
            logger.error(f"Error generating DM response for {sender_name}: {e}")
            
        # Clean up old conversations
        self.conversation_manager.clean_old_conversations()
            
    async def _generate_response(self, message_text, matched_keywords, is_new_conversation, conversation_history, from_group=False, group_name=None):
        """
        Generate a response based on the message text, matched keywords, and conversation history.
        
        Args:
            message_text: The text of the message
            matched_keywords: List of keywords that matched in the message
            is_new_conversation: Whether this is a new conversation
            conversation_history: List of previous messages in this conversation
            from_group: Whether this message originated in a group
            group_name: The name of the group (if from_group is True)
            
        Returns:
            str: The generated response text, or None if no response should be sent
        """
        try:
            # First, analyze the message to understand its content and intent
            logger.debug(f"Analyzing message: '{message_text[:50]}...' with keywords: {matched_keywords}")
            analysis = await analyze_message(message_text)
            
            # Create context based on the message analysis and matched keywords
            context = {
                "keywords": matched_keywords,
                "is_new_conversation": is_new_conversation,
                "sentiment": analysis.get("sentiment", "neutral"),
                "category": analysis.get("category", "general_chat"),
                "urgency": analysis.get("urgency", False),
                "conversation_length": len(conversation_history),
                "from_group": from_group,
                "group_name": group_name
            }
            
            # Format conversation history for the AI
            conversation_str = ""
            if conversation_history:
                for msg in conversation_history:
                    role = "User" if msg['role'] == 'user' else "Assistant"
                    conversation_str += f"{role}: {msg['content']}\n\n"
            
            # Build context string with different prompts based on message source
            if from_group and is_new_conversation:
                context_intro = f"""
                I noticed you mentioned {', '.join(matched_keywords)} in the group "{group_name}".
                I'm messaging you directly to have a more personal conversation about this.
                """
            elif from_group:
                context_intro = f"""
                You mentioned {', '.join(matched_keywords)} in the group "{group_name}".
                """
            elif is_new_conversation:
                context_intro = f"""
                This is a new direct message conversation.
                """
            else:
                context_intro = f"""
                This is a continuing direct message conversation.
                """
                
            context_str = f"""
            {context_intro}
            Message sentiment: {context['sentiment']}
            Message category: {context['category']}
            Message urgency: {'Yes' if context['urgency'] else 'No'}
            
            Previous conversation:
            {conversation_str}
            """
            
            # Generate an appropriate response using the AI engine
            logger.debug(f"Generating response with context: {context_str[:100]}...")
            response = await generate_response(message_text, context_str)
            
            if response:
                logger.debug(f"Generated response: '{response[:50]}...'")
            else:
                logger.warning(f"Empty response generated for message with keywords: {matched_keywords}")
                # Provide a fallback response
                if from_group and is_new_conversation:
                    response = f"I noticed you mentioned {', '.join(matched_keywords)} in the group. I've messaged you directly to chat about this. How can I help?"
                elif from_group:
                    response = f"Regarding your mention of {', '.join(matched_keywords)} in the group, let me help you with that."
                elif is_new_conversation and matched_keywords == ["assistance"]:
                    response = f"Hello! I'm your AI assistant. How can I help you today?"
                else:
                    response = f"I noticed you mentioned {', '.join(matched_keywords)}. Let me help you with that."
                
            return response
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Fallback to simple response if AI generation fails
            if is_new_conversation:
                # Initial greeting for new conversations
                if from_group:
                    return (f"Hello! I noticed you mentioned {', '.join(matched_keywords)} in the group. "
                           f"I'm messaging you directly to chat about this. How can I help?")
                elif matched_keywords == ["assistance"]:
                    return "Hello! I'm your AI assistant. How can I help you today?"
                else:
                    return (f"Hello! I noticed you mentioned {', '.join(matched_keywords)}. "
                           f"I'd be happy to chat about that. How can I help you?")
            else:
                # Continue existing conversation
                return f"Thanks for your message. I see you're still interested in {', '.join(matched_keywords)}."
    
    def _cleanup_old_conversations(self):
        """
        Remove old conversations to free up memory.
        This is a legacy method kept for compatibility.
        Now it delegates to the ConversationManager.
        """
        if hasattr(self, 'conversation_manager'):
            self.conversation_manager.clean_old_conversations()
    
    async def cleanup(self):
        """
        Clean up resources when stopping the AI messenger.
        """
        # Disconnect all active clients
        for account_id, client in self.ai_clients.items():
            if client and client.is_connected():
                try:
                    await client.disconnect()
                    logger.info(f"AI messenger client for account {account_id} disconnected")
                except Exception as e:
                    logger.error(f"Error disconnecting client for account {account_id}: {e}")
        
        # Clear all internal state
        self.ai_clients = {}
        self.ai_accounts = {}
        self.group_ai_map = {}
        
        # Reset message analyzer and conversation manager
        if hasattr(self, 'message_analyzer'):
            self.message_analyzer = MessageAnalyzer()
            
        if hasattr(self, 'conversation_manager'):
            self.conversation_manager.clear_all()
        
    async def diagnostic_check(self):
        """
        Perform a diagnostic check of the AI messenger.
        Returns a dictionary with diagnostic information.
        """
        results = {
            "ai_clients": [],
            "group_mappings": [],
            "status": "unknown"
        }
        
        try:
            # Check AI clients
            for account_id, client in self.ai_clients.items():
                client_info = {
                    "account_id": account_id,
                    "connected": False,
                    "authorized": False,
                    "account_name": self.ai_accounts.get(account_id, {}).get("name", "Unknown")
                }
                
                if client:
                    try:
                        client_info["connected"] = client.is_connected()
                        if client_info["connected"]:
                            client_info["authorized"] = await client.is_user_authorized()
                    except Exception as e:
                        logger.error(f"Error checking client status for account {account_id}: {e}")
                
                results["ai_clients"].append(client_info)
            
            # Check group mappings
            for group_id, ai_account_id in self.group_ai_map.items():
                mapping_info = {
                    "group_id": group_id,
                    "ai_account_id": ai_account_id,
                    "ai_client_available": ai_account_id in self.ai_clients,
                    "ai_client_connected": False,
                    "ai_client_authorized": False
                }
                
                client = self.ai_clients.get(ai_account_id)
                if client:
                    try:
                        mapping_info["ai_client_connected"] = client.is_connected()
                        if mapping_info["ai_client_connected"]:
                            mapping_info["ai_client_authorized"] = await client.is_user_authorized()
                    except Exception as e:
                        logger.error(f"Error checking client status for mapping {group_id} -> {ai_account_id}: {e}")
                
                results["group_mappings"].append(mapping_info)
            
            # Determine overall status
            if not self.ai_clients:
                results["status"] = "no_clients"
            elif not self.group_ai_map:
                results["status"] = "no_mappings"
            elif all(client_info["connected"] and client_info["authorized"] for client_info in results["ai_clients"]):
                results["status"] = "ready"
            else:
                results["status"] = "partial"
                
            return results
        
        except Exception as e:
            logger.error(f"Error performing diagnostic check: {e}")
            results["status"] = "error"
            results["error"] = str(e)
            return results
        
    def get_active_conversations(self):
        """
        Get information about all active conversations.
        Returns a list of conversation information dictionaries.
        """
        conversations = []
        
        for user_id, conv_data in self.conversations.items():
            try:
                conversation = {
                    "conversation_id": str(user_id),
                    "user_id": user_id,
                    "user_name": conv_data.get("user_name", f"User {user_id}"),
                    "start_time": conv_data.get("start_time", ""),
                    "last_message_time": conv_data.get("last_update_time", ""),
                    "message_count": len(conv_data.get("messages", [])),
                    "chat_type": "Direct Message",
                    "status": "active" if (datetime.now() - datetime.fromisoformat(conv_data.get("last_update_time", datetime.now().isoformat()))).total_seconds() < 3600 else "inactive"
                }
                conversations.append(conversation)
            except Exception as e:
                logger.error(f"Error getting conversation info for user {user_id}: {e}")
        
        return conversations
        
    def get_clients_info(self):
        """
        Get information about AI clients
        """
        return {
            "connected_clients": [ai_id for ai_id, client in self.ai_clients.items() if client and client.is_connected()],
            "active_listeners": len(self.ai_clients),
            "total_accounts": len(self.ai_accounts)
        }
        
    def get_monitored_groups_info(self):
        """
        Get information about monitored groups
        """
        return {
            "groups": list(self.group_ai_map.keys()),
            "keywords_count": len(self.monitored_keywords)
        }

    async def _update_conversation_status(self, user_id, update_type="update"):
        """
        Update the WebSocket clients about a conversation update
        """
        try:
            
            
            if update_type == "new" or update_type == "update":
                # Get the conversation data
                if user_id in self.conversations:
                    conv_data = self.conversations[user_id]
                    conversation = {
                        "conversation_id": str(user_id),
                        "user_id": user_id,
                        "user_name": conv_data.get("user_name", f"User {user_id}"),
                        "start_time": conv_data.get("start_time", ""),
                        "last_message_time": conv_data.get("last_update_time", ""),
                        "message_count": len(conv_data.get("messages", [])),
                        "chat_type": "Direct Message",
                        "status": "active"
                    }
                    
                    # Send the update
                    await websocket_manager.update_conversation(conversation)
            
        except Exception as e:
            logger.error(f"Error updating conversation status via WebSocket: {e}")
            logger.error(traceback.format_exc())


# This is a singleton instance of the MessengerAI class
_messenger_ai_instance = None

async def get_messenger_ai():
    """
    Get the global MessengerAI instance.
    If no instance exists, returns None.
    """
    global _messenger_ai_instance
    return _messenger_ai_instance

async def initialize_messenger_ai(user_id):
    """
    Initialize the global MessengerAI instance for a specific user.
    """
    global _messenger_ai_instance
    
    # Clean up existing instance if it exists
    if _messenger_ai_instance:
        await _messenger_ai_instance.cleanup()
    
    # Create a new instance
    _messenger_ai_instance = MessengerAI()
    success = await _messenger_ai_instance.initialize(user_id)
    
    if not success:
        _messenger_ai_instance = None
        
    return success
