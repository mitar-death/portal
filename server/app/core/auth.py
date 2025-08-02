"""
Authentication utilities for the API.
"""
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy import select
from typing import Optional
from server.app.core.databases import AsyncSessionLocal
from server.app.models.models import User
from server.app.core.logging import logger

async def get_current_user_from_token(authorization: Optional[str] = Header(None)):
    """
    Get the current user from the authorization token.
    This is a dependency that can be used in FastAPI route definitions.
    
    Args:
        authorization: The Authorization header value (Bearer token)
        
    Returns:
        The authenticated user object
        
    Raises:
        HTTPException: If authentication fails
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = authorization.split(" ")[1]
    if not token.startswith("token_"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    try:
        user_id = int(token.split("token_")[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalars().first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                
            logger.debug(f"Authenticated user: {user.id}")
            return user
            
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

# This function is used by WebSocket endpoints which receive the token as a parameter
async def get_current_user(token: str):
    """
    Get the current user from a token string.
    This is used for WebSocket authentication where the token is passed as a query parameter.
    
    Args:
        token: The authentication token
        
    Returns:
        The authenticated user object or None if authentication fails
    """
    if not token or not token.startswith("token_"):
        return None
        
    try:
        user_id = int(token.split("token_")[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalars().first()
            
            if not user:
                return None
                
            logger.debug(f"WebSocket authenticated user: {user.id}")
            return user
            
    except Exception as e:
        logger.error(f"WebSocket authentication error: {str(e)}")
        return None
