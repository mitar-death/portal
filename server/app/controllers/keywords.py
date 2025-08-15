
from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request
from server.app.models.models import  Keywords

from server.app.core.logging import logger
from server.app.services.monitor import  start_monitoring, start_health_check_task

from server.app.utils.controller_helpers import (
    ensure_user_authenticated,
    safe_db_operation,
    standardize_response
)

@safe_db_operation()
async def get_keywords_controller(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Get the list of keywords for message filtering.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with keywords data
        
    Raises:
        HTTPException: For database or authentication errors
    """
    user = await ensure_user_authenticated(request)

    try:
        # Execute a proper SQLAlchemy query using the ORM
        stmt = select(Keywords).where(Keywords.user_id == user.id)
        result = await db.execute(stmt)
        user_keywords = result.scalars().first()
        
        # Get the keywords list or empty list if no record exists
        keywords_list = user_keywords.keywords if user_keywords else []
        
        
         # Ensure monitoring is started if not already
        return standardize_response(
            {
                "keywords": keywords_list,
                "count": len(keywords_list)
            },
            "Keywords fetched successfully"
        )
    except Exception as e:
        logger.error(f"Failed to fetch keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch keywords: {str(e)}")

@safe_db_operation()
async def add_keywords_controller(request: Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Adds new keywords for message filtering.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with updated keywords data
        
    Raises:
        HTTPException: For validation or database errors
    """
    user = await ensure_user_authenticated(request)

    try:
        # Get request body
        body = await request.json()
        
        # Extract keywords from request body
        keywords = body.get("keywords", [])
        logger.info(f"Received keywords: {keywords}")
        
        if not isinstance(keywords, list):
            # Handle case where a single keyword is sent
            if isinstance(keywords, str):
                keywords = [keywords]
            else:
                raise HTTPException(status_code=400, detail="Keywords must be a list of strings")
        
        # Check if user already has a keywords entry
        stmt = select(Keywords).where(Keywords.user_id == user.id)
        result = await db.execute(stmt)
        user_keywords = result.scalars().first()
        
        if not user_keywords:
            # Create new keywords entry if none exists
            user_keywords = Keywords(user_id=user.id, keywords=[])
            db.add(user_keywords)
            await db.flush() 
            
        # Add each keyword using the model's add_keyword method
        added_count = 0
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.strip():
                if user_keywords.add_keyword(keyword):
                    added_count += 1
                    logger.info(f"Added keyword: {keyword}")
        
        if added_count > 0:
            await db.commit()
        
        # Refresh the keywords from the database to ensure we're returning the latest data
        await db.refresh(user_keywords)
        
        # Only restart monitoring if keywords were actually added
        if added_count > 0:
            monitoring_started = await start_monitoring()
            if monitoring_started:
                logger.info("Telegram message monitoring started successfully")
            else:
                logger.warning("Failed to start Telegram message monitoring. Login may be required.")
            
            # Start the health check task for real-time diagnostics
            await start_health_check_task()
            logger.info("Health check monitoring task started")
    
        return standardize_response(
            {
                "keywords": user_keywords.keywords,
                "added_count": added_count
            },
            f"{added_count} keywords added successfully"
        )
    except ValueError as e:
        # Handle JSON parsing errors
        logger.error(f"Invalid request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")
    except Exception as e:
        logger.error(f"Failed to add keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add keywords: {str(e)}")


@safe_db_operation()
async def delete_keywords_controller(request:Request, db: AsyncSession = None) -> Dict[str, Any]:
    """
    Deletes specified keywords for message filtering.
    
    Args:
        request: The HTTP request
        db: Database session (injected by decorator)
        
    Returns:
        Dict with updated keywords data
        
    Raises:
        HTTPException: For validation or database errors
    """
    user = await ensure_user_authenticated(request)

    try:
        # Get request body
        body = await request.json()
        
        # Extract keywords from request body
        keywords = body.get("keywords", [])
        logger.info(f"Received keywords to delete: {keywords}")
        
        if not isinstance(keywords, list):
            # Handle case where a single keyword is sent
            if isinstance(keywords, str):
                keywords = [keywords]
                keywords = [keywords]
            else:
                raise HTTPException(status_code=400, detail="Keywords must be a list of strings")
        
        # Check if user already has a keywords entry
        stmt = select(Keywords).where(Keywords.user_id == user.id)
        result = await db.execute(stmt)
        user_keywords = result.scalars().first()
        
        if not user_keywords:
            raise HTTPException(status_code=404, detail="No keywords found for user")
        
        # Remove each keyword using the model's remove_keyword method
        removed_count = 0
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.strip():
                if user_keywords.remove_keyword(keyword):
                    removed_count += 1
                    logger.info(f"Removed keyword: {keyword}")
        
        if removed_count > 0:
            await db.commit()
        
        # Refresh the keywords from the database to ensure we're returning the latest data
        await db.refresh(user_keywords)
        
        return standardize_response(
            {
                "keywords": user_keywords.keywords,
                "removed_count": removed_count
            },
            f"{removed_count} keywords removed successfully"
        )
    except ValueError as e:
        # Handle JSON parsing errors
        logger.error(f"Invalid request body: {e}")
        raise HTTPException(status_code=400, detail="Invalid request body")
    except Exception as e:
        logger.error(f"Failed to delete keywords: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete keywords: {str(e)}")