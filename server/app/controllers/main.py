import os
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request
from server.app.core.databases import db_context
from server.app.models.models import ActiveSession, SelectedGroup, User, Keywords, Group
from server.app.core.logging import logger
from server.app.services.monitor import stop_monitoring, start_monitoring, start_health_check_task
from server.app.services.monitor import set_active_user_id
from server.app.services.telegram import session_path, session_dir
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
        client = await ensure_client_connected()
        
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
async def verify_code(phone_number: str, code: str, phone_code_hash: str, db: AsyncSession = None) -> Dict[str, Any]:
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
    client = await ensure_client_connected()
    
    # Check if we have an active session
    stmt = select(ActiveSession).where(ActiveSession.phone_number == phone_number)
    result = await db.execute(stmt)
    session = result.scalars().first()
    
    if not session or not session.code_requested:
        raise HTTPException(status_code=400, detail="No active login session found")
    
    try:
        response = await client.sign_in(phone=phone_number, code=code, phone_code_hash=phone_code_hash)
        logger.info(f"Authentication successful with Telegram")
       
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
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.error(f"Failed to verify code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to verify code: {str(e)}")

@safe_db_operation()
async def get_user_groups(request: Request, db: AsyncSession = None) -> List[Dict[str, Any]]:
    """
    Fetch the user's Telegram groups using the current authenticated Telegram session.
    Also saves or updates group information in the database.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        List of group data dictionaries
        
    Raises:
        HTTPException: For authentication or Telegram API errors
    """
    user = await ensure_user_authenticated(request)
    client = await ensure_client_connected()
    await ensure_telegram_authorized(client)
    
    groups = []
    
    try:
        # Fetch actual groups from Telegram
        dialogs = await client.get_dialogs()
        
        for dialog in dialogs:
            entity = dialog.entity
  
            # Check if it's a group or channel (not a private chat)
            if hasattr(entity, 'title'):
                # Save or update group in database
                stmt = select(Group).where(
                    Group.user_id == user.id,
                    Group.telegram_id == entity.id
                )
                result = await db.execute(stmt)
                existing_group = result.scalars().first()
                
                # Common attributes for both new and existing groups
                group_data = {  
                    "id": entity.id,
                    "title": entity.title,
                    "member_count": getattr(entity, 'participants_count', 0) or 0,  # Ensure it's never None
                    "description": getattr(entity, 'about', None),
                    "username": getattr(entity, 'username', None),
                    "is_channel": hasattr(entity, 'broadcast') and entity.broadcast
                }
                
                if existing_group:
                    # Update existing group with latest info
                    existing_group.title = entity.title
                    existing_group.username = getattr(entity, 'username', None)
                    existing_group.description = getattr(entity, 'about', None)
                    existing_group.member_count = getattr(entity, 'participants_count', 0)
                    existing_group.is_channel = group_data["is_channel"]
                    db.add(existing_group)
                    
                    # Add is_monitored flag from the database, ensuring it's a boolean
                    group_data["is_monitored"] = bool(existing_group.is_monitored) if existing_group.is_monitored is not None else False
                    logger.info(f"Updated existing group: {entity.title} (ID: {entity.id})")
                else:
                    # Create new group
                    new_group = Group(
                        user_id=user.id,
                        telegram_id=entity.id,
                        title=entity.title,
                        username=group_data["username"],
                        description=group_data["description"],
                        member_count=group_data["member_count"],
                        is_channel=group_data["is_channel"],
                        is_monitored=False 
                    )
                    db.add(new_group)
                    
                    # Add is_monitored flag (default False for new groups)
                    group_data["is_monitored"] = False
                    logger.info(f"Added new group: {entity.title} (ID: {entity.id})")
                
                groups.append(group_data)
        
        # Commit all group updates at once
        await db.commit()
        logger.info(f"Retrieved {len(groups)} groups for user {user.id}")
        return groups
        
    except Exception as e:
        logger.error(f"Failed to fetch groups: {e}")
        # If we already have some groups from Telegram, return those even if database operations failed
        if groups:
            # Ensure all groups have proper boolean values for is_monitored
            for group in groups:
                if "is_monitored" not in group or group["is_monitored"] is None:
                    group["is_monitored"] = False
            logger.info(f"Returning {len(groups)} groups despite database error")
            return groups
        raise HTTPException(status_code=500, detail=f"Failed to fetch groups: {str(e)}")


@safe_db_operation()
async def monitor_groups(request: Request, selected_groups: Dict[str, Any], db: AsyncSession = None) -> List[Dict[str, Any]]: 
    """
    Add selected Telegram groups for monitoring.
    
    Args:
        request: The HTTP request
        selected_groups: Dictionary containing group IDs to monitor
        db: Database session (injected by decorator)
        
    Returns:
        List of group data dictionaries
        
    Raises:
        HTTPException: For authentication or Telegram API errors
    """
    user = await ensure_user_authenticated(request)
    client = await ensure_client_connected()
    await ensure_telegram_authorized(client)
        
    logger.info(f"Adding selected groups for user {user.id} with group IDs: {selected_groups.group_ids}")
    
    try:
        groups = []
        # Process groups in batches to improve performance
        for group_id in selected_groups.group_ids:
            # Create selectedGroups relationship if it doesn't exist
            selected_group_stmt = select(SelectedGroup).where(
                SelectedGroup.user_id == user.id,
                SelectedGroup.group_id == str(group_id)
            )
            selected_group_result = await db.execute(selected_group_stmt)
            selected_group = selected_group_result.scalars().first()
            
            if not selected_group:
                selected_group = SelectedGroup(
                    user_id=user.id,
                    group_id=str(group_id)  # Explicitly convert to string to match model definition
                )
                db.add(selected_group)
            
            # Get the group from db
            stmt = select(Group).where(
                Group.user_id == user.id,
                Group.telegram_id == int(group_id)
            )
            group = await db.execute(stmt)
            db_group = group.scalars().first()
            logger.info(f"Selected group {db_group} for user {user.id}")
            if not db_group:
                # If group doesn't exist, create a minimal entry
                db_group = Group(
                    user_id=user.id,
                    telegram_id=int(group_id),
                    title=f"Group {group_id}",
                    member_count=0, 
                    description=None,
                    username=None,
                    is_channel=False,
                    is_monitored=True  # Mark as monitored
                )
                db.add(db_group)
            else:
                db_group.is_monitored = True
                db.add(db_group)
               
            try:
                entity = await client.get_entity(int(group_id))
                group_data = {
                    "id": entity.id,
                    "title": entity.title,
                    "member_count": getattr(entity, 'participants_count', 0) or 0,  # Ensure it's never None
                    "description": getattr(entity, 'about', None),
                    "username": getattr(entity, 'username', None),
                    "is_channel": hasattr(entity, 'broadcast') and entity.broadcast
                }
                logger.info(f"Adding group {group_data['title']} ({group_data['id']}) for monitoring")
                groups.append(group_data)
            except Exception as e:
                # If we can't get the entity, add minimal data that satisfies the schema
                logger.warning(f"Could not get entity for group {group_id}: {e}")
                groups.append({
                    "id": int(group_id) if isinstance(group_id, str) and group_id.isdigit() else 0,
                    "title": f"Group {group_id}",
                    "member_count": 0,  # Ensure this is always an integer, never None
                    "description": None,
                    "username": None,
                    "is_channel": False
                })
        
        # Commit all changes at once for better performance
        await db.commit()
        logger.info(f"Added {len(groups)} groups for monitoring for user {user.id}")

        # Restart monitoring with updated group selections (uncomment if needed)
        await set_active_user_id(user.id)
        await start_monitoring(user.id)
        
        return groups
        
    except Exception as e:
        logger.error(f"Failed to add selected groups: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add selected groups: {str(e)}")

@safe_db_operation()
async def get_keywords_controller(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Get the list of keywords for message filtering.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with keywords data
        
    Raises:
        HTTPException: For database or authentication errors
    """
    user = await ensure_user_authenticated(request)

    try:
        # Execute a proper SQLAlchemy query using the ORM
        stmt = select(Keywords).where(Keywords.user_id == user.id)
        result = await db.execute(stmt)
        user_keywords = result.scalars().first()
        
        # Get the keywords list or empty list if no record exists
        keywords_list = user_keywords.keywords if user_keywords else []
        
        
         # Ensure monitoring is started if not already
        return standardize_response(
            {
                "keywords": keywords_list,
                "count": len(keywords_list)
            },
            "Keywords fetched successfully"
        )
    except Exception as e:
        logger.error(f"Failed to fetch keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch keywords: {str(e)}")

@safe_db_operation()
async def add_keywords_controller(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Adds new keywords for message filtering.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with updated keywords data
        
    Raises:
        HTTPException: For validation or database errors
    """
    user = await ensure_user_authenticated(request)

    try:
        # Get request body
        body = await request.json()
        
        # Extract keywords from request body
        keywords = body.get("keywords", [])
        logger.info(f"Received keywords: {keywords}")
        
        if not isinstance(keywords, list):
            # Handle case where a single keyword is sent
            if isinstance(keywords, str):
                keywords = [keywords]
            else:
                raise HTTPException(status_code=400, detail="Keywords must be a list of strings")
        
        # Check if user already has a keywords entry
        stmt = select(Keywords).where(Keywords.user_id == user.id)
        result = await db.execute(stmt)
        user_keywords = result.scalars().first()
        
        if not user_keywords:
            # Create new keywords entry if none exists
            user_keywords = Keywords(user_id=user.id, keywords=[])
            db.add(user_keywords)
            await db.flush() 
            
        # Add each keyword using the model's add_keyword method
        added_count = 0
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.strip():
                if user_keywords.add_keyword(keyword):
                    added_count += 1
                    logger.info(f"Added keyword: {keyword}")
        
        if added_count > 0:
            await db.commit()
        
        # Refresh the keywords from the database to ensure we're returning the latest data
        await db.refresh(user_keywords)
        
        # Only restart monitoring if keywords were actually added
        if added_count > 0:
            monitoring_started = await start_monitoring()
            if monitoring_started:
                logger.info("Telegram message monitoring started successfully")
            else:
                logger.warning("Failed to start Telegram message monitoring. Login may be required.")
            
            # Start the health check task for real-time diagnostics
            await start_health_check_task()
            logger.info("Health check monitoring task started")
    
        return standardize_response(
            {
                "keywords": user_keywords.keywords,
                "added_count": added_count
            },
            f"{added_count} keywords added successfully"
        )
    except ValueError as e:
        # Handle JSON parsing errors
        logger.error(f"Invalid request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")
    except Exception as e:
        logger.error(f"Failed to add keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add keywords: {str(e)}")

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
    
    try:
        # Reset the active user ID in the monitor service
        await stop_monitoring()
        logger.info(f"Stopped monitoring for user {user.id}")
        
        # Log out from Telegram
        await client.log_out()
        logger.info(f"User {user.id} logged out successfully")
        
        # Clear user's active session from database
        stmt = select(ActiveSession).where(ActiveSession.user_id == user.id)
        result = await db.execute(stmt)
        active_session = result.scalars().first()
        
        if active_session:
            await db.delete(active_session)
            await db.commit()
        
        # Delete the Telethon session file
        try:
            # Check if user-specific session exists and delete it
            if os.path.exists(session_path):
                os.remove(session_path)
                logger.info(f"Deleted user-specific session file: {session_path}")

            # Check for and delete any additional session files that might exist
            for session_file in os.listdir(session_dir):
                if session_file.startswith("user_session") and session_file.endswith(".session"):
                    file_path = os.path.join(session_dir, session_file)
                    os.remove(file_path)
                    logger.info(f"Deleted session file: {file_path}")
                    
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