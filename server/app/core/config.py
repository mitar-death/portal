"""Configuration module for application settings using Pydantic."""

from functools import lru_cache
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    APP_NAME: str = "TG Portal"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    API_PREFIX: str = os.getenv("API_PREFIX", "/api")
    ENV: str = os.getenv("ENV", "development")
    PORT: int = int(os.getenv("PORT", 8030))

    # FastAPI server settings
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "127.0.0.1")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8030"))

    # Database
    table_prefix: str = "tgportal_"
    database_url: str = ""
    DB_TYPE: str = "postgres"
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))
    DB_USERNAME: str = os.getenv("DB_USERNAME", "homestead")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD" , "password")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_DATABASE: str = os.getenv("DB_DATABASE", "tgportal")
    GOOGLE_STUDIO_API_KEY: str = os.getenv("GOOGLE_STUDIO_API_KEY", "")
    
    #REDIS
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", None)
    # Telegram
    TELEGRAM_API_ID: str = os.getenv("TELEGRAM_API_ID", "")
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_SESSION_FOLDER_DIR: str = os.getenv("TELEGRAM_SESSION_FOLDER_DIR", "storage/sessions")
    TELEGRAM_SESSION_NAME: str = os.getenv("TELEGRAM_SESSION_NAME", "default_session")

    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://127.0.0.1:8030")
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    FIREBASE_PROJECT_NUMBER: str = os.getenv("FIREBASE_PROJECT_NUMBER", "")
    
    
  
    def get_database_url(self) -> str:
        """
        Constructs and returns a database URL if individual components are provided,
        otherwise returns the database_url directly.
        """
        if self.database_url:
            return self.database_url
            
        return f"postgresql://{self.DB_USERNAME}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Retrieve the application settings.

    Caches the settings object for improved performance.

    Returns:
        Settings: A Settings object populated with values from the environment.
    """
    return Settings()

settings = get_settings()