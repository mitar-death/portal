import os
from telethon.sync import TelegramClient
from pathlib import Path
from server.app.core.config import settings
from teleredis import RedisSession
from server.app.services.redis_client import init_redis
from init_db import logger

config_session_dir = settings.TELEGRAM_SESSION_FOLDER_DIR
config_session_name = settings.TELEGRAM_SESSION_NAME

env = settings.ENV
if env == "development":
    logger.info("Using folder session for Telegram client in development environment")
    session_dir = Path(os.path.expanduser(config_session_dir))
    session_dir.mkdir(exist_ok=True)
    session_path = str(session_dir / config_session_name)
    
    client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)

else:
    try:
        logger.info("Using Redis session for Telegram client in production environment")
        redis_connection = init_redis(decode_responses=False)
        redis_session = RedisSession("session_name", redis_connection=redis_connection)
        
        client = TelegramClient(redis_session, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    except Exception as e:
        logger.error(f"Failed to initialize Telegram client with Redis session: {str(e)}")
        logger.info("Falling back to file-based session")
        session_dir = Path(os.path.expanduser(config_session_dir))
        session_dir.mkdir(exist_ok=True)
        
        session_path = str(session_dir / config_session_name)
        client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    

def get_client():
    """
    Get the Telegram client instance.
    
    Returns:
        TelegramClient: The initialized Telegram client.
    """

    return client