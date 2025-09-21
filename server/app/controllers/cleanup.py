"""
Cleanup utilities for the TGPortal application
"""

import os
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from server.app.core.logging import logger
from server.app.models.models import AIAccount
from server.app.utils.controller_helpers import (
    ensure_user_authenticated,
    safe_db_operation,
    sanitize_log_data,
    standardize_response,
)


@safe_db_operation()
async def cleanup_ai_sessions(
    request: Request = None, user_id: Optional[int] = None, db: AsyncSession = None
) -> Dict[str, Any]:
    """
    Clean up all session files for AI accounts belonging to a user.
    This can be called with either a request object (which contains the user in state)
    or directly with a user_id.

    Args:
        request: The HTTP request (optional)
        user_id: User ID to clean up sessions for (optional if request is provided)
        db: Database session (injected by decorator)

    Returns:
        Dict with success status, message, and deletion count
    """
    try:
        # Get user ID either from request or parameter
        user = await ensure_user_authenticated(request)

        # Get all AI accounts for this user
        stmt = select(AIAccount).where(AIAccount.user_id == user.id)
        result = await db.execute(stmt)
        accounts = result.scalars().all()

        if not accounts:
            return standardize_response(
                {"deleted_count": 0}, "No AI accounts found for cleanup."
            )

        # Delete session files for each account
        deleted_count = 0
        sessions_dir = os.path.join("storage", "sessions", "ai_accounts")

        if not os.path.exists(sessions_dir):
            return standardize_response(
                {"deleted_count": 0}, "Sessions directory does not exist."
            )

        for account in accounts:
            session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")
            session_file = f"{session_path}.session"

            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                    deleted_count += 1
                    logger.info(f"Deleted session file for account {account.id}")
                except Exception as e:
                    logger.error(
                        f"Error deleting session file for account {account.id}: {sanitize_log_data(str(e))}"
                    )

        return standardize_response(
            {"deleted_count": deleted_count},
            f"Successfully cleaned up {deleted_count} session files.",
        )

    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e
    except SQLAlchemyError as e:
        logger.error(
            f"Database error in cleanup_ai_sessions: {sanitize_log_data(str(e))}"
        )
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in cleanup_ai_sessions: {sanitize_log_data(str(e))}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from e


@safe_db_operation()
async def logout_ai_account(
    request: Request, db: AsyncSession = None
) -> Dict[str, Any]:
    """
    Logout from a specific AI account by deleting its session file.

    Args:
        request: The HTTP request containing user and account information
        db: Database session (injected by decorator)

    Returns:
        Dict with success status and message
    """
    try:
        user = await ensure_user_authenticated(request)

        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")

        if not account_id:
            return standardize_response(
                {"details": "Please provide the account_id to logout."},
                "Missing account_id",
                400,
            )

        # Get the account and verify ownership
        stmt = select(AIAccount).where(
            AIAccount.id == account_id, AIAccount.user_id == user.id
        )
        result = await db.execute(stmt)
        account = result.scalars().first()

        if not account:
            return standardize_response(
                {
                    "details": "The specified account was not found or does not belong to this user."
                },
                "Account not found",
                404,
            )

        # Delete the session file
        sessions_dir = os.path.join("storage", "sessions", "ai_accounts")
        session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")
        session_file = f"{session_path}.session"

        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                logger.info(
                    f"Deleted session file for account {account.id}: {sanitize_log_data(session_file)}"
                )
                return standardize_response(
                    {}, f"Successfully logged out from account '{account.name}'."
                )
            except Exception as e:
                logger.error(
                    f"Error deleting session file: {sanitize_log_data(str(e))}"
                )
                return standardize_response(
                    {"details": str(e)}, "Failed to delete session file", 500
                )
        else:
            return standardize_response(
                {}, f"No active session found for account '{account.name}'."
            )

    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e
    except SQLAlchemyError as e:
        logger.error(
            f"Database error in logout_ai_account: {sanitize_log_data(str(e))}"
        )
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in logout_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from e
