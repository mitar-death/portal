from typing import Dict, Any
from fastapi import Request, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from server.app.core.logging import logger
from server.app.models.models import AIAccount, Group, GroupAIAccount
from server.app.services.monitor import (
    start_monitoring,
    start_health_check_task,
)
from server.app.utils.controller_helpers import (
    ensure_user_authenticated,
    safe_db_operation,
    sanitize_log_data,
    standardize_response,
)


@safe_db_operation()
async def get_group_ai_assignments(
    request: Request, db: AsyncSession = None
) -> Dict[str, Any]:
    """
    Get all AI account assignments for the user's groups.

    Args:
        request: The HTTP request
        db: Database session (injected by decorator)

    Returns:
        Dict with groups and AI accounts data

    Raises:
        HTTPException: For authentication or database errors
    """
    user = await ensure_user_authenticated(request)

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
        assignment_stmt = select(GroupAIAccount).where(
            GroupAIAccount.group_id == group.id
        )
        assignment_result = await db.execute(assignment_stmt)
        assignment = assignment_result.scalars().first()

        # Add to assignments dict
        assignments[str(group.id)] = {
            "group_id": group.id,
            "telegram_id": group.telegram_id,
            "title": group.title,
            "ai_account_id": assignment.ai_account_id if assignment else None,
            "is_active": assignment.is_active if assignment else False,
        }

    # Format AI accounts for the response
    ai_accounts_list = [
        {
            "id": account.id,
            "name": account.name,
            "phone_number": sanitize_log_data(account.phone_number),
            "is_active": account.is_active,
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
            "is_active": assignments[str(group.id)]["is_active"],
            "is_monitored": (
                group.is_monitored if hasattr(group, "is_monitored") else False
            ),
        }
        for group in groups
    ]

    logger.info(
        f"Retrieved {len(groups)} groups and {len(groups_list)} AI accounts for user {user.id}"
    )
    return standardize_response(
        {"groups": groups_list, "ai_accounts": ai_accounts_list},
        "Retrieved group AI assignments successfully",
    )


@safe_db_operation()
async def update_group_ai_assignment(
    request: Request, db: AsyncSession = None
) -> Dict[str, Any]:
    """
    Update the AI account assignment for a group.

    Args:
        request: The HTTP request
        db: Database session (injected by decorator)

    Returns:
        Dict with update status

    Raises:
        HTTPException: For validation, authentication or database errors
    """
    user = await ensure_user_authenticated(request)

    # Parse the request body
    body = await request.json()
    group_id = body.get("group_id")
    ai_account_id = body.get("ai_account_id")
    is_active = body.get("is_active", True)

    # Validate required fields
    if not group_id:
        raise HTTPException(
            status_code=400,
            detail="Missing group_id. Please provide the group_id to update.",
        )

    # Verify ownership of the group
    group_stmt = select(Group).where(Group.id == group_id, Group.user_id == user.id)
    group_result = await db.execute(group_stmt)
    group = group_result.scalars().first()

    if not group:
        raise HTTPException(
            status_code=404,
            detail="The specified group was not found or does not belong to this user.",
        )

    # If ai_account_id is provided, verify ownership of the AI account
    if ai_account_id:
        ai_account_stmt = select(AIAccount).where(
            AIAccount.id == ai_account_id, AIAccount.user_id == user.id
        )
        ai_account_result = await db.execute(ai_account_stmt)
        ai_account = ai_account_result.scalars().first()

        if not ai_account:
            raise HTTPException(
                status_code=404,
                detail="The specified AI account was not found or does not belong to this user.",
            )

    # Check if assignment already exists
    assignment_stmt = select(GroupAIAccount).where(GroupAIAccount.group_id == group_id)
    assignment_result = await db.execute(assignment_stmt)
    existing_assignment = assignment_result.scalars().first()

    result_message = ""

    if existing_assignment:
        if ai_account_id:
            # Update existing assignment
            existing_assignment.ai_account_id = ai_account_id
            existing_assignment.is_active = is_active
            db.add(existing_assignment)
            result_message = (
                f"Group '{group.title}' assigned to AI account successfully"
            )
        else:
            # If no AI account ID provided, delete the assignment
            await db.delete(existing_assignment)
            result_message = f"Removed AI account assignment from group '{group.title}'"
    elif ai_account_id:
        # Create new assignment
        new_assignment = GroupAIAccount(
            group_id=group_id, ai_account_id=ai_account_id, is_active=is_active
        )
        db.add(new_assignment)
        result_message = f"Group '{group.title}' assigned to AI account successfully"
    else:
        # No existing assignment and no AI account ID provided
        result_message = "No changes needed"

    monitoring_started = await start_monitoring()
    if monitoring_started:
        logger.info("Telegram message monitoring started successfully")
    else:
        logger.warning(
            "Failed to start Telegram message monitoring. Login may be required."
        )

    # Start the health check task for real-time diagnostics
    await start_health_check_task()
    logger.info("Health check monitoring task started")

    # Commit changes
    await db.commit()

    return standardize_response({}, result_message)
