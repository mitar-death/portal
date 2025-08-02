from fastapi import Request, HTTPException
from server.app.core.logging import logger
from server.app.core.databases import db_context
from server.app.models.models import User, AIAccount, Group, GroupAIAccount
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, List, Any

async def get_group_ai_assignments(request: Request):
    """
    Get all AI account assignments for the user's groups.
    """
    try:
        user = request.state.user
        db = db_context.get()
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")

        # Get all groups for this user
        groups_stmt = select(Group).where(Group.user_id == user.id)
        groups_result = await db.execute(groups_stmt)
        groups = groups_result.scalars().all()
        
        # Get all AI accounts for this user
        ai_accounts_stmt = select(AIAccount).where(AIAccount.user_id == user.id)
        ai_accounts_result = await db.execute(ai_accounts_stmt)
        ai_accounts = ai_accounts_result.scalars().all()
        
        # Get all existing assignments
        assignments = {}
        for group in groups:
            # Find assignment for this group
            assignment_stmt = select(GroupAIAccount).where(GroupAIAccount.group_id == group.id)
            assignment_result = await db.execute(assignment_stmt)
            assignment = assignment_result.scalars().first()
            
            # Add to assignments dict
            assignments[str(group.id)] = {
                "group_id": group.id,
                "telegram_id": group.telegram_id,
                "title": group.title,
                "ai_account_id": assignment.ai_account_id if assignment else None,
                "is_active": assignment.is_active if assignment else False
            }
        
        # Format AI accounts for the response
        ai_accounts_list = [
            {
                "id": account.id,
                "name": account.name,
                "phone_number": account.phone_number,
                "is_active": account.is_active
            }
            for account in ai_accounts
        ]
        
        # Format groups with their assignments
        groups_list = [
            {
                "id": group.id,
                "telegram_id": group.telegram_id,
                "title": group.title,
                "ai_account_id": assignments[str(group.id)]["ai_account_id"],
                "is_active": assignments[str(group.id)]["is_active"]
            }
            for group in groups
        ]
        
        return {
            "groups": groups_list,
            "ai_accounts": ai_accounts_list
        }
            
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_group_ai_assignments: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in get_group_ai_assignments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def update_group_ai_assignment(request: Request):
    """
    Update the AI account assignment for a group.
    """
    try:
        user = request.state.user
        db = db_context.get()
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        # Parse the request body
        body = await request.json()
        group_id = body.get("group_id")
        ai_account_id = body.get("ai_account_id")
        is_active = body.get("is_active", True)
        
        # Validate required fields
        if not group_id:
            return {
                "success": False,
                "error": "Missing group_id",
                "details": "Please provide the group_id to update."
            }
        
        
        # Verify ownership of the group
        group_stmt = select(Group).where(Group.id == group_id, Group.user_id == user.id)
        group_result = await db.execute(group_stmt)
        group = group_result.scalars().first()
        
        if not group:
            return {
                "success": False,
                "error": "Group not found",
                "details": "The specified group was not found or does not belong to this user."
            }
        
        # If ai_account_id is provided, verify ownership of the AI account
        if ai_account_id:
            ai_account_stmt = select(AIAccount).where(AIAccount.id == ai_account_id, AIAccount.user_id == user.id)
            ai_account_result = await db.execute(ai_account_stmt)
            ai_account = ai_account_result.scalars().first()
            
            if not ai_account:
                return {
                    "success": False,
                    "error": "AI account not found",
                    "details": "The specified AI account was not found or does not belong to this user."
                }
        
        # Check if assignment already exists
        assignment_stmt = select(GroupAIAccount).where(GroupAIAccount.group_id == group_id)
        assignment_result = await db.execute(assignment_stmt)
        existing_assignment = assignment_result.scalars().first()
        
        if existing_assignment:
            if ai_account_id:
                # Update existing assignment
                existing_assignment.ai_account_id = ai_account_id
                existing_assignment.is_active = is_active
                await db.commit()
                return {
                    "success": True,
                    "message": f"Group '{group.title}' assigned to AI account successfully"
                }
            else:
                # If no AI account ID provided, delete the assignment
                await db.delete(existing_assignment)
                await db.commit()
                return {
                    "success": True,
                    "message": f"Removed AI account assignment from group '{group.title}'"
                }
        elif ai_account_id:
            # Create new assignment
            new_assignment = GroupAIAccount(
                group_id=group_id,
                ai_account_id=ai_account_id,
                is_active=is_active
            )
            db.add(new_assignment)
            await db.commit()
            return {
                "success": True,
                "message": f"Group '{group.title}' assigned to AI account successfully"
            }
        else:
            # No existing assignment and no AI account ID provided
            return {
                "success": True,
                "message": "No changes needed"
            }
                
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_group_ai_assignment: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except Exception as e:
        logger.error(f"Error in update_group_ai_assignment: {e}")
        raise HTTPException(status_code=500, detail=str(e))
