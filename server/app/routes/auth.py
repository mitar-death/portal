
from fastapi import APIRouter, Request


from server.app.schemas.schemas import (
    CodeVerification, 
    AuthResponse, 
)
from server.app.controllers.main import (
    verify_code,
    logout_telegram as telegram_logout_service 
)
from server.app.controllers.auth import check_auth_status

auth_routes = APIRouter() 
 


@auth_routes.get('/auth/status', tags=['Auth'])
async def check_auth_status_endpoint(request: Request):
    """
    Check the current Telegram authentication status.
    """
    return await check_auth_status(request)


@auth_routes.post('/auth/verify-code', tags=['Auth'], response_model=AuthResponse)
async def verify_login_code(verification: CodeVerification):
    """
    Verify Telegram login code
    """
    return await verify_code(verification.phone_number, verification.code, verification.phone_code_hash)




@auth_routes.post('/auth/logout', tags=['Auth'])
async def logout_user(request: Request):
    """
    Log out the user from Telegram and clear the session.
    """
    return await telegram_logout_service(request)