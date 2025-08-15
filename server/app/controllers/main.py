from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request
from server.app.models.models import ActiveSession, SelectedGroup, User, Group
from telethon.errors import PhoneCodeInvalidError, SessionPasswordNeededError, SessionExpiredError, SignInFailedError
from server.app.core.logging import logger
from server.app.services.monitor import  start_monitoring, start_health_check_task
from server.app.services.monitor import set_active_user_id
from  server.app.services.telegram import (get_client)

from server.app.utils.controller_helpers import (
    ensure_client_connected,
    ensure_user_authenticated,
    ensure_telegram_authorized,
    safe_db_operation,
    sanitize_log_data,
    standardize_response
)
@safe_db_operation()
async def request_code(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
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
            raise HTTPException(status_code=400, detail="Phone number is required")
            
        logger.info(f"Requesting code for phone number: {sanitize_log_data(phone_number)}")
        
        # Get and connect client
        client = await get_client(new_session=True)
        
        if await client.is_user_authorized():
            logger.info("User already authorized")
            return standardize_response(
                {"action": "already_authorized", "phone_code_hash": ""},
                "Already authorized"
            )
            
        session_id = f"session_{phone_number}"
        response = await client.send_code_request(phone_number)

        # Check if there's an existing session for this phone
        stmt = select(ActiveSession).where(ActiveSession.phone_number == phone_number)
        result = await db.execute(stmt)
        existing_session = result.scalars().first()
        
        if existing_session:
            # Update existing session
            existing_session.code_requested = True
            existing_session.verified = False
            db.add(existing_session)
        else:
            # Create new session
            new_session = ActiveSession(
                session_id=session_id,
                user_id = user.id if user else None,
                phone_number=phone_number,
                code_requested=True,
                verified=False
            )
            db.add(new_session)
        
        await db.commit()
        
        # Don't log the full phone_code_hash
        logger.info(f"Code requested successfully")
        
        return standardize_response(
            {"phone_code_hash": response.phone_code_hash},
            "Verification code sent to your phone"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Failed to send code request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send verification code")


@safe_db_operation()
async def verify_code(phone_number: str, code: str, phone_code_hash: str, db: AsyncSession = None):
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
    # Start with a fresh client connection
    client = await get_client()
    
    # Check if we have an active session
    stmt = select(ActiveSession).where(ActiveSession.phone_number == phone_number)
    result = await db.execute(stmt)
    session = result.scalars().first()
    
    if not session or not session.code_requested:
        raise HTTPException(status_code=400, detail="No active login session found")
    
    try:
        # After successful sign_in, verify the session was saved
        response = await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
        logger.info(f"Authentication successful with Telegram {phone_code_hash}")
        
        # Verify the session is actually authorized
        if not await client.is_user_authorized():
            logger.error("Client reports as unauthorized even after successful sign_in")
            raise HTTPException(status_code=500, detail="Authentication session not saved properly")
            
        # Force a simple API call to ensure the session works
        me = await client.get_me()
        logger.info(f"Verified session with user: {me.first_name} (ID: {me.id})")
       
        session.verified = True
        db.add(session)
        await db.commit()
            
        # Check if user exists in database
        user_stmt = select(User).where(User.telegram_id == str(response.id))
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        
        if not user:
            # Check if there's a user with this phone number
            phone_user_stmt = select(User).where(User.phone_number == phone_number)
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
                    first_name=response.first_name if response.first_name else "User",
                    last_name=response.last_name if response.last_name else None,
                    phone_number=phone_number
                )
                db.add(user)
                
            await db.commit()
            await db.refresh(user)
            
        token = f"token_{response.id}"
            
        user_data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": sanitize_log_data(user.phone_number)
        }
        
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
                "token": token
            },
           "Successfully logged in",
        )
    except PhoneCodeInvalidError:
        logger.error("Invalid verification code provided")
        raise HTTPException(status_code=400, detail="Invalid verification code")
    except SessionPasswordNeededError:
        logger.error("Two-step verification is enabled, password required")
        raise HTTPException(status_code=403, detail="Two-step verification is enabled, password required")
    except SessionExpiredError:
        logger.error("Session expired, please request a new code")
        raise HTTPException(status_code=401, detail="Session expired, please request a new code")
    except SignInFailedError:
        logger.error("Sign-in failed, please check your credentials")
        raise HTTPException(status_code=401, detail="Sign-in failed, please check your credentials")
    except HTTPException as e:
        # Re-raise HTTP exceptions without logging them again
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to verify code: {str(e)}")

