"""
Script to set up group-AI mappings for a user.
Run this script to create mappings for all groups to the default AI account.
"""
import asyncio
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.app.core.databases import AsyncSessionLocal
from server.app.core.logging import logger
from server.app.models.models import Group, AIAccount, GroupAIAccount
from sqlalchemy import select, and_
from server.app.services.test_messenger import test_messenger_ai_config

async def setup_default_mappings(user_id):
    """
    Set up default mappings for all groups to the first active AI account.
    """
    try:
        logger.info(f"Setting up default group-AI mappings for user {user_id}")
        
        async with AsyncSessionLocal() as session:
            # Get all groups for the user
            groups_stmt = select(Group).where(Group.user_id == user_id)
            groups_result = await session.execute(groups_stmt)
            groups = groups_result.scalars().all()
            
            if not groups:
                logger.warning(f"No groups found for user {user_id}")
                return False
                
            # Get the first active AI account
            ai_account_stmt = select(AIAccount).where(
                and_(
                    AIAccount.user_id == user_id,
                    AIAccount.is_active == True
                )
            )
            ai_account_result = await session.execute(ai_account_stmt)
            ai_account = ai_account_result.scalars().first()
            
            if not ai_account:
                logger.warning(f"No active AI accounts found for user {user_id}")
                return False
                
            # Create mappings for all groups
            mappings_created = 0
            for group in groups:
                # Check if mapping already exists
                existing_mapping_stmt = select(GroupAIAccount).where(
                    and_(
                        GroupAIAccount.group_id == group.id,
                        GroupAIAccount.ai_account_id == ai_account.id
                    )
                )
                existing_mapping_result = await session.execute(existing_mapping_stmt)
                existing_mapping = existing_mapping_result.scalars().first()
                
                if existing_mapping:
                    logger.info(f"Mapping already exists for group {group.title or group.name} (ID: {group.id})")
                    # Make sure it's active
                    if not existing_mapping.is_active:
                        existing_mapping.is_active = True
                        session.add(existing_mapping)
                        logger.info(f"Activated existing mapping for group {group.title or group.name}")
                else:
                    # Create new mapping
                    new_mapping = GroupAIAccount(
                        group_id=group.id,
                        ai_account_id=ai_account.id,
                        is_active=True
                    )
                    session.add(new_mapping)
                    mappings_created += 1
                    logger.info(f"Created new mapping for group {group.title or group.name} (ID: {group.id}) -> AI account {ai_account.id}")
            
            if mappings_created > 0 or any(m.is_active for m in session.query(GroupAIAccount).all()):
                await session.commit()
                logger.info(f"Created {mappings_created} new group-AI mappings")
                return True
            else:
                logger.warning("No new mappings created and no existing active mappings found")
                return False
                
    except Exception as e:
        logger.error(f"Error setting up default group-AI mappings: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
        
async def main():
    """
    Main function.
    """
    if len(sys.argv) < 2:
        print("Usage: python setup_mappings.py <user_id>")
        return
        
    user_id = int(sys.argv[1])
    
    # Set up default mappings
    result = await setup_default_mappings(user_id)
    
    if result:
        print(f"Successfully set up default group-AI mappings for user {user_id}")
        
        # Test the messenger AI configuration
        test_result = await test_messenger_ai_config(user_id)
        
        if test_result:
            print("MessengerAI configuration test passed")
        else:
            print("MessengerAI configuration test failed")
    else:
        print(f"Failed to set up default group-AI mappings for user {user_id}")
        
if __name__ == "__main__":
    asyncio.run(main())
