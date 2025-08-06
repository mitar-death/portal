"""
Database helper functions for the monitoring service.
These functions handle their own database sessions.
"""
from server.app.core.databases import AsyncSessionLocal
from server.app.models.models import Keywords, SelectedGroup
from server.app.core.logging import logger
from sqlalchemy import select
from typing import Set, List


async def get_user_keywords(user_id: int) -> Set[str]:
    """
    Get keywords for a user from the database using a new session.
    """
    if not user_id:
        logger.warning("No user ID provided, cannot load keywords")
        return set()
    
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(Keywords).where(Keywords.user_id == user_id)
            result = await db.execute(stmt)
            user_keywords = result.scalars().first()
            
            if user_keywords and user_keywords.keywords:
                # Convert to lowercase for case-insensitive matching
                return {k.lower() for k in user_keywords.keywords if isinstance(k, str)}
            else:
                logger.info(f"No keywords found for user {user_id}")
                return set()
    except Exception as e:
        logger.error(f"Error loading keywords for user {user_id}: {e}")
        return set()


async def get_user_selected_groups(user_id: int) -> Set[str]:
    """
    Get selected group IDs for a user from the database using a new session.
    """
    if not user_id:
        logger.warning("No user ID provided, cannot load groups")
        return set()
    
    try: 
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SelectedGroup).where(SelectedGroup.user_id == user_id)
            )
            selected_groups = result.scalars().all()
            
            # Store both formats of the group ID to handle Telegram's format
            group_ids = set()
            for group in selected_groups:
                # Original ID
                group_ids.add(str(group.group_id))
                
                # If the ID doesn't already have the -100 prefix, add a version with it
                if not str(group.group_id).startswith('-100'):
                    group_ids.add(f"-100{group.group_id}")
                
            return group_ids
    except Exception as e:
        logger.error(f"Error fetching selected groups for user {user_id}: {e}")
        return set()
