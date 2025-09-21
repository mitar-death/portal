import redis
import asyncio
import time
from typing import Optional
from server.app.core.config import settings
from server.app.core.logging import logger


redis_host = settings.REDIS_HOST
redis_port = settings.REDIS_PORT
redis_db = settings.REDIS_DB
redis_password = settings.REDIS_PASSWORD

# Global Redis connection instance for reuse
_redis_connection: Optional[redis.Redis] = None
_redis_connection_lock = asyncio.Lock()


class RedisConnectionError(Exception):
    """Custom exception for Redis connection issues"""
    pass


def is_redis_available() -> bool:
    """
    Check if Redis is available without throwing exceptions.
    
    Returns:
        bool: True if Redis is available, False otherwise
    """
    try:
        test_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,
            password=redis_password if redis_password != "None" else None,
            socket_timeout=2,
            socket_connect_timeout=2,
            retry_on_timeout=False
        )
        test_client.ping()
        test_client.close()
        return True
    except Exception as e:
        logger.debug(f"Redis not available: {e}")
        return False


def init_redis_with_retry(decode_responses=False, max_retries=3, base_delay=1.0) -> Optional[redis.Redis]:
    """
    Initialize Redis connection with retry logic and exponential backoff.
    
    Args:
        decode_responses (bool): Whether to decode responses to str. 
                                Must be False for Telethon sessions.
        max_retries (int): Maximum number of connection attempts
        base_delay (float): Base delay in seconds for exponential backoff
    
    Returns:
        Redis: Redis connection instance or None if connection fails
    """
    for attempt in range(max_retries):
        try:
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=decode_responses,
                password=redis_password if redis_password != "None" else None,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError],
                health_check_interval=30
            )
            
            # Test the connection
            client.ping()
            logger.info(f"Redis connection established successfully on attempt {attempt + 1}")
            return client
            
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Redis connection attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Redis connection failed after {max_retries} attempts: {e}")
                return None
    
    return None


def init_redis(decode_responses=False) -> Optional[redis.Redis]:
    """
    Initialize Redis connection with fallback handling.
    
    Args:
        decode_responses (bool): Whether to decode responses to str. 
                                Must be False for Telethon sessions.
    
    Returns:
        Redis: Redis connection instance or None if Redis is unavailable
    """
    global _redis_connection
    
    # Return existing connection if it's healthy
    if _redis_connection is not None:
        try:
            _redis_connection.ping()
            return _redis_connection
        except Exception:
            logger.warning("Existing Redis connection is unhealthy, creating new connection")
            _redis_connection = None
    
    # Create new connection with retry logic
    _redis_connection = init_redis_with_retry(decode_responses=decode_responses)
    return _redis_connection


async def check_redis_health() -> dict:
    """
    Perform a comprehensive Redis health check.
    
    Returns:
        dict: Health check results
    """
    health_info = {
        "status": "unhealthy",
        "available": False,
        "connection_time_ms": None,
        "error": None,
        "info": None
    }
    
    try:
        start_time = time.time()
        
        # Check basic availability
        if not is_redis_available():
            health_info["error"] = "Redis server is not reachable"
            return health_info
        
        # Get detailed connection
        client = init_redis_with_retry(decode_responses=True, max_retries=1)
        if client is None:
            health_info["error"] = "Failed to establish Redis connection"
            return health_info
        
        # Test basic operations
        client.ping()
        connection_time = (time.time() - start_time) * 1000
        
        # Get Redis info
        redis_info = client.info()
        
        health_info.update({
            "status": "healthy",
            "available": True,
            "connection_time_ms": round(connection_time, 2),
            "info": {
                "version": redis_info.get("redis_version"),
                "uptime_seconds": redis_info.get("uptime_in_seconds"),
                "connected_clients": redis_info.get("connected_clients"),
                "used_memory_human": redis_info.get("used_memory_human"),
                "total_commands_processed": redis_info.get("total_commands_processed")
            }
        })
        
        client.close()
        logger.debug("Redis health check completed successfully")
        
    except Exception as e:
        health_info["error"] = str(e)
        logger.warning(f"Redis health check failed: {e}")
    
    return health_info


def safe_redis_operation(operation, *args, **kwargs):
    """
    Safely execute a Redis operation with error handling.
    
    Args:
        operation: Redis operation function
        *args: Operation arguments
        **kwargs: Operation keyword arguments
    
    Returns:
        Result of the operation or None if it fails
    """
    try:
        client = init_redis()
        if client is None:
            logger.debug("Redis not available for operation")
            return None
        
        return operation(client, *args, **kwargs)
    except Exception as e:
        logger.warning(f"Redis operation failed: {e}")
        return None

