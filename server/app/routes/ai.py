
from fastapi import APIRouter, Request

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

ai_routes = APIRouter()
# AI Account Routes
@ai_routes.get('/ai/accounts', tags=['AI'])
async def get_user_ai_accounts(request: Request):
    """
    Get all AI accounts for the current user.
    """
    return await get_ai_accounts(request)

@ai_routes.post('/ai/accounts', tags=['AI'])
async def create_new_ai_account(request: Request):
    """
    Create a new AI account for the current user.
    """
    return await create_ai_account(request)

@ai_routes.put('/ai/accounts', tags=['AI'])
async def update_existing_ai_account(request: Request):
    """
    Update an existing AI account.
    """
    return await update_ai_account(request)

@ai_routes.delete('/ai/accounts/delete', tags=['AI'])
async def delete_existing_ai_account(request: Request):
    """
    Delete an AI account.
    """
    return await delete_ai_account(request)

@ai_routes.post('/ai/accounts/test', tags=['AI'])
async def test_existing_ai_account(request: Request):
    """
    Test the connection for an AI account.
    """
    return await test_ai_account(request)

@ai_routes.post('/ai/accounts/login', tags=['AI'])
async def login_existing_ai_account(request: Request):
    """
    Login to an AI account by requesting and verifying a code.
    """
    return await login_ai_account(request)

@ai_routes.post('/ai/accounts/logout', tags=['AI'])
async def logout_existing_ai_account(request: Request):
    """
    Logout from an AI account by deleting its session file.
    """
    return await logout_ai_account(request)

@ai_routes.post('/ai/accounts/cleanup-sessions', tags=['AI'])
async def cleanup_ai_account_sessions(request: Request):
    """
    Clean up all session files for the user's AI accounts.
    """
    return await cleanup_ai_sessions(request)

# Group AI Assignment Routes
@ai_routes.get('/ai/group-assignments', tags=['AI'])
async def get_ai_group_assignments(request: Request):
    """
    Get all AI account assignments for the user's groups.
    """
    return await get_group_ai_assignments(request)

@ai_routes.post('/ai/group-assignments', tags=['AI'])
async def update_ai_group_assignment(request: Request):
    """
    Update the AI account assignment for a group.
    """
    return await update_group_ai_assignment(request)