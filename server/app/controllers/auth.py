from fastapi import HTTPException, Request
from server.app.core.logging import logger
from server.app.services.monitor import set_active_user_id
from server.app.services.telegram import get_client
from server.app.core.databases import db_context
from server.app.models.models import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any, Optional
from server.app.utils.controller_helpers import (
    safe_db_operation,
    sanitize_log_data,
    standardize_response
)

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
