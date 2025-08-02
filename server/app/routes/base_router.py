from fastapi import APIRouter, Depends,Request, HTTPException, Header
from typing import Optional, Dict, Any

from server.app.schemas.schemas import (
    SendCodeRequest, 
    CodeVerification, 
    AuthResponse, 
    GroupsResponse,
    SelectedGroupsRequest
)
from server.app.controllers.ai import (
    test_ai_controller
    )
from server.app.controllers.ai_accounts import (
    get_ai_accounts,
    create_ai_account,
    update_ai_account,
    delete_ai_account,
    test_ai_account,
    login_ai_account
)
from server.app.controllers.cleanup import (
    logout_ai_account,
    cleanup_ai_sessions
)
from server.app.controllers.group_ai_assignment import (
    get_group_ai_assignments,
    update_group_ai_assignment
)
from server.app.controllers.diagnostics import (
    get_ai_diagnostics,
    reinitialize_ai_messenger
)
from server.app.controllers.main import (
    request_code,
    verify_code,
    get_user_groups,
    monitor_groups,
    get_keywords_controller,
    add_keywords_controller,
    logout_telegram as telegram_logout_service  # Rename the import
)
from server.app.controllers.auth import check_auth_status
from server.app.core.logging import logger
from server.app.services.monitor import keywords

router = APIRouter()


@router.get('/', tags=['Base'])
async def index():
    """Root endpoint"""
    return {"message": "Welcome to the TGPortal API"}

@router.post('/ai', tags=['Base'])
async def ai_test(request:Request):
    """Test ai endpoint"""
    return await test_ai_controller(request)



@router.post('/auth/request-code', tags=['Auth'], response_model=Dict[str, Any])
async def request_login_code(
    request: Request,
    ):
    """
    Request Telegram verification code for login
    """
    return await request_code(request)


@router.get('/auth/status', tags=['Auth'])
async def check_auth_status_endpoint(request: Request):
    """
    Check the current Telegram authentication status.
    """
    return await check_auth_status(request)


@router.post('/auth/verify-code', tags=['Auth'], response_model=AuthResponse)
async def verify_login_code(verification: CodeVerification):
    """
    Verify Telegram login code
    """
    return await verify_code(verification.phone_number, verification.code, verification.phone_code_hash)

@router.post('/add/selected-groups', tags=['Telegram'], response_model=GroupsResponse)
async def add_selected_groups(
    request: Request,
    selected_groups: SelectedGroupsRequest):
    """
    Add selected Telegram groups for monitoring
    """

    groups = await monitor_groups(request,selected_groups)
    return {"groups": groups}

@router.get('/telegram/groups', tags=['Telegram'], response_model=GroupsResponse)
async def get_groups(
   request: Request):
    """
    Get user's Telegram groups
    """

    groups = await get_user_groups(request)
    return {"groups": groups}

@router.get('/keywords', tags=['Keywords'])
async def get_keywords(request:Request):
    """
    Get the list of keywords for message filtering.
    """
    return await get_keywords_controller(request)

@router.post('/add/keywords', tags=['Keywords'])
async def add_keywords(request:Request):
    """
    Add keywords for message filtering.
    """
    return await add_keywords_controller(request)

# AI Account Routes
@router.get('/ai/accounts', tags=['AI'])
async def get_user_ai_accounts(request: Request):
    """
    Get all AI accounts for the current user.
    """
    return await get_ai_accounts(request)

@router.post('/ai/accounts', tags=['AI'])
async def create_new_ai_account(request: Request):
    """
    Create a new AI account for the current user.
    """
    return await create_ai_account(request)

@router.put('/ai/accounts', tags=['AI'])
async def update_existing_ai_account(request: Request):
    """
    Update an existing AI account.
    """
    return await update_ai_account(request)

@router.delete('/ai/accounts', tags=['AI'])
async def delete_existing_ai_account(request: Request):
    """
    Delete an AI account.
    """
    return await delete_ai_account(request)

@router.post('/ai/accounts/test', tags=['AI'])
async def test_existing_ai_account(request: Request):
    """
    Test the connection for an AI account.
    """
    return await test_ai_account(request)

@router.post('/ai/accounts/login', tags=['AI'])
async def login_existing_ai_account(request: Request):
    """
    Login to an AI account by requesting and verifying a code.
    """
    return await login_ai_account(request)

@router.post('/ai/accounts/logout', tags=['AI'])
async def logout_existing_ai_account(request: Request):
    """
    Logout from an AI account by deleting its session file.
    """
    return await logout_ai_account(request)

@router.post('/ai/accounts/cleanup-sessions', tags=['AI'])
async def cleanup_ai_account_sessions(request: Request):
    """
    Clean up all session files for the user's AI accounts.
    """
    return await cleanup_ai_sessions(request)

# Group AI Assignment Routes
@router.get('/ai/group-assignments', tags=['AI'])
async def get_ai_group_assignments(request: Request):
    """
    Get all AI account assignments for the user's groups.
    """
    return await get_group_ai_assignments(request)

@router.post('/ai/group-assignments', tags=['AI'])
async def update_ai_group_assignment(request: Request):
    """
    Update the AI account assignment for a group.
    """
    return await update_group_ai_assignment(request)

@router.post('/auth/logout', tags=['Auth'])
async def logout_user(request: Request):
    """
    Log out the user from Telegram and clear the session.
    """
    return await telegram_logout_service(request)

@router.get('/diagnostics', tags=['Diagnotics'])
async def get_diagnostics(request: Request):
    """
    Get diagnostic information about the AI messenger system.
    Provides detailed status of AI clients, group mappings, and monitoring.
    """
    return await get_ai_diagnostics(request)

@router.post('/diagnostics/reinitialize', tags=['Diagnotics'])
async def reinitialize_ai(request: Request):
    """
    Force reinitialization of the AI messenger system.
    This can be used to recover from a state where the AI messenger has stopped responding.
    """
    return await reinitialize_ai_messenger(request)