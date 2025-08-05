import redis
from server.app.core.config import settings 


redis_host = settings.REDIS_HOST
redis_port = settings.REDIS_PORT
redis_db = settings.REDIS_DB
redis_password = settings.REDIS_PASSWORD

def init_redis(decode_responses=False):
    """
    Initialize Redis connection
    
    Args:
        decode_responses (bool): Whether to decode responses to str. 
                                Must be False for Telethon sessions.
    
    Returns:
        Redis: Redis connection instance
    """
    return redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=decode_responses,
        password=redis_password if redis_password != "None" else None
    )

