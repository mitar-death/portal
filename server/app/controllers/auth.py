import os
from fastapi import HTTPException, Request
from server.app.core.logging import logger
from server.app.services.monitor import set_active_user_id
from server.app.services.telegram import get_client
from server.app.models.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any
from server.app.models.models import ActiveSession, User
from server.app.services.monitor import stop_monitoring
from server.app.utils.controller_helpers import (
    ensure_client_connected,
    ensure_user_authenticated,
    safe_db_operation,
    sanitize_log_data,
    standardize_response
)
from  server.app.services.telegram import (get_client, 
                                           reset_client, 
                                           session_dir, 
                                           session_path,
                                           get_session_name,
                                           metadata_file)
from server.app.services.redis_client import (init_redis)
@safe_db_operation()
async def check_auth_status(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Check the current Telegram authentication status.
    Returns whether the user is authenticated and if the client is connected.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with connection status, authorization status, and user info if available
    """
    try:
        # Get the Telegram client
        client = await get_client()
        
        # Check if the client is connected
        is_connected = client.is_connected()
        if not is_connected:
            # Try to connect if not already connected
            await client.connect()
            is_connected = client.is_connected()
        
        # Check if the user is authorized
        is_authorized = await client.is_user_authorized()
        
        # Get user info if authorized
        user_info = None
        if is_authorized:
            me = await client.get_me()
            if me:
                user_info = {
                    "id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "phone": me.phone
                }
                
                # Check if user already exists
                tg_id = str(me.id)
                stmt = select(User).where(User.telegram_id == tg_id)
                result = await db.execute(stmt)
                user = result.scalars().first()
                
                if user:
                    # Set this user as the active user for monitoring
                    await set_active_user_id(user.id)
                    logger.info(f"Set active user ID to {user.id} based on authenticated Telegram user")
        
        # Return the status
        return standardize_response(
            {
                "is_connected": is_connected,
                "is_authorized": is_authorized,
                "user_info": user_info
            },
            "Authentication status retrieved successfully"
        )
    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e
    except SQLAlchemyError as e:
        logger.error(f"Database error in check_auth_status: {sanitize_log_data(str(e))}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in check_auth_status: {sanitize_log_data(str(e))}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@safe_db_operation()
async def logout_telegram(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Log out the user from Telegram and clear the session.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with logout status
        
    Raises:
        HTTPException: For logout errors
    """
    user = await ensure_user_authenticated(request)
    client = await ensure_client_connected()
    
    if client is None:
        client = await reset_client()
        await client.connect()
    
    try:
        # Reset the active user ID in the monitor service
        await stop_monitoring()
        logger.info(f"Stopped monitoring for user {user.id}")
        
        # Log out from Telegram
        await client.log_out()
        logger.info(f"User {user.id} logged out successfully")
        
        # # Clear user's active session from database
        stmt = select(ActiveSession).where(ActiveSession.user_id == user.id)
        result = await db.execute(stmt)
        active_session = result.scalars().first()
        
        if active_session:
            await db.delete(active_session)
            await db.commit()
        
        # # Delete the Telethon session file
        try:
            # Check if user-specific session exists and delete it
            if os.path.exists(session_path):
                os.remove(session_path)
                logger.info(f"Deleted user-specific session file: {session_path}")
            
            if os.path.exists(metadata_file):
                os.remove(metadata_file)
                logger.info(f"Deleted session metadata file: {metadata_file}")

            # Check for and delete any additional session files that might exist
            for session_file in os.listdir(session_dir):
                if session_file.startswith("user_session") and session_file.endswith(".session"):
                    file_path = os.path.join(session_dir, session_file)
                    os.remove(file_path)
                    logger.info(f"Deleted session file: {file_path}")
            
            #clear the redis session 
            redis_connection = init_redis(decode_responses=False)
            if redis_connection:
                session_name = get_session_name()
                redis_connection.delete(session_name)
                logger.info(f"Cleared Redis session: {session_name}")
                    
        except Exception as e:
            logger.error(f"Error deleting session file: {e}")
            # Continue with logout even if file deletion fails
        
        return standardize_response({}, "Successfully logged out")
        
    except Exception as e:
        logger.error(f"Failed to log out: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log out: {str(e)}")
    finally:
        # Ensure the client is disconnected after operation
        if client.is_connected():
            await client.disconnect()
        logger.info("Disconnected Telegram client")