import redis



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
        host='host.docker.internal',
        port=6379,
        db=0,
        decode_responses=decode_responses,
        password=None  # Set your Redis password if required
    )

