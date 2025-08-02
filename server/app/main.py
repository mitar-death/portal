import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from server.app.core.logging import setup_logging, logger
from server.app.core.config import settings
from server.app.routes.base_router import router
from server.app.routes.websocket_routes import ws_router
from server.app.core.middlewares import DBSessionMiddleware, AuthMiddleware, RequestLoggingMiddleware
from server.app.services.telegram import get_client
from server.app.services.monitor import start_monitoring, stop_monitoring, start_health_check_task
from server.app.core.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
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
    client = get_client()
    if not client.is_connected():
        await client.connect()
    
    # Start monitoring in the background - don't pass user_id here
    # User-specific monitoring will be initiated after login
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Include API routers with a prefix
app.include_router(router)
app.include_router(ws_router)

# Middlewares - add in reverse order (last added is executed first)
app.add_middleware(AuthMiddleware)  # Will be executed last
app.add_middleware(RequestLoggingMiddleware)  # Will be executed third
app.add_middleware(DBSessionMiddleware)  # Will be executed second

# Add exception handlers
app.add_exception_handler(HTTPException, app_exception_handler)  
app.add_exception_handler(AppException, app_exception_handler)  
app.add_exception_handler(RequestValidationError, validation_exception_handler) 
app.add_exception_handler(
    Exception, unhandled_exception_handler
) 

def run():
    """Entry point for the Poetry script."""
   
    uvicorn.run("server.app.main:app", host="0.0.0.0", port=8030, reload=True)

if __name__ == "__main__":
    run()
