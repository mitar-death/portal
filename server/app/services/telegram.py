import os
from telethon.sync import TelegramClient
from pathlib import Path
from server.app.core.config import settings
from teleredis import RedisSession
from server.app.services.redis_client import init_redis

session_folder_dir = settings.TELEGRAM_SESSION_FOLDER_DIR

session_name = settings.TELEGRAM_SESSION_NAME or "user_session"
if not session_folder_dir:
    raise ValueError("TELEGRAM_SESSION_FOLDER_DIR must be set in the configuration.")

session_dir = Path(os.path.expanduser(f"{session_folder_dir}"))
session_dir.mkdir(exist_ok=True)
session_path = str(session_dir / session_name)

env = settings.ENV
if env == "production":
    client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)

else:
    redis_connection = init_redis(decode_responses=False)
    redis_session = RedisSession("session_name", redis_connection=redis_connection)
    client = TelegramClient(redis_session, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)

def get_client():
    """
    Get the Telegram client instance.
    
    Returns:
        TelegramClient: The initialized Telegram client.
    """

    return client