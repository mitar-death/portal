import json
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request
from server.app.models.models import ActiveSession, User
from telethon.errors import PhoneCodeInvalidError, SessionPasswordNeededError, SessionExpiredError, SignInFailedError
from server.app.core.logging import logger
from server.app.services.monitor import start_monitoring, start_health_check_task
from server.app.services.monitor import set_active_user_id
from server.app.services.telegram import client_manager
from server.app.utils.controller_helpers import (safe_db_operation,
                                                 sanitize_log_data,
                                                 standardize_response)
from server.app.core.jwt_utils import create_token_pair, JWTManager
from datetime import datetime, timezone, timedelta
from server.app.core.config import settings
from server.app.core.rate_limiter import login_rate_limiter


async def transfer_session_to_user(guest_client, user_id: int):
    """
    Transfer Telegram session from guest client to user client.
    
    Args:
        guest_client: The authenticated guest Telegram client
        user_id: The user ID to transfer the session to
    """
    try:
        if not guest_client or not guest_client.is_connected():
            logger.warning("Guest client is not connected, cannot transfer session")
            return
        
        # Export session string from authenticated guest client
        try:
            session_string = guest_client.session.save()
            if not session_string:
                # Try alternative method to get session data
                logger.warning("session.save() returned None, trying to get session data directly")
                if hasattr(guest_client.session, '_session_data'):
                    session_string = str(guest_client.session._session_data).encode()
                else:
                    logger.warning("No session string available from guest client")
                    return
        except Exception as e:
            logger.error(f"Failed to extract session string: {e}")
            return
        
        # Save session metadata for the user
        metadata_file = client_manager._get_user_metadata_file(user_id)
        try:
            existing_metadata = {}
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    existing_metadata = json.load(f)
            
            # Update with session string
            existing_metadata["session_string"] = session_string.decode() if isinstance(session_string, bytes) else session_string
            existing_metadata["transferred_at"] = datetime.now(timezone.utc).isoformat()
            
            with open(metadata_file, "w") as f:
                json.dump(existing_metadata, f)
            
            logger.info(f"Successfully saved session string for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save session metadata for user {user_id}: {e}")
            
    except Exception as e:
        logger.error(f"Error transferring session to user {user_id}: {e}")


@safe_db_operation()
async def request_code(request: Request,
                       db: AsyncSession = None) -> Dict[str, Any]:
    """
    Request a login code from Telegram for the given phone number.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with response data
        
    Raises:
        HTTPException: For validation or Telegram errors
    """
    user = getattr(request.state, "user", None)

    try:
        body = await request.json()
        phone_number = body.get("phone_number")
        if not phone_number:
            raise HTTPException(status_code=400,
                                detail="Phone number is required")

        logger.info(
            f"Requesting code for phone number: {sanitize_log_data(phone_number)}"
        )

        # Check rate limiting for code requests
        is_limited, limit_message = login_rate_limiter.is_rate_limited(
            phone_number)
        if is_limited:
            logger.warning(
                f"Rate limit exceeded for phone number: {sanitize_log_data(phone_number)}"
            )
            raise HTTPException(status_code=429, detail=limit_message)

        # Get a client for initial authentication (no user required yet)
        from server.app.services.telegram import client_manager
        client = await client_manager.get_guest_client()

        try:
            if await client.is_user_authorized():
                logger.info("User already authorized")
                return standardize_response(
                    {
                        "action": "already_authorized",
                        "phone_code_hash": ""
                    }, "Already authorized")

            session_id = f"session_{phone_number}"
            response = await client.send_code_request(phone_number)

            # Check if there's an existing session for this phone
            stmt = select(ActiveSession).where(
                ActiveSession.phone_number == phone_number)
            result = await db.execute(stmt)
            existing_session = result.scalars().first()

            if existing_session:
                # Update existing session
                existing_session.code_requested = True
                existing_session.verified = False
                db.add(existing_session)
            else:
                # Create new session
                new_session = ActiveSession(session_id=session_id,
                                            user_id=user.id if user else None,
                                            phone_number=phone_number,
                                            code_requested=True,
                                            verified=False)
                db.add(new_session)

            await db.commit()

            # Record the code request attempt (not a verification attempt yet)
            # Don't log the full phone_code_hash
            logger.info(f"Code requested successfully")

            return standardize_response(
                {"phone_code_hash": response.phone_code_hash},
                "Verification code sent to your phone")
        finally:
            # Always disconnect the guest client to prevent resource leaks
            try:
                if client and client.is_connected():
                    await client.disconnect()
                    logger.info("Guest client disconnected successfully")
            except Exception as disconnect_error:
                logger.warning(
                    f"Error disconnecting guest client: {disconnect_error}")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Failed to send code request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@safe_db_operation()
async def verify_code(request: Request,
                      phone_number: str,
                      code: str,
                      phone_code_hash: str,
                      db: AsyncSession = None):
    """
    Verify the code provided by the user.
    
    Args:
        phone_number: The phone number
        code: The verification code
        phone_code_hash: The hash received from request_code
        db: Database session (injected by decorator)
    
    Returns:
        Dict with user data and authentication token
    
    Raises:
        HTTPException: If verification fails
    """
    # Use guest client for verification (consistent with request_code)
    from server.app.services.telegram import client_manager
    client = await client_manager.get_guest_client()

    try:
        # Check if we have an active session
        stmt = select(ActiveSession).where(
            ActiveSession.phone_number == phone_number)
        result = await db.execute(stmt)
        session = result.scalars().first()

        if not session or not session.code_requested:
            raise HTTPException(status_code=400,
                                detail="No active login session found")

        # Check rate limiting for login attempts
        is_limited, limit_message = login_rate_limiter.is_rate_limited(
            phone_number)
        if is_limited:
            logger.warning(
                f"Rate limit exceeded for login attempt: {sanitize_log_data(phone_number)}"
            )
            raise HTTPException(status_code=429, detail=limit_message)

        # After successful sign_in, verify the session was saved
        response = await client.sign_in(phone=phone_number,
                                        code=code,
                                        phone_code_hash=phone_code_hash)
        logger.info(
            f"Authentication successful with Telegram {phone_code_hash}")

        # Verify the session is actually authorized
        if not await client.is_user_authorized():
            logger.error(
                "Client reports as unauthorized even after successful sign_in")
            raise HTTPException(
                status_code=500,
                detail="Authentication session not saved properly")

        # Force a simple API call to ensure the session works
        me = await client.get_me()
        logger.info(
            f"Verified session with user: {me.first_name} (ID: {me.id})")

        session.verified = True
        db.add(session)
        await db.commit()

        # Check if user exists in database
        user_stmt = select(User).where(User.telegram_id == str(response.id))
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()

        if not user:
            # Check if there's a user with this phone number
            phone_user_stmt = select(User).where(
                User.phone_number == phone_number)
            phone_user_result = await db.execute(phone_user_stmt)
            user = phone_user_result.scalars().first()

            if user:
                # Update existing user with Telegram ID
                user.telegram_id = str(response.id)
                user.username = response.username if response.username else user.username
                user.first_name = response.first_name if response.first_name else user.first_name
                user.last_name = response.last_name if response.last_name else user.last_name
                db.add(user)
            else:
                # Create a new user
                user = User(
                    telegram_id=str(response.id),
                    username=response.username if response.username else None,
                    first_name=response.first_name
                    if response.first_name else "User",
                    last_name=response.last_name
                    if response.last_name else None,
                    phone_number=phone_number)
                db.add(user)

            await db.commit()
            await db.refresh(user)

        # Generate JWT token pair
        tokens = create_token_pair(user_id=user.id,
                                   telegram_id=str(response.id))

        # Update session with JWT information
        # Extract JTI from tokens for session tracking
        access_payload = JWTManager.verify_token(tokens["access_token"],
                                                 verify_expiry=False)
        refresh_payload = JWTManager.verify_token(tokens["refresh_token"],
                                                  "refresh",
                                                  verify_expiry=False)

        session.access_token_jti = access_payload["jti"]
        session.refresh_token_jti = refresh_payload["jti"]
        session.access_token_expires_at = datetime.fromtimestamp(
            access_payload["exp"], tz=timezone.utc)
        session.refresh_token_expires_at = datetime.fromtimestamp(
            refresh_payload["exp"], tz=timezone.utc)
        session.last_activity = datetime.now(timezone.utc)
        session.is_active = True

        # Set device/IP info if available from request
        if hasattr(request, 'headers'):
            session.device_info = request.headers.get('User-Agent', 'Unknown')

        db.add(session)
        await db.commit()

        user_data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": sanitize_log_data(user.phone_number)
        }

        # Record successful login attempt for rate limiting
        login_rate_limiter.record_attempt(phone_number, success=True)

        # CRITICAL FIX: Transfer session from guest client to user client
        try:
            await transfer_session_to_user(client, user.id)
            logger.info(f"Successfully transferred session from guest to user {user.id}")
        except Exception as e:
            logger.error(f"Failed to transfer session to user {user.id}: {e}")
            # Don't fail the login for session transfer issues, but log it

        # Set this user as the active user for the monitoring service
        await set_active_user_id(user.id)
        logger.info(f"Set active user ID to {user.id} during login")

        monitoring_started = await start_monitoring()
        if monitoring_started:
            logger.info("Telegram message monitoring started successfully")
        else:
            logger.warning("Failed to start Telegram message monitoring")

        # Start the health check task for real-time diagnostics
        await start_health_check_task()
        logger.info("Health check monitoring task started")

        return standardize_response(
            {
                "action": "login_success",
                "user": user_data,
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": "Bearer",
                "expires_in":
                settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds
            },
            "Successfully logged in",
        )
    except PhoneCodeInvalidError:
        # Record failed login attempt for rate limiting
        login_rate_limiter.record_attempt(phone_number, success=False)
        logger.error("Invalid verification code provided")
        raise HTTPException(status_code=400,
                            detail="Invalid verification code")
    except SessionPasswordNeededError:
        logger.error("Two-step verification is enabled, password required")
        raise HTTPException(
            status_code=403,
            detail="Two-step verification is enabled, password required")
    except SessionExpiredError:
        logger.error("Session expired, please request a new code")
        raise HTTPException(
            status_code=401,
            detail="Session expired, please request a new code")
    except SignInFailedError:
        # Record failed login attempt for rate limiting
        login_rate_limiter.record_attempt(phone_number, success=False)
        logger.error("Sign-in failed, please check your credentials")
        raise HTTPException(
            status_code=401,
            detail="Sign-in failed, please check your credentials")
    except HTTPException as e:
        # Re-raise HTTP exceptions without logging them again
        raise e
    except Exception as e:
        # Record failed login attempt for rate limiting on general exceptions
        login_rate_limiter.record_attempt(phone_number, success=False)
        raise HTTPException(status_code=500,
                            detail=f"Failed to verify code: {str(e)}")
    finally:
        # Always disconnect the guest client to prevent resource leaks
        try:
            if client and client.is_connected():
                await client.disconnect()
                logger.info(
                    "Guest client disconnected successfully after verification"
                )
        except Exception as disconnect_error:
            logger.warning(
                f"Error disconnecting guest client after verification: {disconnect_error}"
            )
