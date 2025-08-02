"""
Database helper functions for group mappings.
"""
from server.app.core.databases import AsyncSessionLocal
from server.app.core.logging import logger
from server.app.models.models import GroupAIAccount, Group
from sqlalchemy import select, and_

async def get_group_ai_mappings(user_id: int):
    """
    Get all group-AI account mappings for a user.
    Returns a dictionary mapping group IDs to AI account IDs.
    """
    mappings = {}
    
    try:
        async with AsyncSessionLocal() as session:
            # Query all group-AI account mappings for this user's groups
            mapping_stmt = select(GroupAIAccount, Group).join(
                Group, GroupAIAccount.group_id == Group.id
            ).where(
                and_(
                    Group.user_id == user_id,
                    GroupAIAccount.is_active == True
                )
            )
            mapping_result = await session.execute(mapping_stmt)
            
            # Build the mapping dictionary: {telegram_group_id: ai_account_id}
            for mapping, group in mapping_result:
                # Store both versions of the group ID for compatibility
                str_telegram_id = str(group.telegram_id)
                mappings[str_telegram_id] = {
                    'ai_account_id': mapping.ai_account_id,
                    'group_name': group.title or group.name or f"Group {str_telegram_id}"
                }
                
                # Also add the version without the "-100" prefix
                if str_telegram_id.startswith('-100'):
                    short_id = str_telegram_id.replace('-100', '')
                    mappings[short_id] = {
                        'ai_account_id': mapping.ai_account_id,
                        'group_name': group.title or group.name or f"Group {str_telegram_id}"
                    }
                # Also add the version with the "-100" prefix
                elif not str_telegram_id.startswith('-100'):
                    prefixed_id = f"-100{str_telegram_id}"
                    mappings[prefixed_id] = {
                        'ai_account_id': mapping.ai_account_id,
                        'group_name': group.title or group.name or f"Group {str_telegram_id}"
                    }
            
            return mappings
    except Exception as e:
        logger.error(f"Error fetching group-AI mappings: {e}")
        return {}
