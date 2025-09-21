"""
Helper utilities for controllers to reduce code duplication and improve error handling.
"""
import functools
import asyncio
from typing import Any, Callable, TypeVar, cast
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from server.app.core.logging import logger
from server.app.core.databases import db_context
from contextlib import asynccontextmanager
from server.app.services.telegram import client_manager
T = TypeVar('T')

# Semaphore to limit concurrent operations
API_SEMAPHORE = asyncio.Semaphore(10)

async def ensure_client_connected(request: Request):
    """
    Ensure the Telegram client is connected for the authenticated user. Returns the connected client.
    Uses timeout protection to prevent blocking indefinitely.
    
    Args:
        request: HTTP request containing user context
    """
    # Get user from request state (set by AuthMiddleware)
    user = await ensure_user_authenticated(request)
    user_id = user.id
    
    # Get user-specific client
    client = await client_manager.get_user_client(user_id)
    
    # Always explicitly check connection state
    if not client.is_connected():
        logger.info("Client disconnected, reconnecting...")
        try:
            async with API_SEMAPHORE:
                await asyncio.wait_for(client.connect(), timeout=5)
            logger.info("Client reconnected successfully")
            
        except asyncio.TimeoutError:
            logger.error("Timeout while connecting Telegram client")
            return None
        except Exception as e:
            logger.error(f"Error reconnecting client: {e}")
            return None
    
    # Add more detailed connection verification
    try:
        # Perform a lightweight API call to verify connection with timeout
        async with API_SEMAPHORE:
            await asyncio.wait_for(client.get_me(), timeout=5)
        logger.debug("Verified client connection with API call")
    except asyncio.TimeoutError:
        logger.error("Timeout during connection verification")
        # Try reconnecting once more
        await client.disconnect()
        try:
            async with API_SEMAPHORE:
                await asyncio.wait_for(client.connect(), timeout=5)
        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"Failed to reconnect after timeout: {e}")

    except Exception as e:
        logger.error(f"Error verifying client connection: {e}")
        # Try reconnecting
        await client.disconnect()
        try:
            async with API_SEMAPHORE:
                await asyncio.wait_for(client.connect(), timeout=5)
        except (asyncio.TimeoutError, Exception) as reconnect_error:
            logger.error(f"Failed to reconnect: {reconnect_error}")

    
    # Validate the session is active
    try:
        async with API_SEMAPHORE:
            is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=5)
        if not is_authorized:
            logger.warning("Telegram client connected but not authorized")
        else:
            logger.debug("Telegram client connected and authorized")
    except asyncio.TimeoutError:
        logger.error("Timeout checking authorization status")

    except Exception as e:
        logger.error(f"Error checking authorization: {e}")

     
    return client

async def ensure_user_authenticated(request: Request):
    """
    Ensure the user is authenticated. Returns the authenticated user or raises an exception.
    """
    user = getattr(request.state, "user", None) or getattr(request, "user", None)
    if not user:
        raise HTTPException(
            status_code=401, 
            detail={"code": "JWT_UNAUTHORIZED", "message": "Authentication required"}
        )
    return user

async def ensure_telegram_authorized(request: Request, client=None):
    """
    Ensure the Telegram client is authorized with timeout protection.
    Returns the authorized client or raises an exception.
    
    Args:
        request: HTTP request containing user context
        client: Optional pre-existing client to check, otherwise creates one for user
    """
    if client is None:
        client = await ensure_client_connected(request)
    
    try:
        async with API_SEMAPHORE:
            is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=5)
        if not is_authorized:
            logger.error("Telegram client is not authorized")
            return None
    except asyncio.TimeoutError:
        logger.error("Timeout checking authorization status")
        return None
    except Exception as e:
        logger.error(f"Error checking authorization: {e}")
        return None
        
    return client

@asynccontextmanager
async def safe_db_session():
    """
    Context manager for safely handling database sessions.
    Ensures proper session cleanup to prevent database locks.
    """
    from server.app.core.databases import AsyncSessionLocal
    
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()

def safe_db_operation():
    """
    Decorator for safely handling database operations with proper transaction management.
    Prevents database locks by ensuring proper session handling.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            
            # If db is already provided, use it
            if db is not None:
                return await func(*args, **kwargs)
                
            # Otherwise, create a new session
            async with safe_db_session() as session:
                kwargs['db'] = session
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    raise
                    
        return wrapper
    return decorator

def sanitize_log_data(data: Any) -> Any:
    """
    Sanitize sensitive data for logging.
    
    Args:
        data: The data to sanitize
        
    Returns:
        Sanitized data safe for logging
    """
    if data is None:
        return None
        
    if isinstance(data, str):
        # For phone numbers, mask all but the last 4 digits
        if any(char.isdigit() for char in data) and len(data) > 4:
            return "*" * (len(data) - 4) + data[-4:]
        # For other strings, mask the middle portion
        elif len(data) > 6:
            return data[:2] + "*" * (len(data) - 4) + data[-2:]
        # For short strings, replace with asterisks
        else:
            return "*" * len(data)
            
    elif isinstance(data, dict):
        # Recursively sanitize dictionary values
        return {k: sanitize_log_data(v) for k, v in data.items()}
        
    elif isinstance(data, list):
        # Recursively sanitize list items
        return [sanitize_log_data(item) for item in data]
        
    # Return other types unchanged
    return data

def standardize_response(data: Any, message: str = "Operation successful", status_code: int = 200):
    """
    Create a standardized response format.
    
    Args:
        data: The response data
        message: A message describing the result
        status_code: HTTP status code
        
    Returns:
        Dict with standardized response format
    """
    return {
        "success": True if status_code < 400 else False,
        "data": data,
        "message": message,
        "status_code": status_code,
    }
