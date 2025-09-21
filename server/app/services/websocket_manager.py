from fastapi import WebSocket
from typing import Dict, Set, Any, Optional
import json
import asyncio
from server.app.core.logging import logger
from datetime import datetime
import pusher
from server.app.core.config import settings

class ConnectionManager:
    def __init__(self):
        logger.info(f"Initializing WebSocket Connection Manager")
        # Initialize Pusher client only if credentials are provided
        self.pusher_client = None
        if settings.PUSHER_APP_ID and settings.PUSHER_KEY and settings.PUSHER_SECRET:
            try:
                self.pusher_client = pusher.Pusher(
                    app_id=settings.PUSHER_APP_ID,
                    key=settings.PUSHER_KEY,
                    secret=settings.PUSHER_SECRET,
                    cluster=settings.PUSHER_CLUSTER,
                    ssl=True
                )
                logger.info("Pusher client initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Pusher client: {e}")
                self.pusher_client = None
        else:
            logger.info("Pusher credentials not provided, running without Pusher support")

        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.connection_user: Dict[str, str] = {}  # connection_id -> user_id
        self._lock = asyncio.Lock()
        
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: Optional[str] = None):
        """
        Connect a new WebSocket client and register it with a unique connection ID
        """
        try:
            await websocket.accept()
            self.active_connections[connection_id] = websocket
            
            if user_id:
                await self._add_user_connection(user_id, connection_id)
                
            logger.info(f"WebSocket connected: {connection_id}, user: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {e}", exc_info=True)
            return False
        
    async def disconnect(self, connection_id: str):
        """
        Disconnect a WebSocket client and clean up its registration
        """
        try:
            if connection_id in self.active_connections:
                # Don't need to close the WebSocket here - it's likely already closed
                # or will be closed by FastAPI
                self.active_connections.pop(connection_id)
                
                # Remove from user connections if applicable
                if connection_id in self.connection_user:
                    user_id = self.connection_user[connection_id]
                    
                    async with self._lock:
                        if user_id in self.user_connections:
                            self.user_connections[user_id].discard(connection_id)
                            if not self.user_connections[user_id]:
                                del self.user_connections[user_id]
                                
                        del self.connection_user[connection_id]
                        
                logger.info(f"WebSocket disconnected: {connection_id}")
                return True
            else:
                logger.warning(f"Attempted to disconnect non-existent WebSocket: {connection_id}")
                return False
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket {connection_id}: {e}", exc_info=True)
            return False
    
    async def _add_user_connection(self, user_id: str, connection_id: str):
        async with self._lock:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            self.connection_user[connection_id] = user_id
    
    async def send_personal_message(self, message: str, connection_id: str):
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(message)
    
    async def send_to_user(self, user_id: str, message: str):
        if user_id in self.user_connections:
            for connection_id in list(self.user_connections[user_id]):
                await self.send_personal_message(message, connection_id)
    
    async def broadcast(self, message: str):
        for connection_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, connection_id)
    
    async def send_json(self, connection_id: str, data: dict):
        """
        Send a JSON message to a specific WebSocket connection
        """
        try:
            if connection_id not in self.active_connections:
                logger.warning(f"Attempted to send message to non-existent connection: {connection_id}")
                return False
                
            # Convert the data to a JSON string
            message = json.dumps(data)
            
            # Get the WebSocket connection
            websocket = self.active_connections[connection_id]
            
            # Send the message
            await websocket.send_text(message)
            return True
        except Exception as e:
            logger.error(f"Error sending JSON via WebSocket {connection_id}: {e}", exc_info=True)
            
            # If the error suggests the connection is dead, clean it up
            if "connection is closed" in str(e).lower() or "disconnected" in str(e).lower():
                logger.info(f"Connection appears to be closed, cleaning up: {connection_id}")
                await self.disconnect(connection_id)
            
            return False
    
    async def send_json_to_user(self, user_id: str, data: dict):
        try:
            message = json.dumps(data)
            await self.send_to_user(user_id, message)
        except Exception as e:
            logger.error(f"Error sending JSON to user via WebSocket: {e}")
    
    async def broadcast_json(self, data: dict):
        """
        Broadcast a JSON message to all connected WebSocket clients
        """
        try:
            if not self.active_connections:
                logger.debug("No active connections for broadcast")
                return
                
            # Convert the data to a JSON string
            message = json.dumps(data)
            
            # Store connection IDs that failed so we can clean them up after the broadcast
            failed_connections = []
            
            # Send to all connections
            for connection_id, websocket in list(self.active_connections.items()):
                try:
                    await websocket.send_text(message)
                except Exception as e:
                    logger.error(f"Failed to send to connection {connection_id}: {e}")
                    failed_connections.append(connection_id)
            
            # Clean up failed connections
            for connection_id in failed_connections:
                await self.disconnect(connection_id)
                
            if failed_connections:
                logger.info(f"Cleaned up {len(failed_connections)} failed connections during broadcast")
                
            return True
        except Exception as e:
            logger.error(f"Error broadcasting JSON: {e}", exc_info=True)
            return False
    
    async def send_notification(self, event_type: str, message: str, level: str = "info", details: Any = None):
        """Send a notification to all connected clients"""
        notification = {
            "type": "notification",
            "event": event_type,
            "message": message,
            "level": level,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        await self.broadcast_json(notification)
    
    def get_connection_count(self) -> int:
        """Get the count of active connections"""
        return len(self.active_connections)
        
    def get_user_count(self) -> int:
        """Get the count of users with active connections"""
        return len(self.user_connections)
    
    async def update_diagnostics(self, diagnostics_data: dict):
        """Send updated diagnostics to all connected clients"""
        try:
            # Ensure diagnostics_data is a valid dictionary
            if not isinstance(diagnostics_data, dict):
                logger.error(f"Invalid diagnostics data type: {type(diagnostics_data)}")
                return
                
            # Always add a timestamp if it doesn't exist
            if "timestamp" not in diagnostics_data:
                diagnostics_data["timestamp"] = datetime.now().isoformat()
                
            # Add connection information
            if "websocket_info" not in diagnostics_data:
                diagnostics_data["websocket_info"] = {}
                
            diagnostics_data["websocket_info"].update({
                "active_connections": self.get_connection_count(),
                "connected_users": self.get_user_count(),
                "last_update": datetime.now().isoformat()
            })
                
            message = {
                "type": "diagnostics_update",
                "data": diagnostics_data,
                "timestamp": datetime.now().isoformat()
            }
            
            # Use Pusher to broadcast diagnostics - send just the data for better frontend compatibility
            if self.pusher_client:
                self.pusher_client.trigger('diagnostics', 'diagnostics_update', diagnostics_data)
            
            # Fallback to WebSockets if needed - include the full message structure
            if self.active_connections:
                await self.broadcast_json(message)
                logger.debug(f"Broadcasting diagnostics update to {len(self.active_connections)} connections")
            else:
                logger.debug("No active WebSocket connections for diagnostics update")
        except Exception as e:
            logger.error(f"Error broadcasting diagnostics update: {e}", exc_info=True)
        
    async def add_chat_message(self, message_data: dict):
        """Add a new chat message to the real-time activity monitor"""
        data = {
            "type": "chat_message",
            "data": message_data
        }
        # Use Pusher with public channels
        if self.pusher_client:
            self.pusher_client.trigger('chat', 'new_message', data)
        # Fallback to WebSockets if needed
        if self.active_connections:
            await self.broadcast_json(data)


    
    async def update_conversation(self, conversation_data):
        """Send updated conversation data to all connected clients"""
        # Ensure the conversation has an ID
        if not conversation_data.get('conversation_id'):
            logger.error(f"Attempted to send conversation update without conversation_id: {conversation_data}")
            return
            
        # Make sure we have timestamps for all messages
        if 'history' in conversation_data and isinstance(conversation_data['history'], list):
            for msg in conversation_data['history']:
                if not msg.get('timestamp'):
                    msg['timestamp'] = datetime.now().isoformat()
    
        # Always ensure chat_type is set
        if 'chat_type' not in conversation_data:
            conversation_data['chat_type'] = 'direct'
    
        # Prepare the message
        message = {
            "type": "conversation_update",
            "data": conversation_data
        }
        
        # Log the update
        logger.info(f"Sending conversation update for {conversation_data.get('conversation_id')} (type: {conversation_data.get('chat_type', 'direct')})")
        
        # Use Pusher with public channels
        if self.pusher_client:
            self.pusher_client.trigger('diagnostics', 'conversation_update', conversation_data)
        
        # Fallback to WebSockets if needed
        if self.active_connections:
            await self.broadcast_json(message)
    
    # Add the broadcast_health method to your WebSocketManager class
    async def broadcast_health(self, health_data):
        """
        Broadcast health status data to all connected clients.
        
        Args:
            health_data: The health status data to broadcast
        """
        if not self.active_connections:
            return
            
        message = {
            "type": "health_update",
            "data": health_data,
            "timestamp": datetime.now().isoformat()
        }
        
        await self.broadcast(message)

# Create a singleton instance
websocket_manager = ConnectionManager()