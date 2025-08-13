"""
WebSocket routes for real-time diagnostics and monitoring.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from server.app.core.logging import logger
from server.app.services.websocket_manager import websocket_manager
from server.app.services.monitor import diagnostic_check
from server.app.core.middlewares import get_current_user
from datetime import datetime
import asyncio
import json
import uuid

# Create a separate router for WebSocket endpoints
ws_router = APIRouter()

@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Accept all connections (only do this for development)
    origin = websocket.headers.get("origin", "")
    host = websocket.headers.get("host", "")
    
    logger.debug(f"WebSocket connection attempt from origin: {origin}, host: {host}")
    
    await websocket.accept()
    
    # Get token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
        
    # Authenticate user
    try:
        user = await get_current_user(token=token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
            
        # Generate a unique connection ID
        connection_id = str(uuid.uuid4())
        user_id = str(user.id)
        
        # Register connection with WebSocket manager
        await websocket_manager.connect(websocket, connection_id, user_id)
        
        try:
            # Keep connection alive and process messages
            while True:
                data = await websocket.receive_text()
                try:
                    # Parse JSON
                    message = json.loads(data)
                    
                    # Process message based on type
                    message_type = message.get("type", "")
                    
                    if message_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError:
                    # For plain text messages
                    if data == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                        
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {connection_id}")
        finally:
            # Clean up connection
            await websocket_manager.disconnect(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason="Server error")

@ws_router.websocket("/ws/diagnostics")
async def diagnostics_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time diagnostics updates.
    Provides live updates of system status, chat activity, and ongoing conversations.
    """
    connection_id = None
    
    # Accept the connection
    await websocket.accept()
    
    # Get the authentication token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
        
    # Authenticate the user
    try:
        user = await get_current_user(token=token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
            
        # Generate a unique connection ID
        connection_id = str(uuid.uuid4())
        user_id = str(user.id)
        
        # Register the connection with the WebSocket manager
        await websocket_manager.connect(websocket, connection_id, user_id)
        
        # Send initial diagnostics data
        try:
            # Get diagnostics using the diagnostic_check function
            diagnostics = await diagnostic_check()
            
            # Add connection info
            diagnostics["websocket_info"] = {
                "active_connections": websocket_manager.get_connection_count(),
                "connected_users": websocket_manager.get_user_count(),
                "connection_id": connection_id
            }
            
            # Send to client
            await websocket.send_json({
                "type": "diagnostics_update",
                "data": diagnostics,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error sending initial diagnostics: {e}")
            
        # Handle client messages
        try:
            while True:
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    message_type = message.get("type", "")
                    
                    if message_type == "get_diagnostics":
                        # Refresh diagnostics
                        diagnostics = await diagnostic_check()
                        
                        # Add connection info
                        diagnostics["websocket_info"] = {
                            "active_connections": websocket_manager.get_connection_count(),
                            "connected_users": websocket_manager.get_user_count(),
                            "connection_id": connection_id
                        }
                        
                        # Send to client
                        await websocket.send_json({
                            "type": "diagnostics_update",
                            "data": diagnostics,
                            "timestamp": datetime.now().isoformat()
                        })
                    elif message_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError:
                    # Handle plain text for backward compatibility
                    if data == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                    elif data == "refresh":
                        diagnostics = await diagnostic_check()
                        await websocket.send_json({
                            "type": "diagnostics_update",
                            "data": diagnostics,
                            "timestamp": datetime.now().isoformat()
                        })
                        
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Error in diagnostics WebSocket: {e}")
            
    except Exception as e:
        logger.error(f"Error establishing WebSocket connection: {e}")
    finally:
        # Always clean up the connection
        if connection_id:
            await websocket_manager.disconnect(connection_id)

@ws_router.websocket("/ws/chat-activity")
async def chat_activity_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat activity monitoring.
    Provides live updates of messages being processed by the system.
    """
    # Accept the connection
    await websocket.accept()
    
    # Get the authentication token from query parameters
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return
    
    # Authenticate the user
    try:
        user = await get_current_user(token=token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
    except Exception as e:
        logger.error(f"Authentication error in WebSocket: {e}")
        await websocket.close(code=1008, reason="Authentication error")
        return
    
    # Generate a unique connection ID
    connection_id = str(uuid.uuid4())
    user_id = str(user.id)
    
    # Register the connection with the WebSocket manager
    await websocket_manager.connect(websocket, connection_id, user_id)
    
    try:
        # Keep the connection alive and process any client messages
        while True:
            # Wait for any message from the client
            await websocket.receive_text()
                
    except WebSocketDisconnect:
        # Client disconnected
        logger.info(f"WebSocket client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up the connection
        if connection_id:
            await websocket_manager.disconnect(connection_id)
