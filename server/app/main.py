import uvicorn
import asyncio
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
from server.app.core.sentry import init_sentry


# Set up logging
setup_logging()

init_sentry()
# Background tasks set
background_tasks = set()

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    This handles startup and shutdown events with non-blocking operations.
    """
    # Create a task set to track background operations
    startup_complete = asyncio.Event()
    
    # Startup: Initialize core components without blocking
    async def initialize_app():
        try:
            # Initialize client with timeout protection
            try:
                client = await asyncio.wait_for(get_client(), timeout=5)
                if not client.is_connected():
                    await asyncio.wait_for(client.connect(), timeout=5)
                logger.info("Telegram client initialized")
            except asyncio.TimeoutError:
                logger.warning("Telegram client initialization timed out, will retry in background")
                client = None
            except Exception as e:
                logger.error(f"Error initializing Telegram client: {e}")
                client = None
            
            # Check authorization status if client is available
            if client and client.is_connected():
                try:
                    is_authorized = await asyncio.wait_for(client.is_user_authorized(), timeout=5)
                    if is_authorized:
                        try:
                            me = await asyncio.wait_for(client.get_me(), timeout=5)
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
                        except asyncio.TimeoutError:
                            logger.warning("Getting user info timed out")
                        except Exception as e:
                            logger.error(f"Error getting authorized user info: {e}")
                except asyncio.TimeoutError:
                    logger.warning("Authorization check timed out")
                except Exception as e:
                    logger.error(f"Error checking authorization: {e}")
            
            # Start monitoring in background without blocking app startup
            try:
                monitoring_task = asyncio.create_task(start_monitoring())
                background_tasks.add(monitoring_task)
                monitoring_task.add_done_callback(lambda t: background_tasks.discard(t))
                
                # Don't wait for this to complete
                monitoring_task.add_done_callback(
                    lambda t: logger.info("Monitoring started successfully") if not t.exception() else 
                    logger.error(f"Error starting monitoring: {t.exception()}")
                )
            except Exception as e:
                logger.error(f"Error initiating monitoring: {e}")
            
            # Start health check in background
            try:
                health_check_task = asyncio.create_task(start_health_check_task())
                background_tasks.add(health_check_task)
                health_check_task.add_done_callback(lambda t: background_tasks.discard(t))
                
                # Don't wait for this to complete
                health_check_task.add_done_callback(
                    lambda t: logger.info("Health check task started") if not t.exception() else 
                    logger.error(f"Error starting health check: {t.exception()}")
                )
            except Exception as e:
                logger.error(f"Error initiating health check: {e}")
            
            # Signal that startup is complete so the app can start accepting requests
            startup_complete.set()
            
        except Exception as e:
            logger.error(f"Unhandled error during app initialization: {e}")
            # Still set the event to allow the app to start
            startup_complete.set()
    
    # Start initialization in background
    init_task = asyncio.create_task(initialize_app())
    background_tasks.add(init_task)
    init_task.add_done_callback(lambda t: background_tasks.discard(t))
    
    # Wait for critical startup tasks with a timeout
    try:
        # Wait for a maximum of 2 seconds for initialization
        # This allows the app to start even if some initialization is still ongoing
        await asyncio.wait_for(startup_complete.wait(), timeout=2)
    except asyncio.TimeoutError:
        logger.warning("App initialization taking longer than expected, starting anyway")
    
    # App is now ready to accept requests
    logger.info("FastAPI application startup complete")
    
    yield
    
    # Shutdown: Clean up background tasks
    logger.info("Application shutting down, cleaning up resources...")
    
    # Stop monitoring without blocking shutdown
    try:
        await asyncio.wait_for(stop_monitoring(), timeout=5)
        logger.info("Monitoring stopped successfully")
    except asyncio.TimeoutError:
        logger.warning("Stopping monitoring timed out")
    except Exception as e:
        logger.error(f"Error stopping monitoring: {e}")
    
    # Cancel any remaining background tasks
    remaining_tasks = [t for t in background_tasks if not t.done()]
    if remaining_tasks:
        logger.info(f"Cancelling {len(remaining_tasks)} remaining background tasks")
        for task in remaining_tasks:
            task.cancel()
        
        # Wait for tasks to be cancelled with timeout
        try:
            await asyncio.wait_for(asyncio.gather(*remaining_tasks, return_exceptions=True), timeout=5)
        except asyncio.TimeoutError:
            logger.warning("Some background tasks didn't terminate in time")
    
    # Get telegram client to disconnect it
    try:
        client = await asyncio.wait_for(get_client(), timeout=2)
        if client and client.is_connected():
            await asyncio.wait_for(client.disconnect(), timeout=3)
            logger.info("Telegram client disconnected")
    except (asyncio.TimeoutError, Exception) as e:
        logger.error(f"Error disconnecting Telegram client: {e}")
    
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
        "http://localhost:5000", 
        "http://127.0.0.1:5000",
        "https://bbd506a1-322a-4a63-b208-7792a6078304-00-ualde7y289ys.worf.replit.dev",
        "https://gen-lang-client-0560055117.web.app",
        "*"  # Allow all origins for development
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
    
    logger.info("Running in development mode with reload enabled")
    uvicorn.run("server.app.main:app", host=settings.HOST, port=settings.SERVER_PORT, reload=True)

if __name__ == "__main__":
    run()
