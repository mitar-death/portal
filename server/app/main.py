import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from server.app.services.monitor import set_active_user_id
from server.app.core.logging import setup_logging, logger
from server.app.core.config import settings
from server.app.routes.base_router import router
from server.app.routes.websocket_routes import ws_router
from server.app.routes.pusher_routes import pusher_router
from server.app.core.middlewares import DBSessionMiddleware, AuthMiddleware, RequestLoggingMiddleware
from server.app.services.telegram import get_client
from server.app.services.monitor import start_monitoring, stop_monitoring, start_health_check_task
from server.app.core.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from server.app.core.databases import AsyncSessionLocal
from server.app.models.models import User
from sqlalchemy import select
# Set up logging
setup_logging()

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    This handles startup and shutdown events.
    """
    # Startup: Initialize Telegram client and start monitoring
    client = await get_client()
    if not client.is_connected():
        await client.connect()
    
    # Validate all API credentials in the database
    logger.info("Validating API credentials...")

    
    # Check if a user is already authorized
    is_authorized = await client.is_user_authorized()
    if is_authorized:
        # Try to get the user info
        try:
            me = await client.get_me()
            if me:
                logger.info(f"Found authorized Telegram user: {me.first_name} {me.last_name} (@{me.username})")
                
                # Find the user in the database
                
                
                async with AsyncSessionLocal() as session:
                    stmt = select(User).where(User.telegram_id == str(me.id))
                    result = await session.execute(stmt)
                    user = result.scalars().first()
                    
                    if user:
                        # Set this user as the active user for monitoring
                        await set_active_user_id(user.id)
                        logger.info(f"Set active user ID to {user.id} during application startup")
                    else:
                        logger.warning(f"Found authorized Telegram user but no matching user in database: {me.id}")
        except Exception as e:
            logger.error(f"Error getting authorized user info during startup: {e}")
    
    # Start monitoring in the background but without a specific user ID
    # The user ID will be set when a user logs in via the AuthMiddleware
    monitoring_started = await start_monitoring()
    if monitoring_started:
        logger.info("Telegram message monitoring started successfully")
    else:
        logger.warning("Failed to start Telegram message monitoring. Login may be required.")
    
    # Start the health check task for real-time diagnostics
    await start_health_check_task()
    logger.info("Health check monitoring task started")
    
    yield
    
    # Shutdown: Stop monitoring and disconnect client
    await stop_monitoring()
    logger.info("Application shutdown complete")

# Initialize the FastAPI app
app = FastAPI(
    title="TGPortal API",
    description="API for TGPortal",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path=settings.API_PREFIX,
    openapi_url="/openapi.json",
    lifespan=lifespan,  # Add the lifespan context manager
)

# Set up CORS - allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "localhost", 
        "http://localhost:8080", 
        "http://127.0.0.1:8080",
        "https://gen-lang-client-0560055117.web.app" 
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  
)


# Middlewares - add in reverse order (last added is executed first)
app.add_middleware(AuthMiddleware)  # Will be executed last
app.add_middleware(RequestLoggingMiddleware)  # Will be executed third
app.add_middleware(DBSessionMiddleware)  # Will be executed second

# Include API routers with a prefix
app.include_router(router)
app.include_router(ws_router)
app.include_router(pusher_router)

# Add exception handlers
app.add_exception_handler(HTTPException, app_exception_handler)  
app.add_exception_handler(AppException, app_exception_handler)  
app.add_exception_handler(RequestValidationError, validation_exception_handler) 
app.add_exception_handler(
    Exception, unhandled_exception_handler
) 

def run():
    """Entry point for the Poetry script."""
    if settings.ENV == "development":
        logger.info("Running in development mode with reload enabled")
        uvicorn.run("server.app.main:app", host=settings.HOST, port=settings.SERVER_PORT, reload=True)
    else:
        logger.info("Running in production mode")
        uvicorn.run("server.app.main:app", host=settings.HOST, port=settings.SERVER_PORT, workers=4)

if __name__ == "__main__":
    run()
