"""
Helper utilities for controllers to reduce code duplication and improve error handling.
"""
import functools
from typing import Any, Callable, TypeVar, cast
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from server.app.core.logging import logger
from server.app.core.databases import db_context

T = TypeVar('T')

async def ensure_client_connected():
    """
    Ensure the Telegram client is connected. Returns the connected client.
    """
    from server.app.services.telegram import get_client
    
    client = get_client()
    
    # Always explicitly check connection state
    if not client.is_connected():
        logger.info("Client disconnected, reconnecting...")
        await client.connect()
    
    # Add more detailed connection verification
    try:
        # Perform a lightweight API call to verify connection
        await client.get_me()
        logger.debug("Verified client connection with API call")
    except Exception as e:
        logger.warning(f"Client connection verification failed: {e}")
        # Try reconnecting once more
        await client.disconnect()
        await client.connect()
    
    # Validate the session is active
    if not await client.is_user_authorized():
        logger.warning("Telegram client connected but not authorized")
    else:
        logger.debug("Telegram client connected and authorized")
     
    return client

async def ensure_user_authenticated(request: Request):
    """
    Ensure the user is authenticated. Returns the authenticated user or raises an exception.
    """
    user = getattr(request.state, "user", None) or getattr(request, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return user

async def ensure_telegram_authorized(client=None):
    """
    Ensure the Telegram client is authorized. Returns the authorized client or raises an exception.
    """
    if client is None:
        client = await ensure_client_connected()
    
    if not await client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Telegram session not authorized")
    return client

def safe_db_operation():
    """
    Decorator for safely handling database operations with proper transaction management.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            db = db_context.get()
            try:
                result = await func(*args, **kwargs, db=db)
                await db.commit()  # Add this line to commit the transaction
                return result
            except HTTPException:
                await db.rollback()
                raise
            except Exception as e:
                await db.rollback()
                logger.error(f"Database operation failed in {func.__name__}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")
        return cast(Callable[..., T], wrapper)
    return decorator

def sanitize_log_data(data: Any) -> Any:
    """
    Remove sensitive information from data before logging.
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if key.lower() in ['phone', 'phone_number', 'password', 'token', 'secret', 'hash']:
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = sanitize_log_data(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    return data

def standardize_response(data: Any, message: str = "Operation successful", status_code: int = 200):
    """
    Return a standardized response format.
    """
    return {
        "success": 200 <= status_code < 300,
        "message": message,
        "data": data
    }
