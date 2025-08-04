from fastapi import Request, HTTPException, WebSocket, Depends, WebSocketDisconnect, Header
from server.app.core.logging import logger
from server.app.services.messenger_ai import MessengerAI
from server.app.services.websocket_manager import websocket_manager
from datetime import datetime
import platform
import os
import psutil
import uuid
import json
import asyncio
from server.app.core.config import settings
from server.app.core.middlewares import get_current_user
from typing import Optional
from server.app.models.models import User


async def websocket_diagnostics(
    websocket: WebSocket,
    token: str = None
):
    """
    WebSocket endpoint for real-time diagnostics updates
    """
    connection_id = None
    user_id = None
    
    try:
        # Authenticate the user using the token
        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            return
            
        user = await get_current_user(token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
            
        # Generate a unique connection ID
        connection_id = str(uuid.uuid4())
        user_id = str(user.id) if user else None
        
        # Connect to the WebSocket manager
        await websocket_manager.connect(websocket, connection_id, user_id)
        
        try:
            # Send initial diagnostics data
            diagnostics = await MessengerAI().diagnostic_check()
            
            # Add additional system information
            diagnostics["timestamp"] = datetime.now().isoformat()
            diagnostics["system_info"] = {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "api_version": getattr(settings, "API_VERSION", "1.0.0")
            }
            
            # Add system resource information
            try:
                diagnostics["system_resources"] = {
                    "cpu_percent": psutil.cpu_percent(),
                    "memory_percent": psutil.virtual_memory().percent,
                    "disk_usage_percent": psutil.disk_usage('/').percent,
                    "process_memory_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                }
            except Exception as e:
                logger.error(f"Error getting system resources: {e}")
                diagnostics["system_resources"] = {"error": str(e)}
                
            # Add WebSocket information
            diagnostics["websocket_info"] = {
                "active_connections": websocket_manager.get_connection_count(),
                "connected_users": websocket_manager.get_user_count(),
                "connection_id": connection_id
            }
            
            await websocket_manager.send_json(connection_id, {
                "type": "diagnostics_update",
                "data": diagnostics,
                "timestamp": datetime.now().isoformat()
            })
            
            # Keep the connection alive and handle incoming messages
            while True:
                data = await websocket.receive_text()
                try:
                    message = json.loads(data)
                    message_type = message.get("type", "")
                    
                    if message_type == "ping":
                        await websocket_manager.send_json(connection_id, {
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                    elif message_type == "get_diagnostics":
                        # Client requested a refresh of diagnostics
                        diagnostics = await MessengerAI().diagnostic_check()
                        
                        # Add additional system information
                        diagnostics["timestamp"] = datetime.now().isoformat()
                        diagnostics["system_info"] = {
                            "platform": platform.platform(),
                            "python_version": platform.python_version(),
                            "api_version": getattr(settings, "API_VERSION", "1.0.0")
                        }
                        
                        # Add system resource information
                        try:
                            diagnostics["system_resources"] = {
                                "cpu_percent": psutil.cpu_percent(),
                                "memory_percent": psutil.virtual_memory().percent,
                                "disk_usage_percent": psutil.disk_usage('/').percent,
                                "process_memory_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                            }
                        except Exception as e:
                            logger.error(f"Error getting system resources: {e}")
                            diagnostics["system_resources"] = {"error": str(e)}
                            
                        # Add WebSocket information
                        diagnostics["websocket_info"] = {
                            "active_connections": websocket_manager.get_connection_count(),
                            "connected_users": websocket_manager.get_user_count(),
                            "connection_id": connection_id
                        }
                        
                        await websocket_manager.send_json(connection_id, {
                            "type": "diagnostics_update",
                            "data": diagnostics,
                            "timestamp": datetime.now().isoformat()
                        })
                except json.JSONDecodeError:
                    # Handle plain text messages for backward compatibility
                    if data == "ping":
                        await websocket_manager.send_json(connection_id, {
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                    elif data == "refresh":
                        # Client requested a refresh of diagnostics
                        diagnostics = await MessengerAI().diagnostic_check()
                        await websocket_manager.send_json(connection_id, {
                            "type": "diagnostics_update",
                            "data": diagnostics,
                            "timestamp": datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}")
                    
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Error in diagnostics WebSocket: {e}")
    
    except Exception as e:
        logger.error(f"Error establishing WebSocket connection: {e}")
    finally:
        # Always clean up the connection if it was established
        if connection_id:
            await websocket_manager.disconnect(connection_id)

async def get_ai_diagnostics(request: Request):
    """
    Get diagnostic information about the AI messenger system.
    This includes:
    - Status of telegram clients
    - AI accounts initialization status
    - Group-to-AI mappings
    - Keywords monitoring status
    - Active conversations
    - System resource usage
    - Email sending status
    - Recent errors
    """
    try:
        # Get diagnostics from the monitor service
        diagnostics = await MessengerAI().diagnostic_check()

        # Add version and timestamp
        diagnostics["timestamp"] = datetime.now().isoformat()
        diagnostics["system_info"] = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "api_version": getattr(settings, "API_VERSION", "1.0.0")
        }
        
        # Add session directory status
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
        
        # Add WebSocket information
        diagnostics["websocket_info"] = {
            "active_connections": websocket_manager.get_connection_count(),
            "connected_users": websocket_manager.get_user_count()
        }
        
        # Add system resource information
        try:
            diagnostics["system_resources"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent,
                "process_memory_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            diagnostics["system_resources"] = {"error": str(e)}
        
        logger.info(f"AI messenger diagnostics requested")
        
        # Return a standardized response
        return {
            "success": True,
            "message": "Diagnostics retrieved successfully",
            "diagnostics": diagnostics
        }
        
    except Exception as e:
        logger.error(f"Error in AI diagnostics controller: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving diagnostics: {str(e)}")


async def reinitialize_ai_messenger(request: Request):
    """
    Force reinitialization of the AI messenger system.
    This can be used to recover from a state where messenger_ai is None.
    """
    try:
        # Force a reinitialization of the messenger_ai
        result = await MessengerAI().ensure_messenger_ai_initialized()

        # Get updated diagnostics regardless of result
        diagnostics = await MessengerAI().diagnostic_check()
        
        # Add timestamp and standard fields
        diagnostics["timestamp"] = datetime.now().isoformat()
        diagnostics["system_info"] = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "api_version": getattr(settings, "API_VERSION", "1.0.0")
        }
        
        # Add system resources
        try:
            diagnostics["system_resources"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage_percent": psutil.disk_usage('/').percent,
                "process_memory_mb": psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            diagnostics["system_resources"] = {"error": str(e)}

        if result:
            logger.info("Successfully reinitialized AI messenger")
            
            # Broadcast notification to WebSocket clients
            try:
                await websocket_manager.send_notification(
                    "ai_reinitialized",
                    "AI messenger successfully reinitialized",
                    "success"
                )
                # Update diagnostics in WebSocket
                await websocket_manager.update_diagnostics(diagnostics)
            except Exception as e:
                logger.error(f"Error sending WebSocket notification: {e}", exc_info=True)
            
            return {
                "success": True,
                "message": "AI messenger successfully reinitialized",
                "diagnostics": diagnostics
            }
        else:
            logger.warning("Failed to reinitialize AI messenger")
            
            # Broadcast notification to WebSocket clients
            try:
                await websocket_manager.send_notification(
                    "ai_reinitialize_failed",
                    "Failed to reinitialize AI messenger",
                    "error"
                )
                # Still update diagnostics to show current state
                await websocket_manager.update_diagnostics(diagnostics)
            except Exception as e:
                logger.error(f"Error sending WebSocket notification: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": "Failed to reinitialize AI messenger",
                "diagnostics": diagnostics
            }
    except Exception as e:
        logger.error(f"Error reinitializing AI messenger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error reinitializing AI messenger: {str(e)}")


async def diagnostics_websocket_endpoint(
    websocket: WebSocket,
    token: str = None
):
    """
    WebSocket endpoint for real-time diagnostics updates (legacy endpoint)
    This endpoint is maintained for backward compatibility.
    New connections should use the websocket_diagnostics endpoint instead.
    """
    connection_id = None
    user_id = None
    
    try:
        # Authenticate the user using the token
        if not token:
            await websocket.close(code=1008, reason="Authentication required")
            return
            
        user = await get_current_user(token)
        if not user:
            await websocket.close(code=1008, reason="Invalid authentication")
            return
            
        # Generate a unique connection ID
        connection_id = str(uuid.uuid4())
        user_id = str(user.id) if user else None
        
        # Connect to the WebSocket manager
        await websocket_manager.connect(websocket, connection_id, user_id)
        logger.info(f"Legacy diagnostics WebSocket endpoint connected: {connection_id}, user: {user_id}")
        
        try:
            # Send initial diagnostics data
            diagnostics = await MessengerAI().diagnostic_check()
            
            # Add timestamp and system info
            diagnostics["timestamp"] = datetime.now().isoformat()
            diagnostics["system_info"] = {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "api_version": getattr(settings, "API_VERSION", "1.0.0")
            }
            
            # Add WebSocket information
            diagnostics["websocket_info"] = {
                "active_connections": websocket_manager.get_connection_count(),
                "connected_users": websocket_manager.get_user_count(),
                "connection_id": connection_id
            }
            
            await websocket_manager.send_json(connection_id, {
                "type": "diagnostics_update",
                "data": diagnostics,
                "timestamp": datetime.now().isoformat()
            })
            
            # Keep the connection alive and handle incoming messages
            while True:
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket_manager.send_json(connection_id, {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    })
                elif data == "refresh":
                    # Client requested a refresh of diagnostics
                    diagnostics = await MessengerAI().diagnostic_check()
                    
                    # Add timestamp and system info
                    diagnostics["timestamp"] = datetime.now().isoformat()
                    diagnostics["system_info"] = {
                        "platform": platform.platform(),
                        "python_version": platform.python_version(),
                        "api_version": getattr(settings, "API_VERSION", "1.0.0")
                    }
                    
                    # Add WebSocket information
                    diagnostics["websocket_info"] = {
                        "active_connections": websocket_manager.get_connection_count(),
                        "connected_users": websocket_manager.get_user_count(),
                        "connection_id": connection_id
                    }
                    
                    await websocket_manager.send_json(connection_id, {
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
        # Always clean up the connection if it was established
        if connection_id:
            await websocket_manager.disconnect(connection_id)