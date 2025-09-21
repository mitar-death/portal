"""
Authentication utilities for the API.
"""

from fastapi import Depends, HTTPException, status, Header, Request
from sqlalchemy import select, and_
from typing import Optional
from server.app.core.databases import AsyncSessionLocal
from server.app.models.models import User, BlacklistedToken, ActiveSession
from server.app.core.logging import logger
from server.app.core.jwt_utils import JWTManager, verify_token
from datetime import datetime, timezone


async def is_token_blacklisted(jti: str, db_session) -> bool:
    """
    Check if a JWT token is blacklisted.

    Args:
        jti: JWT ID
        db_session: Database session

    Returns:
        True if token is blacklisted, False otherwise
    """
    try:
        result = await db_session.execute(
            select(BlacklistedToken).where(BlacklistedToken.jti == jti)
        )
        blacklisted_token = result.scalars().first()
        return blacklisted_token is not None
    except Exception as e:
        logger.error(f"Error checking blacklisted token: {str(e)}")
        return False


async def get_current_user_from_token(authorization: Optional[str] = Header(None)):
    """
    Get the current user from the JWT authorization token.
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

    try:
        # Verify JWT token
        payload = verify_token(token, "access")

        # Extract user information
        user_id = JWTManager.extract_user_id_from_token(payload)
        jti = payload.get("jti")

        if not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"},
            )

        async with AsyncSessionLocal() as session:
            # Check if token is blacklisted
            if await is_token_blacklisted(jti, session):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Get user from database
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Check if user is active
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is inactive",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Update session activity
            await update_session_activity(session, jti)

            logger.debug(f"Authenticated user: {user.id}")
            return user

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def update_session_activity(db_session, access_token_jti: str):
    """
    Update the last activity timestamp for a session.

    Args:
        db_session: Database session
        access_token_jti: Access token JTI
    """
    try:
        result = await db_session.execute(
            select(ActiveSession).where(
                ActiveSession.access_token_jti == access_token_jti
            )
        )
        session = result.scalars().first()

        if session:
            session.last_activity = datetime.now(timezone.utc)
            db_session.add(session)
            await db_session.commit()
    except Exception as e:
        logger.error(f"Error updating session activity: {str(e)}")


# This function is used by WebSocket endpoints which receive the token as a parameter
async def get_current_user(token: str):
    """
    Get the current user from a JWT token string.
    This is used for WebSocket authentication where the token is passed as a query parameter.

    Args:
        token: The JWT authentication token

    Returns:
        The authenticated user object or None if authentication fails
    """
    if not token:
        return None

    try:
        # Verify JWT token
        payload = verify_token(token, "access")

        # Extract user information
        user_id = JWTManager.extract_user_id_from_token(payload)
        jti = payload.get("jti")

        if not jti:
            logger.warning("WebSocket token missing JTI")
            return None

        async with AsyncSessionLocal() as session:
            # Check if token is blacklisted
            if await is_token_blacklisted(jti, session):
                logger.warning("WebSocket token is blacklisted")
                return None

            # Get user from database
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()

            if not user or not user.is_active:
                logger.warning(f"WebSocket user not found or inactive: {user_id}")
                return None

            # Update session activity
            await update_session_activity(session, jti)

            logger.debug(f"WebSocket authenticated user: {user.id}")
            return user

    except Exception as e:
        logger.error(f"WebSocket authentication error: {str(e)}")
        return None


async def require_auth(request: Request) -> User:
    """
    Ensure that a request has an authenticated user.

    Args:
        request (Request): FastAPI request object.

    Raises:
        HTTPException: If the user is not authenticated.

    Returns:
        User: Authenticated user object from request.
    """
    # Try to get user from both request.user and request.state.user
    user = getattr(request, "user", None) or getattr(request.state, "user", None)
    logger.debug(f"User: {user}")

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user
