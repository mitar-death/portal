import json
import uuid
from typing import  Awaitable, Callable, Any, Optional
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from server.app.core.databases import AsyncSessionLocal, db_context
from server.app.services.monitor import set_active_user_id
from server.app.services.telegram import set_active_user_for_legacy_functions
from server.app.core.logging import logger
from server.app.models.models import User
from server.app.core.config import settings 

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.status import HTTP_404_NOT_FOUND

class DBSessionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to manage the database session lifecycle per request.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        async with AsyncSessionLocal() as session:
            token = db_context.set(session)
            try:
                response = await call_next(request)
            finally:
                db_context.reset(token)
        return response


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle authentication and authorization.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Set default user to unauthenticated
        request.state.user = None
        
        # Skip authentication for OPTIONS requests
        if request.method == "OPTIONS":
            return await call_next(request)
            
        # Check for valid authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            if not token or token.strip() == "":
                logger.info("No token found or empty token")
                return Response(status_code=401, content="Unauthorized")
            
            try:
                # Import JWT utilities
                from server.app.core.jwt_utils import verify_token, JWTManager
                from server.app.core.auth import is_token_blacklisted, update_session_activity
                
                # Verify JWT token
                payload = verify_token(token, "access")
                
                # Extract user information
                user_id = JWTManager.extract_user_id_from_token(payload)
                jti = payload.get("jti")
                
                if not jti:
                    logger.warning("Token missing JTI")
                    return Response(status_code=401, content="Unauthorized")
                
                async with AsyncSessionLocal() as session:
                    # Check if token is blacklisted
                    if await is_token_blacklisted(jti, session):
                        logger.warning("Token is blacklisted")
                        return Response(status_code=401, content="Unauthorized")
                    
                    # Get user from database
                    result = await session.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.scalars().first()
                    
                    if not user:
                        logger.warning(f"User not found: {user_id}")
                        return Response(status_code=401, content="Unauthorized")
                    
                    # Check if user is active
                    if not user.is_active:
                        logger.warning(f"User account is inactive: {user_id}")
                        return Response(status_code=401, content="Unauthorized")
                    
                    logger.info(f"Authenticated user: {user.id}")
                   
                    # Set the authenticated user in the request
                    request.scope["user"] = user
                    request.state.user = user 
                    await set_active_user_id(user.id)
                    
                    # Set active user for Telegram legacy functions
                    await set_active_user_for_legacy_functions(user.id)
                    
                    # Update session activity
                    await update_session_activity(session, jti)
                    
            except Exception as e:
                logger.error(f"Authentication error: {str(e)}")
                return Response(status_code=401, content="Unauthorized")

        # Continue with the request
        return await call_next(request)
    
# Add this new middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging request details for debugging.
    """
    
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        logger.info(f"Request path: {request.url.path}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request headers: {request.headers}")
        
        response = await call_next(request)
        return response
    
class ResponseTransformerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to transform successful JSON responses into a consistent format.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        # List of url to exclude from the response transformation
        excluded_routes = ["openapi.json"]

        # Exclude url, expecially the docs url
        if (
            str(request.url.path).replace(f"{settings.API_PREFIX}/", "")
            in excluded_routes
        ):
            return response

        if (
            200 <= response.status_code < 300
            and "application/json" in response.headers.get("content-type", "")
        ):
            route = request.scope.get("route")
            message: str | None = (
                getattr(route.endpoint, "response_message", None) if route else None
            )

            original_body = b"".join([chunk async for chunk in response.body_iterator])
            try:
                data: Any = json.loads(original_body.decode())
            except json.JSONDecodeError:
                data = original_body.decode()

            wrapped_body = {
                "success": True,
                "status_code": response.status_code,
                "message": message or "Success",
                "data": data,
            }

            return JSONResponse(content=wrapped_body, status_code=response.status_code)

        return response


async def get_current_user(token: str) -> Optional[User]:
    """
    Get the current user from a token string.
    This is used for WebSocket authentication where the token is passed as a query parameter.
    
    Args:
        token: The authentication token
        
    Returns:
        The authenticated user object or None if authentication fails
    """
    if not token or not token.startswith("token_"):
        logger.warning(f"Invalid token format: {token}")
        return None
        
    try:
        user_id = int(token.split("token_")[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalars().first()
            
            if not user:
                logger.warning(f"User not found for token: {token}")
                return None
                
            logger.debug(f"WebSocket authenticated user: {user.id}")
            return user
            
    except ValueError:
        logger.warning(f"Invalid token format (not an integer): {token}")
        return None
    except Exception as e:
        logger.error(f"WebSocket authentication error: {str(e)}")
        return None
