from fastapi import APIRouter, Request

from server.app.schemas.schemas import (
    CodeVerification,
    AuthResponse,
)
from server.app.controllers.main import (
    verify_code, )
from server.app.controllers.auth import (check_auth_status, logout_telegram as
                                         telegram_logout_service,
                                         refresh_access_token, logout_user as
                                         jwt_logout_service)

auth_routes = APIRouter()


@auth_routes.get('/auth/status', tags=['Auth'])
async def check_auth_status_endpoint(request: Request):
    """
    Check the current Telegram authentication status.
    """
    return await check_auth_status(request)


@auth_routes.post('/auth/verify-code',
                  tags=['Auth'],
                  response_model=AuthResponse)
async def verify_login_code(request: Request, verification: CodeVerification):
    """
    Verify Telegram login code
    """
    return await verify_code(request=request,
                             phone_number=verification.phone_number,
                             code=verification.code,
                             phone_code_hash=verification.phone_code_hash)


@auth_routes.post('/auth/logout', tags=['Auth'])
async def logout_user(request: Request):
    """
    Log out the user from Telegram and clear the session.
    """
    return await telegram_logout_service(request)


@auth_routes.post('/auth/refresh', tags=['Auth'])
async def refresh_token_endpoint(request: Request):
    """
    Refresh access token using valid refresh token.
    """
    return await refresh_access_token(request)


@auth_routes.post('/auth/jwt-logout', tags=['Auth'])
async def jwt_logout_endpoint(request: Request):
    """
    Logout user and blacklist JWT tokens.
    """
    return await jwt_logout_service(request)
