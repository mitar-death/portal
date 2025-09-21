from contextvars import ContextVar
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from sqlalchemy.orm import sessionmaker
from server.app.core.config import settings
from server.app.core.logging import logger


def create_async_database_engine() -> AsyncEngine:
    """
    Create and return an asynchronous SQLAlchemy engine based on configuration.

    Returns:
        AsyncEngine: Configured async SQLAlchemy engine.

    Raises:
        ValueError: If an unsupported database type is specified in settings.
    """
    if settings.DB_TYPE not in ["postgres", "mysql"]:
        raise ValueError(
            f"Unsupported database type specified in settings: {settings.DB_TYPE}"
        )

    database_url = settings.get_database_url()
    # Log URL with masked password for security
    masked_url = database_url.split('@')[0].split(':')[:-1] + ['***'] + ['@' + database_url.split('@')[1]] if '@' in database_url else [database_url]
    logger.info(f"Creating async database engine with URL: {''.join(masked_url)}")

    # Replace with async-compatible dialect and handle SSL parameters
    if settings.DB_TYPE == "postgres":
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Handle SSL mode parameter for asyncpg - convert to connection arguments
        ssl_args = {}
        if "sslmode=require" in database_url:
            database_url = database_url.replace("?sslmode=require", "").replace("&sslmode=require", "")
            ssl_args["ssl"] = "require"
        elif "sslmode=" in database_url:
            # Remove any sslmode parameter as asyncpg handles SSL differently
            import re
            database_url = re.sub(r'[?&]sslmode=[^&]*', '', database_url)
            
        # Log driver info without exposing credentials
        logger.info(f"Using asyncpg for PostgreSQL connection")
        
        # For asyncpg, we handle SSL through connection arguments if needed
        engine_kwargs = {"pool_pre_ping": True, "echo": False}
        if ssl_args:
            engine_kwargs["connect_args"] = ssl_args
            
        return create_async_engine(database_url, **engine_kwargs)
        
    elif settings.DB_TYPE == "mysql":
        database_url = database_url.replace("mysql://", "mysql+aiomysql://", 1)
        return create_async_engine(database_url, pool_pre_ping=True, echo=False)
        
    return create_async_engine(database_url, pool_pre_ping=True, echo=False)


# Create the async engine and sessionmaker
async_engine: AsyncEngine = create_async_database_engine()

AsyncSessionLocal: sessionmaker = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

db_context: ContextVar[AsyncSession] = ContextVar("db_session")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a new async database session.

    Yields:
        AsyncGenerator[AsyncSession, None]: A SQLAlchemy async session.
    """
    async with AsyncSessionLocal() as session:
        token = db_context.set(session)
        try:
            yield session
        finally:
            db_context.reset(token)
