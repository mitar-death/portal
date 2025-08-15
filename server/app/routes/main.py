from fastapi import APIRouter, Request
from typing import Dict, Any
from server.app.controllers.ai import (
    test_ai_controller
    )
from server.app.controllers.main import (
    request_code,
)

main_routes = APIRouter()

@main_routes.get("/sentry-debug")
async def trigger_error():
    division_by_zero = 1 / 0

@main_routes.get('/', tags=['Base'])
async def index():
    """Root endpoint"""
    return {"message": "Welcome to the TGPortal API"}

@main_routes.post('/ai', tags=['Base'])
async def ai_test(request:Request):
    """Test ai endpoint"""
    return await test_ai_controller(request)


@main_routes.post('/auth/request-code', response_model=Dict[str, Any])
async def request_login_code(
    request: Request,
    ):
    """
    Request Telegram verification code for login
    """
    return await request_code(request)

