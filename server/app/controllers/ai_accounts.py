import os
from typing import Dict, Any
from fastapi import Request, HTTPException

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from teleredis import RedisSession

# SERVER packages
from server.app.services.redis_client import init_redis, is_redis_available
from server.app.utils.controller_helpers import (
    ensure_user_authenticated,
    safe_db_operation,
    sanitize_log_data,
    standardize_response,
)
from server.app.core.logging import logger
from server.app.models.models import AIAccount
from server.app.models.models import GroupAIAccount


@safe_db_operation()
async def get_ai_accounts(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Get all AI accounts for the current user.
    """
    try:
        user = await ensure_user_authenticated(request)

        # Query all AI accounts for this user
        stmt = select(AIAccount).where(AIAccount.user_id == user.id)
        result = await db.execute(stmt)
        accounts = result.scalars().all()

        # Convert to list of dicts for JSON response
        account_list = [
            {
                "id": account.id,
                "name": account.name,
                "phone_number": sanitize_log_data(account.phone_number),
                "is_active": account.is_active,
                "shareable_link": account.shareable_link,
                "ai_response_context": account.ai_response_context,
                "created_at": (
                    account.created_at.isoformat() if account.created_at else None
                ),
            }
            for account in accounts
        ]

        return standardize_response(
            {"accounts": account_list}, "AI accounts retrieved successfully"
        )

    except HTTPException as e:
        # Pass through HTTP exceptions raised by ensure_user_authenticated
        raise e from e
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_ai_accounts: {e}")
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in get_ai_accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@safe_db_operation()
async def create_ai_account(
    request: Request, db: AsyncSession = None
) -> Dict[str, Any]:
    """
    Create a new AI account for the current user.
    """
    try:
        user = await ensure_user_authenticated(request)

        # Parse the request body
        body = await request.json()
        name = body.get("name")
        phone_number = body.get("phone_number")
        api_id = body.get("api_id")
        api_hash = body.get("api_hash")

        # Validate required fields
        if not all([name, phone_number, api_id, api_hash]):
            return standardize_response(
                {"details": "Please provide name, phone_number, api_id, and api_hash."},
                "Missing required fields",
                400,
            )

        # Validate that API ID is a valid integer and clean up inputs
        try:
            # Clean up inputs
            api_id = api_id.strip() if isinstance(api_id, str) else api_id
            api_hash = api_hash.strip() if isinstance(api_hash, str) else api_hash
            phone_number = (
                phone_number.strip() if isinstance(phone_number, str) else phone_number
            )

            # Validate API ID can be converted to int
            int(api_id)  # Just validate it can be converted to int

            # API hash should be a 32-character hexadecimal string
            if (
                not isinstance(api_hash, str)
                or len(api_hash) != 32
                or not all(c in "0123456789abcdef" for c in api_hash.lower())
            ):
                return standardize_response(
                    {"details": "API Hash must be a 32-character hexadecimal string."},
                    "Invalid API Hash",
                    400,
                )

        except (ValueError, TypeError):
            return standardize_response(
                {
                    "details": f"API ID must be a valid integer. Got: {api_id} (type: {type(api_id)})"
                },
                "Invalid API ID",
                400,
            )

        # Format phone number
        if not phone_number.startswith("+"):
            phone_number = f"+{phone_number}"

        # Create a new AI account
        new_account = AIAccount(
            user_id=user.id,
            name=name,
            phone_number=phone_number,
            api_id=api_id,
            api_hash=api_hash,
            is_active=True,
        )

        db.add(new_account)
        await db.flush()  # Flush to get the ID
        await db.commit()  # Commit the transaction

        return standardize_response(
            {"account_id": new_account.id}, f"AI account '{name}' created successfully"
        )

    except HTTPException as e:
        # Pass through HTTP exceptions raised by ensure_user_authenticated
        raise e from e
    except SQLAlchemyError as e:
        logger.error(
            f"Database error in create_ai_account: {sanitize_log_data(str(e))}"
        )
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in create_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from e


@safe_db_operation()
async def update_ai_account(
    request: Request, db: AsyncSession = None
) -> Dict[str, Any]:
    """
    Update an existing AI account.
    """
    try:
        user = await ensure_user_authenticated(request)

        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")
        name = body.get("name")
        is_active = body.get("is_active")
        shareable_link = body.get("shareable_link")
        ai_response_context = body.get("ai_response_context")

        if not account_id:
            return standardize_response(
                {"details": "Please provide the account_id to update."},
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

        # Update fields
        if name is not None:
            account.name = name
        if is_active is not None:
            account.is_active = is_active
        if shareable_link is not None:
            account.shareable_link = shareable_link
        if ai_response_context is not None:
            account.ai_response_context = ai_response_context

        return standardize_response(
            {"account_id": account.id},
            "AI account updated successfully",
        )

    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e from e
    except SQLAlchemyError as e:
        logger.error(
            f"Database error in update_ai_account: {sanitize_log_data(str(e))}"
        )
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in update_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from e


@safe_db_operation()
async def delete_ai_account(
    request: Request, db: AsyncSession = None
) -> Dict[str, Any]:
    """
    Delete an AI account.
    This will also delete any related records in the group_ai_accounts table.
    """
    try:
        user = await ensure_user_authenticated(request)

        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")

        if not account_id:
            return standardize_response(
                {"details": "Please provide the account_id to delete."},
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

        logger.info(f"Deleting AI account with ID: {account.id}")

        # Delete the associated session file if it exists
        try:
            sessions_dir = os.path.join("storage", "sessions", "ai_accounts")
            session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")
            session_file = f"{session_path}.session"

            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info(f"Deleted session file for account {account.id}")
        except Exception as e:
            logger.error(f"Error deleting session file: {sanitize_log_data(str(e))}")

        # Delete related group assignments
        delete_stmt = delete(GroupAIAccount).where(
            GroupAIAccount.ai_account_id == account.id
        )
        await db.execute(delete_stmt)
        logger.info(f"Deleted related group assignments for AI account {account.id}")

        # Now delete the account itself
        await db.delete(account)
        await db.commit()
        return standardize_response({}, "AI account deleted successfully")

    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e from e
    except SQLAlchemyError as e:
        logger.error(
            f"Database error in delete_ai_account: {sanitize_log_data(str(e))}"
        )
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in delete_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from e


@safe_db_operation()
async def test_ai_account(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Test the connection for an AI account.
    This attempts to connect to Telegram with the provided credentials.
    """
    client = None
    try:
        user = await ensure_user_authenticated(request)

        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")

        if not account_id:
            return standardize_response(
                {"details": "Please provide the account_id to test."},
                "Missing account_id",
                404,
            )

        # Get the account
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

        logger.info(f"Testing Telegram connection for account: {account.name}")

        # Define session path for AI accounts
        sessions_dir = os.path.join("storage", "sessions", "ai_accounts")
        os.makedirs(sessions_dir, exist_ok=True)
        session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")

        # Try to connect to Telegram
        # Convert api_id to integer since the TelegramClient requires it as an integer
        try:
            # Make sure to strip any whitespace that might be present
            api_id_str = (
                account.api_id.strip()
                if isinstance(account.api_id, str)
                else account.api_id
            )
            api_id_int = int(api_id_str)
            logger.debug(
                f"[test_ai_account] Converted API ID from '{api_id_str}' to integer"
            )
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(
                f"[test_ai_account] Invalid API ID format: {type(account.api_id)}. "
                f"Error: {sanitize_log_data(str(e))}"
            )
            return standardize_response(
                {"details": "API ID must be a numeric value."},
                "Invalid API ID format",
                404,
            )

        client = TelegramClient(
            session_path,
            api_id=api_id_int,
            api_hash=(
                account.api_hash.strip()
                if isinstance(account.api_hash, str)
                else account.api_hash
            ),
        )

        try:
            await client.connect()
            is_authorized = await client.is_user_authorized()

            if is_authorized:
                return standardize_response(
                    {"is_authorized": True, "session_path": session_path},
                    "Successfully connected and authorized with Telegram",
                )
            return standardize_response(
                {"is_authorized": False},
                "Connected to Telegram but not authorized. Login required.",
                200,
            )

        finally:
            if client and client.is_connected():
                await client.disconnect()

    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e from e
    except SQLAlchemyError as e:
        logger.error(f"Database error in test_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in test_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from e
    finally:
        # Ensure the client is disconnected in case of any errors
        if client and client.is_connected():
            await client.disconnect()
            logger.info(f"Disconnected Telegram client for account {account_id}")


@safe_db_operation()
async def login_ai_account(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Login to an AI account by requesting a verification code and then verifying it.
    This is a two-step process:
    1. Request code (sends code to the phone)
    2. Submit code (verifies the code and completes login)
    """
    client = None
    try:
        user = await ensure_user_authenticated(request)

        # Parse the request body
        body = await request.json()
        account_id = body.get("account_id")
        action = body.get("action", "request_code")  # request_code or verify_code
        phone_code = body.get("phone_code")
        password = body.get("password")  # For 2FA if needed

        if not account_id:
            return standardize_response(
                {"details": "Please provide the account_id to login."},
                "Missing account_id",
                400,
            )

        # Get the account
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

        # Create a session name based on account ID
        sessions_dir = os.path.join("storage", "sessions", "ai_accounts")
        os.makedirs(sessions_dir, exist_ok=True)
        session_path = os.path.join(sessions_dir, f"ai_account_{account.id}")

        logger.info(f"Login attempt for account: {account.name}")

        api_id = (
            account.api_id.strip()
            if isinstance(account.api_id, str)
            else account.api_id
        )
        api_hash = (
            account.api_hash.strip()
            if isinstance(account.api_hash, str)
            else account.api_hash
        )

        client = TelegramClient(session_path, api_id=int(api_id), api_hash=api_hash)

        await client.connect()

        # Check if already authorized
        if await client.is_user_authorized():
            await client.disconnect()
            return standardize_response(
                {"action": "already_authorized"},
                "Account is already authorized.",
            )

        if action == "request_code":
            # Request verification code
            phone_number = account.phone_number
            # Clean up phone number
            phone_number = (
                phone_number.strip() if isinstance(phone_number, str) else phone_number
            )

            # Ensure phone number starts with '+'
            if not phone_number.startswith("+"):
                phone_number = f"+{phone_number}"

            logger.info(
                f"Sending code request to phone: {sanitize_log_data(phone_number)}"
            )

            try:
                phone_code_hash = await client.send_code_request(phone=phone_number)

                # Store the phone_code_hash in the account for later use
                account.phone_code_hash = phone_code_hash.phone_code_hash
                db.add(account)
                await db.flush()
                await db.commit()

                await client.disconnect()

                return standardize_response(
                    {"action": "code_requested"},
                    "Verification code sent to your phone. Please check your Telegram app.",
                )
            except Exception as e:
                logger.error(f"Error requesting code: {sanitize_log_data(str(e))}")
                await client.disconnect()
                return standardize_response(
                    {
                        "details": "An error occurred while requesting the verification code."
                    },
                    "Failed to request verification code",
                    400,
                )

        elif action == "verify_code":
            # Verify code and complete login
            if not phone_code:
                await client.disconnect()
                return standardize_response(
                    {"details": "Please provide the verification code."},
                    "Missing verification code",
                    400,
                )

            try:
                phone_number = account.phone_number
                if not phone_number.startswith("+"):
                    phone_number = f"+{phone_number}"

                # Get stored phone_code_hash
                phone_code_hash = account.phone_code_hash

                try:
                    # Try to sign in
                    await client.sign_in(
                        phone_number, phone_code, phone_code_hash=phone_code_hash
                    )
                except SessionPasswordNeededError:
                    # 2FA is enabled
                    if not password:
                        await client.disconnect()
                        return standardize_response(
                            {
                                "action": "password_required",
                                "details": "Please provide your 2FA password.",
                            },
                            "Two-factor authentication is enabled",
                            400,
                        )

                    # Try to sign in with password
                    await client.sign_in(password=password)

                # Successfully signed in
                await client.disconnect()

                # Clear the phone_code_hash
                account.phone_code_hash = None

                return standardize_response(
                    {"action": "signed_in"},
                    "Successfully logged into the account.",
                )
            except PhoneCodeInvalidError:
                await client.disconnect()
                return standardize_response(
                    {
                        "details": "The verification code is incorrect. Please try again."
                    },
                    "Invalid verification code",
                    400,
                )
            except Exception as e:
                logger.error(f"Error verifying code: {sanitize_log_data(str(e))}")
                await client.disconnect()
                return standardize_response(
                    {"details": "An error occurred while verifying the code."},
                    "Failed to verify code",
                    400,
                )

        else:
            await client.disconnect()
            return standardize_response(
                {"details": "Action must be either 'request_code' or 'verify_code'."},
                "Invalid action",
                400,
            )

    except HTTPException as e:
        # Pass through HTTP exceptions
        raise e from e
    except SQLAlchemyError as e:
        logger.error(f"Database error in login_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(status_code=500, detail="Database error") from e
    except Exception as e:
        logger.error(f"Error in login_ai_account: {sanitize_log_data(str(e))}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred"
        ) from e
    finally:
        # Ensure the client is disconnected in case of any errors
        if client and client.is_connected():
            try:
                await client.disconnect()
            except Exception:
                pass


def __init_telegram_client(api_id, api_hash, session_path=None):
    """
    Initialize a Telegram client with Redis or file-based session fallback.

    Args:
        api_id (str): The application ID for the Telegram API.
        api_hash (str): The application hash for the Telegram API.
        session_path (str, optional): Path for file-based session if Redis unavailable.
    """
    try:
        if is_redis_available():
            redis_connection = init_redis(decode_responses=False)
            if redis_connection is not None:
                redis_session = RedisSession(
                    "ai_session_name", redis_connection=redis_connection
                )
                client = TelegramClient(redis_session, api_id, api_hash)
                return client
    except Exception as e:
        logger.warning(f"Failed to initialize Redis session for AI client: {e}")

    # Fallback to file-based session
    if session_path is None:
        session_path = "ai_default_session"

    logger.info(f"Using file-based session for AI client: {session_path}")
    client = TelegramClient(session_path, api_id, api_hash)
    return client
