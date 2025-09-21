import os
from fastapi import HTTPException, Request
from server.app.core.logging import logger
from server.app.services.monitor import set_active_user_id
from server.app.services.telegram import client_manager
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
# Legacy session imports removed - use client_manager directly
from server.app.services.redis_client import init_redis, safe_redis_operation
from server.app.core.jwt_utils import create_token_pair, verify_token, JWTManager
from server.app.models.models import BlacklistedToken
from server.app.core.config import settings
from datetime import datetime, timezone, timedelta
@safe_db_operation()
async def check_auth_status(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Check the current Telegram authentication status.
    This function checks if there's already a user with an authenticated session.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with connection status, authorization status, and user info if available
    """
    try:
        # First check if there are any users with active sessions
        # For now, we'll check all users to see if any have authenticated sessions
        # In a more advanced implementation, this would be based on the current user's JWT token
        
        stmt = select(User)
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        # If no users exist in the database, return not connected/authorized
        if not users:
            return standardize_response(
                {
                    "is_connected": False,
                    "is_authorized": False,
                    "user_info": None
                },
                "Authentication status retrieved successfully"
            )
        
        # Check each user to see if they have an authenticated Telegram client
        for user in users:
            try:
                client = await client_manager.get_user_client(user.id)
                if client and client.is_connected() and await client.is_user_authorized():
                    # Found an authenticated user
                    me = await client.get_me()
                    if me:
                        user_info = {
                            "id": me.id,
                            "username": me.username,
                            "first_name": me.first_name,
                            "last_name": me.last_name,
                            "phone": me.phone
                        }
                        
                        # Set this user as the active user for monitoring
                        await set_active_user_id(user.id)
                        logger.info(f"Set active user ID to {user.id} based on authenticated Telegram user")
                        
                        return standardize_response(
                            {
                                "is_connected": True,
                                "is_authorized": True,
                                "user_info": user_info
                            },
                            "Authentication status retrieved successfully"
                        )
            except Exception as e:
                logger.debug(f"Error checking auth for user {user.id}: {e}")
                continue
        
        # No authenticated users found
        return standardize_response(
            {
                "is_connected": False,
                "is_authorized": False,
                "user_info": None
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
        import traceback
        logger.error(f"Error in check_auth_status: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


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
    
    try:
        # Stop monitoring for this user
        await stop_monitoring()
        logger.info(f"Stopped monitoring for user {user.id}")
        
        # Get the user's Telegram client
        client = await client_manager.get_user_client(user.id)
        
        if client:
            # Log out from Telegram
            await client.log_out()
            logger.info(f"User {user.id} logged out successfully")
        
        # Clean up user's session completely using ClientManager
        cleanup_success = await client_manager.cleanup_user_session(user.id)
        if cleanup_success:
            logger.info(f"Successfully cleaned up all session data for user {user.id}")
        else:
            logger.warning(f"Some session cleanup failed for user {user.id}")
        
        # Clear user's active session from database
        stmt = select(ActiveSession).where(ActiveSession.user_id == user.id)
        result = await db.execute(stmt)
        active_session = result.scalars().first()
        
        if active_session:
            await db.delete(active_session)
            await db.commit()
        
        return standardize_response({}, "Successfully logged out")
        
    except Exception as e:
        logger.error(f"Failed to log out user {user.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log out: {str(e)}")


@safe_db_operation()
async def refresh_access_token(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Refresh an access token using a valid refresh token.
    
    Args:
        request: The HTTP request containing refresh token
        db: Database session (injected by decorator)
        
    Returns:
        Dict with new access token
        
    Raises:
        HTTPException: For token refresh errors
    """
    try:
        # Get refresh token from request body
        body = await request.json()
        refresh_token = body.get("refresh_token")
        
        if not refresh_token:
            raise HTTPException(status_code=400, detail="Refresh token is required")
        
        # Verify refresh token
        payload = verify_token(refresh_token, "refresh")
        
        # Extract user information
        user_id = JWTManager.extract_user_id_from_token(payload)
        telegram_id = JWTManager.extract_telegram_id_from_token(payload)
        refresh_jti = payload.get("jti")
        
        if not refresh_jti:
            raise HTTPException(status_code=401, detail="Invalid refresh token format")
        
        # Check if refresh token is blacklisted
        from server.app.core.auth import is_token_blacklisted
        if await is_token_blacklisted(refresh_jti, db):
            raise HTTPException(status_code=401, detail="Refresh token has been revoked")
        
        # Verify user exists and is active
        user_stmt = select(User).where(User.id == user_id)
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        # Generate new access token (keep the same refresh token)
        from server.app.core.jwt_utils import create_access_token
        new_access_token = create_access_token(user_id, telegram_id)
        
        # Update session with new access token JTI
        new_access_payload = verify_token(new_access_token, "access", verify_expiry=False)
        new_access_jti = new_access_payload["jti"]
        
        # Update session in database
        session_stmt = select(ActiveSession).where(ActiveSession.refresh_token_jti == refresh_jti)
        session_result = await db.execute(session_stmt)
        session = session_result.scalars().first()
        
        if session:
            # Update session with new access token info FIRST
            old_access_jti = session.access_token_jti  # Store old JTI for delayed blacklisting
            session.access_token_jti = new_access_jti
            session.access_token_expires_at = datetime.fromtimestamp(
                new_access_payload["exp"], tz=timezone.utc
            )
            session.last_activity = datetime.now(timezone.utc)
            db.add(session)
            await db.commit()
            
            # Blacklist old access token AFTER committing the new token (prevents race condition)
            if old_access_jti:
                old_blacklisted_token = BlacklistedToken(
                    jti=old_access_jti,
                    token_type="access",
                    user_id=user_id,
                    expires_at=session.access_token_expires_at or datetime.now(timezone.utc),
                    reason="token_refresh"
                )
                db.add(old_blacklisted_token)
                await db.commit()
        
        logger.info(f"Access token refreshed for user {user_id}")
        
        return standardize_response(
            {
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
            },
            "Access token refreshed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


@safe_db_operation()
async def logout_user(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Logout user by blacklisting their JWT tokens.
    
    Args:
        request: The HTTP request containing access token in Authorization header
        db: Database session (injected by decorator)
        
    Returns:
        Dict with logout confirmation
        
    Raises:
        HTTPException: For logout errors
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization token required")
        
        access_token = auth_header.split(" ")[1]
        
        # Verify access token to get user information
        try:
            payload = verify_token(access_token, "access")
        except Exception as e:
            logger.warning(f"Invalid token during logout: {str(e)}")
            # Even if token is invalid, we'll try to process logout gracefully
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Extract token information
        user_id = JWTManager.extract_user_id_from_token(payload)
        access_jti = payload.get("jti")
        
        if not access_jti:
            raise HTTPException(status_code=400, detail="Invalid token format")
        
        # Find active session with this access token
        session_stmt = select(ActiveSession).where(ActiveSession.access_token_jti == access_jti)
        session_result = await db.execute(session_stmt)
        session = session_result.scalars().first()
        
        tokens_blacklisted = []
        
        if session:
            # Blacklist access token
            if session.access_token_jti:
                access_blacklisted_token = BlacklistedToken(
                    jti=session.access_token_jti,
                    token_type="access",
                    user_id=user_id,
                    expires_at=session.access_token_expires_at or datetime.now(timezone.utc),
                    reason="user_logout"
                )
                db.add(access_blacklisted_token)
                tokens_blacklisted.append("access")
            
            # Blacklist refresh token
            if session.refresh_token_jti:
                refresh_blacklisted_token = BlacklistedToken(
                    jti=session.refresh_token_jti,
                    token_type="refresh",
                    user_id=user_id,
                    expires_at=session.refresh_token_expires_at or datetime.now(timezone.utc),
                    reason="user_logout"
                )
                db.add(refresh_blacklisted_token)
                tokens_blacklisted.append("refresh")
            
            # Remove the session
            await db.delete(session)
            await db.commit()
            
            logger.info(f"User {user_id} logged out, tokens blacklisted: {tokens_blacklisted}")
        else:
            # Even if no session found, blacklist the access token
            access_blacklisted_token = BlacklistedToken(
                jti=access_jti,
                token_type="access",
                user_id=user_id,
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                reason="user_logout"
            )
            db.add(access_blacklisted_token)
            await db.commit()
            tokens_blacklisted.append("access")
            
            logger.info(f"User {user_id} logged out, access token blacklisted (no session found)")
        
        return standardize_response(
            {
                "tokens_blacklisted": tokens_blacklisted,
                "logout_time": datetime.now(timezone.utc).isoformat()
            },
            "Logout successful"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(status_code=500, detail="Logout failed")