"""
Cleanup utilities for the TGPortal application
"""
import os
import shutil
from fastapi import Request, HTTPException
from sqlalchemy import select
from server.app.core.logging import logger
from server.app.core.databases import db_context
from server.app.models.models import AIAccount

async def cleanup_ai_sessions(request: Request = None, user_id: int = None):
    """
    Clean up all session files for AI accounts belonging to a user.
    This can be called with either a request object (which contains the user in state)
    or directly with a user_id.
    """
    try:
        # Get user ID either from request or parameter
        if request and hasattr(request.state, 'user') and request.state.user:
            user = request.state.user
            user_id = user.id
        elif not user_id:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Get all AI accounts for this user
        db = db_context.get()
        stmt = select(AIAccount).where(AIAccount.user_id == user_id)
        result = await db.execute(stmt)
        accounts = result.scalars().all()
        
        if not accounts:
            return {
                "success": True,
                "message": "No AI accounts found for cleanup.",
                "deleted_count": 0
            }
        
        # Delete session files for each account
        deleted_count = 0
        sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
        
        if not os.path.exists(sessions_dir):
            return {
                "success": True,
                "message": "Sessions directory does not exist.",
                "deleted_count": 0
            }
        
        for account in accounts:
            session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")
            session_file = f"{session_path}.session"
            
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                    deleted_count += 1
                    logger.info(f"Deleted session file for account {account.id}: {session_file}")
                except Exception as e:
                    logger.error(f"Error deleting session file for account {account.id}: {e}")
        
        return {
            "success": True,
            "message": f"Successfully cleaned up {deleted_count} session files.",
            "deleted_count": deleted_count
        }
            
    except Exception as e:
        logger.error(f"Error in cleanup_ai_sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def logout_ai_account(request: Request):
    """
    Logout from a specific AI account by deleting its session file.
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
                "details": "Please provide the account_id to logout."
            }
        
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
        
        # Delete the session file
        sessions_dir = os.path.join('storage', 'sessions', 'ai_accounts')
        session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")
        session_file = f"{session_path}.session"
        
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info(f"Deleted session file for account {account.id}: {session_file}")
                return {
                    "success": True,
                    "message": f"Successfully logged out from account '{account.name}'."
                }
            except Exception as e:
                logger.error(f"Error deleting session file: {e}")
                return {
                    "success": False,
                    "error": "Failed to delete session file",
                    "details": str(e)
                }
        else:
            return {
                "success": True,
                "message": f"No active session found for account '{account.name}'."
            }
            
    except Exception as e:
        logger.error(f"Error in logout_ai_account: {e}")
        raise HTTPException(status_code=500, detail=str(e))
