#!/usr/bin/env python
import os
import sys
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("db_init")

# Load environment variables
load_dotenv()

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    from sqlalchemy import create_engine, text
except ImportError:
    logger.error("Required packages are missing. Please run: pip install psycopg2-binary sqlalchemy")
    sys.exit(1)

def create_database():
    """Create the PostgreSQL database if it doesn't exist."""
    db_name = os.getenv("DB_DATABASE", "tgportal")
    db_user = os.getenv("DB_USERNAME", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    
    try:
        # Connect to PostgreSQL server
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=db_user,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
        exists = cursor.fetchone()
        
        if not exists:
            logger.info(f"Creating database '{db_name}'...")
            cursor.execute(f"CREATE DATABASE {db_name}")
            logger.info(f"Database '{db_name}' created successfully.")
        else:
            logger.info(f"Database '{db_name}' already exists.")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating database: {str(e)}")
        return False

def create_tables():
    """Create database tables using SQLAlchemy models."""
    import sys
    sys.path.append('/Users/mazibuckler/apps/tgportal')
    from server.app.core.databases import engine
    from server.app.models.models import ActiveSession
    from server.app.models.models import User
    from server.app.core.databases import Base
    
    try:
        logger.info("Creating database tables...")
        
        # Create tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database tables created successfully.")
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

def run_migrations():
    """Run Alembic migrations."""
    try:
        logger.info("Running database migrations...")
        os.system("cd /Users/mazibuckler/apps/tgportal && alembic revision --autogenerate -m 'Initial migration'")
        os.system("cd /Users/mazibuckler/apps/tgportal && alembic upgrade head")
        logger.info("Migrations completed successfully.")
        return True
    except Exception as e:
        logger.error(f"Error running migrations: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting database initialization...")
    
    if create_database():
        if create_tables():
            run_migrations()
    
    logger.info("Database initialization completed.")
