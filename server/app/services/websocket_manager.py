from fastapi import WebSocket
from typing import Dict, List, Set, Any, Optional
import json
import asyncio
from server.app.core.logging import logger
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.connection_user: Dict[str, str] = {}  # connection_id -> user_id
        self._lock = asyncio.Lock()
        
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        if user_id:
            await self._add_user_connection(user_id, connection_id)
            
        logger.info(f"WebSocket connected: {connection_id}, user: {user_id}")
        
    async def disconnect(self, connection_id: str):
        if connection_id in self.active_connections:
            websocket = self.active_connections.pop(connection_id)
            
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
        try:
            message = json.dumps(data)
            await self.send_personal_message(message, connection_id)
        except Exception as e:
            logger.error(f"Error sending JSON via WebSocket: {e}")
    
    async def send_json_to_user(self, user_id: str, data: dict):
        try:
            message = json.dumps(data)
            await self.send_to_user(user_id, message)
        except Exception as e:
            logger.error(f"Error sending JSON to user via WebSocket: {e}")
    
    async def broadcast_json(self, data: dict):
        try:
            message = json.dumps(data)
            await self.broadcast(message)
        except Exception as e:
            logger.error(f"Error broadcasting JSON via WebSocket: {e}")
    
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
        message = {
            "type": "diagnostics_update",
            "data": diagnostics_data
        }
        await self.broadcast_json(message)
        
    async def add_chat_message(self, message_data: dict):
        """Add a new chat message to the real-time activity monitor"""
        data = {
            "type": "chat_message",
            "data": message_data
        }
        await self.broadcast_json(data)


    
    async def update_conversation(self, conversation_data: dict):
        """Send updated conversation data to all connected clients"""
        message = {
            "type": "conversation_update",
            "data": conversation_data
        }
        await self.broadcast_json(message)
    
# Create a singleton instance
websocket_manager = ConnectionManager()