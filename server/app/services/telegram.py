import os
from telethon.sync import TelegramClient
from pathlib import Path
from server.app.core.config import settings


session_dir = Path(os.path.expanduser("./.tgportal_sessions"))
session_dir.mkdir(exist_ok=True)
session_path = str(session_dir / "user_session")

client = TelegramClient(session_path, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)


def get_client():
    """
    Get the Telegram client instance.
    
    Returns:
        TelegramClient: The initialized Telegram client.
    """

    return client