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
    PORT: int = int(os.getenv("PORT", 8000))
    
    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-in-production")
    JWT_REFRESH_SECRET_KEY: str = os.getenv("JWT_REFRESH_SECRET_KEY", "jwt-refresh-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # 30 minutes
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 days
    JWT_ISSUER: str = "tg-portal"
    JWT_AUDIENCE: str = "tg-portal-users"
    
    # Rate Limiting Settings
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = 5  # Max attempts per window
    LOGIN_RATE_LIMIT_WINDOW_MINUTES: int = 15  # Time window in minutes
    LOGIN_RATE_LIMIT_LOCKOUT_MINUTES: int = 30  # Lockout duration in minutes

    # FastAPI server settings
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    HOST: str = os.getenv("HOST", "localhost")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))

    # Database
    table_prefix: str = "tgportal_"
    database_url: str = os.getenv("DATABASE_URL", "")
    DB_TYPE: str = "postgres"
    DB_PORT: int = int(os.getenv("PGPORT", "5432"))
    DB_USERNAME: str = os.getenv("PGUSER", "homestead")
    DB_PASSWORD: str = os.getenv("PGPASSWORD", "password")
    DB_HOST: str = os.getenv("PGHOST", "localhost")
    DB_DATABASE: str = os.getenv("PGDATABASE", "tgportal")
    GOOGLE_STUDIO_API_KEY: str = os.getenv("GOOGLE_STUDIO_API_KEY", "")
    
    #REDIS
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # Telegram
    TELEGRAM_API_ID: str = os.getenv("TELEGRAM_API_ID", "")
    TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
    TELEGRAM_SESSION_FOLDER_DIR: str = os.getenv("TELEGRAM_SESSION_FOLDER_DIR", "storage/sessions")
    TELEGRAM_SESSION_NAME: str = os.getenv("TELEGRAM_SESSION_NAME", "default_session")
    
    # Pusher settings for WebSocket communication
    PUSHER_APP_ID: str = os.getenv("PUSHER_APP_ID", "")
    PUSHER_KEY: str = os.getenv("PUSHER_KEY", "")
    PUSHER_SECRET: str = os.getenv("PUSHER_SECRET", "")
    PUSHER_CLUSTER: str = os.getenv("PUSHER_CLUSTER", "us2")
    
    # Sentry config
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    SENTRY_ENVIRONMENT: str = os.getenv("SENTRY_ENVIRONMENT", "production")
    SENTRY_TRACES_SAMPLE_RATE: str = str(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.2"))
    SENTRY_ENABLE_TRACING: str = str(os.getenv("SENTRY_ENABLE_TRACING", "true"))
    

    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
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