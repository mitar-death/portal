from fastapi import Request, HTTPException
from server.app.core.logging import logger
from server.app.core.databases import db_context
from server.app.models.models import User, AIAccount
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Any, Optional
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import os


async def get_ai_accounts(request: Request):
    """
    Get all AI accounts for the current user.
    """
    try:
        user = request.state.user
        db = db_context.get()   
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Query all AI accounts for this user
        stmt = select(AIAccount).where(AIAccount.user_id == user.id)
        result = await db.execute(stmt)
        accounts = result.scalars().all()
        
        # Convert to list of dicts for JSON response
        account_list = [
            {
                "id": account.id,
                "name": account.name,
                "phone_number": account.phone_number,
                "is_active": account.is_active,
                "created_at": account.created_at.isoformat() if account.created_at else None
            }
            for account in accounts
        ]
        
        return {"accounts": account_list}
            
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_ai_accounts: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in get_ai_accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def create_ai_account(request: Request):
    """
    Create a new AI account for the current user.
    """
    try:
        user = request.state.user
        db = db_context.get()
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Parse the request body
        body = await request.json()
        name = body.get("name")
        phone_number = body.get("phone_number")
        api_id = body.get("api_id")
        api_hash = body.get("api_hash")
        
        # Validate required fields
        if not all([name, phone_number, api_id, api_hash]):
            return {
                "success": False,
                "error": "Missing required fields",
                "details": "Please provide name, phone_number, api_id, and api_hash."
            }
        
        # Create a new AI account
       
        new_account = AIAccount(
            user_id=user.id,
            name=name,
            phone_number=phone_number,
            api_id=api_id,
            api_hash=api_hash,
            is_active=True
        )
        
        db.add(new_account)
        await db.commit()
        await db.refresh(new_account)
        
        return {
            "success": True,
            "account_id": new_account.id,
            "message": f"AI account '{name}' created successfully"
        }
            
    except SQLAlchemyError as e:
        logger.error(f"Database error in create_ai_account: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in create_ai_account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def update_ai_account(request: Request):
    """
    Update an existing AI account.
    """
    try:
        user = request.state.user
        
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")
        name = body.get("name")
        is_active = body.get("is_active")
        
        if not account_id:
            return {
                "success": False,
                "error": "Missing account_id",
                "details": "Please provide the account_id to update."
            }
        
        # Update the account
        async with db_context.get_session() as session:
            # Get the account and verify ownership
            stmt = select(AIAccount).where(
                AIAccount.id == account_id,
                AIAccount.user_id == user.id
            )
            result = await session.execute(stmt)
            account = result.scalars().first()
            
            if not account:
                return {
                    "success": False,
                    "error": "Account not found",
                    "details": "The specified account was not found or does not belong to this user."
                }
            
            # Update fields
            if name is not None:
                account.name = name
            if is_active is not None:
                account.is_active = is_active
                
            await session.commit()
            
            return {
                "success": True,
                "message": f"AI account updated successfully"
            }
            
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_ai_account: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in update_ai_account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def delete_ai_account(request: Request):
    """
    Delete an AI account.
    """
    try:
        user = request.state.user
        db = db_context.get()
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")
        
        if not account_id:
            return {
                "success": False,
                "error": "Missing account_id",
                "details": "Please provide the account_id to delete."
            }
        
        # Delete the account
        
        # Get the account and verify ownership
        stmt = select(AIAccount).where(
            AIAccount.id == account_id,
            AIAccount.user_id == user.id
        )
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        if not account:
            return {
                "success": False,
                "error": "Account not found",
                "details": "The specified account was not found or does not belong to this user."
            }
        
        # Delete the associated session file if it exists
        try:
            sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
            session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")
            session_file = f"{session_path}.session"
            
            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info(f"Deleted session file for account {account.id}: {session_file}")
        except Exception as e:
            logger.error(f"Error deleting session file: {e}")
            # Continue with account deletion even if session file deletion fails
        
        # Delete the account from the database
        
        # Delete the account
        await db.delete(account)
        await db.commit()
        
        return {
            "success": True,
            "message": f"AI account deleted successfully"
        }
            
    except SQLAlchemyError as e:
        logger.error(f"Database error in delete_ai_account: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in delete_ai_account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def test_ai_account(request: Request):
    """
    Test the connection for an AI account.
    This attempts to connect to Telegram with the provided credentials.
    """
    try:
        user = request.state.user
        db = db_context.get()
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")
        
        if not account_id:
            return {
                "success": False,
                "error": "Missing account_id",
                "details": "Please provide the account_id to test."
            }
        
        # Get the account
        
        stmt = select(AIAccount).where(
            AIAccount.id == account_id,
            AIAccount.user_id == user.id
        )
        result = await db.execute(stmt)
        account = result.scalars().first()
        logger.info(f"{account.name} Telegram credentials : {account.phone_number}, API ID: {account.api_id}, API Hash: {account.api_hash}")
        if not account:
            return {
                "success": False,
                "error": "Account not found",
                "details": "The specified account was not found or does not belong to this user."
            }
        
        # Define session path for AI accounts
        sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
        os.makedirs(sessions_dir, exist_ok=True)
        session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")
        
        # Try to connect to Telegram
        client = TelegramClient(
            session_path, 
            api_id=account.api_id, 
            api_hash=account.api_hash
        )
        
        try:
            await client.connect()
            is_authorized = await client.is_user_authorized()
            
            if is_authorized:
                return {
                    "success": True,
                    "is_authorized": True,
                    "session_path": session_path,
                    "message": "Successfully connected and authorized with Telegram"
                }
            else:
                return {
                    "success": True,
                    "is_authorized": False,
                    "message": "Connected to Telegram but not authorized. Login required."
                }
                
        finally:
            if client.is_connected():
                await client.disconnect()
                    
    except SQLAlchemyError as e:
        logger.error(f"Database error in test_ai_account: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in test_ai_account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def login_ai_account(request: Request):
    """
    Login to an AI account by requesting a verification code and then verifying it.
    This is a two-step process:
    1. Request code (sends code to the phone)
    2. Submit code (verifies the code and completes login)
    """
    try:
        user = request.state.user
        db = db_context.get()
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")
        action = body.get("action", "request_code")  # request_code or verify_code
        phone_code = body.get("phone_code")
        password = body.get("password")  # For 2FA if needed
        
        if not account_id:
            return {
                "success": False,
                "error": "Missing account_id",
                "details": "Please provide the account_id to login."
            }
        
        # Get the account
      
        stmt = select(AIAccount).where(
            AIAccount.id == account_id,
            AIAccount.user_id == user.id
        )
        result = await db.execute(stmt)
        account = result.scalars().first()
        
        if not account:
            return {
                "success": False,
                "error": "Account not found",
                "details": "The specified account was not found or does not belong to this user."
            }
        
        # Create a session name based on account ID
        sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
        os.makedirs(sessions_dir, exist_ok=True)
        session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")

        logger.info(f"{account.name} Telegram credentials : {account.phone_number}, API ID: {account.api_id}, API Hash: {account.api_hash}")
        # Create a Telegram client
        client = TelegramClient(
            session_path, 
            api_id=account.api_id, 
            api_hash=account.api_hash
        )
        
        await client.connect()
        
        # Check if already authorized
        if await client.is_user_authorized():
            await client.disconnect()
            return {
                "success": True,
                "action": "already_authorized",
                "message": "Account is already authorized."
            }
        
        if action == "request_code":
            # Request verification code
            try:
                phone_number = account.phone_number
                if not phone_number.startswith('+'):
                    phone_number = f"+{phone_number}"
                    
                phone_code_hash = await client.send_code_request(phone_number)
                
                # Store the phone_code_hash in the account for later use
                account.phone_code_hash = phone_code_hash.phone_code_hash
                await db.commit()
                
                await client.disconnect()
                
                return {
                    "success": True,
                    "action": "code_requested",
                    "message": f"Verification code sent to {phone_number}. Please check your Telegram app."
                }
            except Exception as e:
                logger.error(f"Error requesting code: {e}")
                await client.disconnect()
                return {
                    "success": False,
                    "error": "Failed to request verification code",
                    "details": str(e)
                }
        
        elif action == "verify_code":
            # Verify code and complete login
            if not phone_code:
                await client.disconnect()
                return {
                    "success": False,
                    "error": "Missing verification code",
                    "details": "Please provide the verification code."
                }
            
            try:
                phone_number = account.phone_number
                if not phone_number.startswith('+'):
                    phone_number = f"+{phone_number}"
                    
                # Get stored phone_code_hash
                phone_code_hash = account.phone_code_hash
                
                try:
                    # Try to sign in
                    await client.sign_in(phone_number, phone_code, phone_code_hash=phone_code_hash)
                except SessionPasswordNeededError:
                    # 2FA is enabled
                    if not password:
                        await client.disconnect()
                        return {
                            "success": False,
                            "action": "password_required",
                            "error": "Two-factor authentication is enabled",
                            "details": "Please provide your 2FA password."
                        }
                    
                    # Try to sign in with password
                    await client.sign_in(password=password)
                
                # Successfully signed in
                await client.disconnect()
                
                # Clear the phone_code_hash
                account.phone_code_hash = None
                await db.commit()
                
                return {
                    "success": True,
                    "action": "signed_in",
                    "message": "Successfully logged into the account."
                }
            except PhoneCodeInvalidError:
                await client.disconnect()
                return {
                    "success": False,
                    "error": "Invalid verification code",
                    "details": "The verification code is incorrect. Please try again."
                }
            except Exception as e:
                logger.error(f"Error verifying code: {e}")
                await client.disconnect()
                return {
                    "success": False,
                    "error": "Failed to verify code",
                    "details": str(e)
                }
        
        else:
            await client.disconnect()
            return {
                "success": False,
                "error": "Invalid action",
                "details": "Action must be either 'request_code' or 'verify_code'."
            }
                
    except SQLAlchemyError as e:
        logger.error(f"Database error in login_ai_account: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in login_ai_account: {e}")
        raise HTTPException(status_code=500, detail=str(e))
