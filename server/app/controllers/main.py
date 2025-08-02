from typing import Dict, Any, List
from sqlalchemy import select
from fastapi import HTTPException,Request

from telethon.sync import TelegramClient
from server.app.core.databases import db_context
from server.app.models.models import ActiveSession
from server.app.models.models import SelectedGroup, User,Keywords
from server.app.core.config import settings
from server.app.core.logging import logger

from server.app.services.monitor import keywords, start_monitoring


from typing import Dict, Any, List
from sqlalchemy import select
from fastapi import HTTPException,Request

from telethon.sync import TelegramClient
from server.app.core.databases import db_context
from server.app.models.models import ActiveSession
from server.app.models.models import SelectedGroup, User
from server.app.core.config import settings
from server.app.core.logging import logger
import os

from server.app.services.telegram import get_client
# We'll connect the client when needed
async def request_code(request:Request) -> Dict[str, Any]:
    """
    Request a login code from Telegram for the given phone number.
    """

    db = db_context.get()
    user = getattr(request.state, "user", None)
    
    try:
        body = await request.json()
        phone_number = body.get("phone_number")
        if not phone_number:
            raise HTTPException(status_code=400, detail="Phone number is required")
            
        logger.info(f"Requesting code for phone number: {phone_number}")
        client = get_client()
        # Ensure client is connected
        if not client.is_connected():
            await client.connect()
        
        if await client.is_user_authorized():
            logger.info(f"User already authorized with phone {phone_number}")
            return {
                "success": True, 
                "message": "Already authorized",
                "action": "already_authorized",
                "phone_code_hash": "" # Empty hash since no code is needed
            }
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
        
        
        logger.info(f"Code requested for {phone_number}, phone_code_hash: {response.phone_code_hash}")
        
        return {"message": "Verification code sent to your phone", "success": True,"phone_code_hash":response.phone_code_hash }
        
    except Exception as e:
        logger.error(f"Failed to send code request: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification code")


async def verify_code(phone_number: str, code: str, phone_code_hash: str) -> Dict[str, Any]:
    """
    Verify the code provided by the user.
    """
    db = db_context.get()
    client = get_client()
    # Ensure client is connected
    if not client.is_connected():
        await client.connect()
    
    # Check if we have an active session
    stmt = select(ActiveSession).where(ActiveSession.phone_number == phone_number)
    result = await db.execute(stmt)
    session = result.scalars().first()
    
    if not session or not session.code_requested:
        raise HTTPException(status_code=400, detail="No active login session found")
    
    try:
        response = await client.sign_in(phone=phone_number, code =code,phone_code_hash=phone_code_hash)
        logger.info(f"User {response} verified successfully")
       
        session.verified = True
        db.add(session)
        await db.commit()
            
        # Check if user exists in database
        user_stmt = select(User).where(User.phone_number == phone_number)
        user_result = await db.execute(user_stmt)
        user = user_result.scalars().first()
        tg_id = str(response.id)
        
        if not user:
            # Create a new user
            user = User(
                telegram_id=tg_id,  # In production, get from Telegram
                username=response.username if response.username else None,
                first_name=response.first_name if response.first_name else "User",
                last_name=response.last_name if response.last_name else None,
                phone_number=phone_number
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
        token = f"token_{user.id}"
            
        user_data = {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number
        }
           
        return {
            "message": "Successfully logged in",
            "success": True,
            "user": user_data,
            "token": token
        }
    except Exception as e:
        if not isinstance(e, HTTPException):
            logger.error(f"Failed to verify code: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to verify code: {str(e)}")
        raise e

async def get_user_groups(request) -> List[Dict[str, Any]]:
    """
    Fetch the user's Telegram groups using the current authenticated Telegram session.
    Also saves or updates group information in the database.
    """
    db = db_context.get()
    user = getattr(request.state, "user", None)
    client = get_client()
    # Ensure client is connected
    if not client.is_connected():
        await client.connect()
    
    if not await client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Telegram session not authorized")
    
    try:
        # Fetch actual groups from Telegram
        dialogs = await client.get_dialogs()
        groups = []
        
        for dialog in dialogs:
            entity = dialog.entity
            
            # Check if it's a group or channel (not a private chat)
            if hasattr(entity, 'title'):
                group_data = {
                    "id": entity.id,
                    "title": entity.title,
                    "member_count": getattr(entity, 'participants_count', 0),
                    "description": getattr(entity, 'about', None),
                    "username": getattr(entity, 'username', None),
                    "is_channel": hasattr(entity, 'broadcast') and entity.broadcast
                }
                groups.append(group_data)
                
                # Save or update group in database if user is authenticated
                if user:
                    # Check if group already exists in the database
                    from server.app.models.models import Group
                    stmt = select(Group).where(
                        Group.user_id == user.id,
                        Group.telegram_id == entity.id
                    )
                    result = await db.execute(stmt)
                    existing_group = result.scalars().first()
                    
                    if existing_group:
                        # Update existing group with latest info
                        existing_group.title = entity.title
                        existing_group.username = getattr(entity, 'username', None)
                        existing_group.description = getattr(entity, 'about', None)
                        existing_group.member_count = getattr(entity, 'participants_count', 0)
                        existing_group.is_channel = hasattr(entity, 'broadcast') and entity.broadcast
                        db.add(existing_group)
                    else:
                        # Create new group
                        new_group = Group(
                            user_id=user.id,
                            telegram_id=entity.id,
                            title=entity.title,
                            username=getattr(entity, 'username', None),
                            description=getattr(entity, 'about', None),
                            member_count=getattr(entity, 'participants_count', 0),
                            is_channel=hasattr(entity, 'broadcast') and entity.broadcast
                        )
                        db.add(new_group)
                        
                        # Also add a record with the -100 prefixed ID for compatibility
                        str_id = str(entity.id)
                        if not str_id.startswith('-100'):
                            prefixed_id = f"-100{str_id}"
                            logger.info(f"Storing additional group record with prefixed ID: {prefixed_id}")
                            prefixed_group = Group(
                                user_id=user.id,
                                telegram_id=prefixed_id,
                                title=f"{entity.title} (prefixed ID)",
                                username=getattr(entity, 'username', None),
                                description=getattr(entity, 'about', None),
                                member_count=getattr(entity, 'participants_count', 0),
                                is_channel=hasattr(entity, 'broadcast') and entity.broadcast
                            )
                            db.add(prefixed_group)
                
            # Commit all changes to the database
            if user:
                await db.commit()
        
        logger.info(f"Retrieved {len(groups)} groups for user {user.id if user else 'unknown'}")
        return groups
        
    except Exception as e:
        logger.error(f"Failed to fetch groups: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch groups: {str(e)}")


async def monitor_groups(request,selected_groups: Dict[str, Any]) -> List[Dict[str, Any]]: 
    """
    Add selected Telegram groups for monitoring.
    """
    db = db_context.get()
    client =  get_client()
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")
        
    logger.info(f"Adding selected groups for user {user.id} with group IDs: {selected_groups.group_ids}")
    
    # Ensure client is connected
    if not client.is_connected():
        await client.connect()
    
    if not await client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Telegram session not authorized")
    
    try:
        groups = []

        for group_id in selected_groups.group_ids:
            # Create selectedGroups relationship if it doesn't exist
            selected_group_stmt = select(SelectedGroup).where(
                SelectedGroup.user_id == int(user.id),
                SelectedGroup.group_id == str(group_id)
            )
            selected_group_result = await db.execute(selected_group_stmt)
            selected_group = selected_group_result.scalars().first()
            
            if not selected_group:
                selected_group = SelectedGroup(
                    user_id=user.id,
                    group_id=group_id
                )
                db.add(selected_group)
                await db.commit()
            
            # Fetch the group details from Telegram to ensure it matches the TelegramGroup schema
            # try:
            #     entity = await client.get_entity(group_id)
            #     group_data = {
            #         "id": entity.id,
            #         "title": entity.title,
            #         "member_count": getattr(entity, 'participants_count', 0),
            #         "description": getattr(entity, 'about', None),
            #         "username": getattr(entity, 'username', None),
            #         "is_channel": hasattr(entity, 'broadcast') and entity.broadcast
            #     }
            #     groups.append(group_data)
            # except Exception as e:
            #     # If we can't get the entity, add minimal data that satisfies the schema
            #     logger.warning(f"Could not get entity for group {group_id}: {e}")
            #     groups.append({
            #         "id": group_id,
            #         "title": f"Group {group_id}",
            #         "member_count": 0,
            #         "is_channel": False
            #     })
        
        # logger.info(f"Added {len(groups)} groups for monitoring for user {user.id}")
        
        # Restart monitoring with updated group selections
        # await start_monitoring(user.id)
        return groups
        
    except Exception as e:
        logger.error(f"Failed to add selected groups: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add selected groups: {str(e)}")
    finally:
        # Ensure the client is disconnected after operation
        if client.is_connected():
            await client.disconnect()
        logger.info("Disconnected Telegram client")


async def get_keywords_controller(request: Request) -> Dict[str, Any]:
    """
    Get the list of keywords for message filtering.
    """
    db = db_context.get()
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")

    try:
        # Execute a proper SQLAlchemy query using the ORM
        stmt = select(Keywords).where(Keywords.user_id == user.id)
        result = await db.execute(stmt)
        user_keywords = result.scalars().first()
        
        # Get the keywords list or empty list if no record exists
        keywords_list = user_keywords.keywords if user_keywords else []
        
        return {
            "message": "Keywords fetched successfully",
            "success": True,
            "data": {
                "keywords": keywords_list,
                "count": len(keywords_list)
            }
        }
    except Exception as e:
        logger.error(f"Failed to fetch keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch keywords: {str(e)}")

async def add_keywords_controller(request: Request) -> Dict[str, Any]:
    """
    Adds new keywords for message filtering.
    """
    db = db_context.get()
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")

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
        
        return {
            "message": f"{added_count} keywords added successfully", 
            "success": True,
            "data": {
                "keywords": user_keywords.keywords,
                "added_count": added_count
            }
        }
    except ValueError as e:
        # Handle JSON parsing errors
        logger.error(f"Invalid request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")
    except Exception as e:
        logger.error(f"Failed to add keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add keywords: {str(e)}")

async def logout_telegram(request) -> Dict[str, Any]:
    """
    Log out the user from Telegram and clear the session.
    """
    db = db_context.get()
    user = getattr(request.state, "user", None)
    
    if not user:
        raise HTTPException(status_code=401, detail="User not authenticated")
    client = await get_client()
    # Stop monitoring before logout
    
    # Ensure client is connected
    if not client.is_connected():
        await client.connect()
    
    try:
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
        # try:
        #     # Get the session file path
        #     user_session_path = str(session_dir / f"user_session_{user.id}.session")
        #     default_session_path = str(session_dir / "user_session.session")
            
        #     # Check if user-specific session exists and delete it
        #     if os.path.exists(user_session_path):
        #         os.remove(user_session_path)
        #         logger.info(f"Deleted user-specific session file: {user_session_path}")
            
        #     # Also check if the default session exists and delete it
        #     if os.path.exists(default_session_path):
        #         os.remove(default_session_path)
        #         logger.info(f"Deleted default session file: {default_session_path}")
                
        #     # Check for and delete any additional session files that might exist
        #     for session_file in session_dir.glob("*.session"):
        #         if str(session_file).startswith(str(session_dir / "user_session")):
        #             os.remove(session_file)
        #             logger.info(f"Deleted session file: {session_file}")
        # except Exception as e:
        #     logger.error(f"Error deleting session file: {e}")
        #     # Continue with logout even if file deletion fails
        
        return {"message": "Successfully logged out", "success": True}
        
    except Exception as e:
        logger.error(f"Failed to log out: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log out: {str(e)}")
    finally:
        # Ensure the client is disconnected after operation
        if client.is_connected():
            await client.disconnect()
        logger.info("Disconnected Telegram client")