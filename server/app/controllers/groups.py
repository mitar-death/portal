from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request
from server.app.models.models import SelectedGroup, Group
from server.app.core.logging import logger
from server.app.services.monitor import start_monitoring
from server.app.services.monitor import set_active_user_id


from server.app.utils.controller_helpers import (
    ensure_client_connected,
    ensure_user_authenticated,
    ensure_telegram_authorized,
    safe_db_operation,
)


@safe_db_operation()
async def get_user_groups(
    request: Request, db: AsyncSession = None
) -> List[Dict[str, Any]]:
    """
    Fetch the user's Telegram groups using the current authenticated Telegram session.
    Also saves or updates group information in the database.

    Args:
        request: The HTTP request
        db: Database session (injected by decorator)

    Returns:
        List of group data dictionaries

    Raises:
        HTTPException: For authentication or Telegram API errors
    """
    user = await ensure_user_authenticated(request)

    # User context now explicit via client_manager.get_user_client(user.id)
    logger.info(f"Handling groups request for user {user.id}")

    client = await ensure_client_connected(request)
    if client is None:
        raise HTTPException(
            status_code=500, detail="Failed to connect to Telegram client"
        )
    is_telegram_authorized = await ensure_telegram_authorized(request, client)
    if not is_telegram_authorized:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TELEGRAM_UNAUTHORIZED",
                "message": "Telegram authorization required",
            },
        )

    groups = []

    try:
        # Fetch actual groups from Telegram
        dialogs = await client.get_dialogs()

        for dialog in dialogs:
            entity = dialog.entity

            # Check if it's a group or channel (not a private chat)
            if hasattr(entity, "title"):
                # Save or update group in database
                stmt = select(Group).where(
                    Group.user_id == user.id, Group.telegram_id == entity.id
                )
                result = await db.execute(stmt)
                existing_group = result.scalars().first()

                # Common attributes for both new and existing groups
                group_data = {
                    "id": entity.id,
                    "title": entity.title,
                    "member_count": getattr(entity, "participants_count", 0)
                    or 0,  # Ensure it's never None
                    "description": getattr(entity, "about", None),
                    "username": getattr(entity, "username", None),
                    "is_channel": hasattr(entity, "broadcast") and entity.broadcast,
                }

                if existing_group:
                    # Update existing group with latest info
                    existing_group.title = entity.title
                    existing_group.username = getattr(entity, "username", None)
                    existing_group.description = getattr(entity, "about", None)
                    existing_group.member_count = getattr(
                        entity, "participants_count", 0
                    )
                    existing_group.is_channel = group_data["is_channel"]
                    db.add(existing_group)

                    # Add is_monitored flag from the database, ensuring it's a boolean
                    group_data["is_monitored"] = (
                        bool(existing_group.is_monitored)
                        if existing_group.is_monitored is not None
                        else False
                    )
                    logger.info(
                        f"Updated existing group: {entity.title} (ID: {entity.id})"
                    )
                else:
                    # Create new group
                    new_group = Group(
                        user_id=user.id,
                        telegram_id=entity.id,
                        title=entity.title,
                        username=group_data["username"],
                        description=group_data["description"],
                        member_count=group_data["member_count"],
                        is_channel=group_data["is_channel"],
                        is_monitored=False,
                    )
                    db.add(new_group)

                    # Add is_monitored flag (default False for new groups)
                    group_data["is_monitored"] = False
                    logger.info(f"Added new group: {entity.title} (ID: {entity.id})")

                groups.append(group_data)

        # Commit all group updates at once
        await db.commit()
        logger.info(f"Retrieved {len(groups)} groups for user {user.id}")
        return groups

    except Exception as e:
        logger.error(f"Failed to fetch groups: {e}")
        # If we already have some groups from Telegram, return those even if database operations failed
        if groups:
            # Ensure all groups have proper boolean values for is_monitored
            for group in groups:
                if "is_monitored" not in group or group["is_monitored"] is None:
                    group["is_monitored"] = False
            logger.info(f"Returning {len(groups)} groups despite database error")
            return groups
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch groups: {str(e)}"
        ) from e


@safe_db_operation()
async def monitor_groups(
    request: Request, selected_groups: Dict[str, Any], db: AsyncSession = None
) -> List[Dict[str, Any]]:
    """
    Add selected Telegram groups for monitoring.

    Args:
        request: The HTTP request
        selected_groups: Dictionary containing group IDs to monitor
        db: Database session (injected by decorator)

    Returns:
        List of group data dictionaries

    Raises:
        HTTPException: For authentication or Telegram API errors
    """
    user = await ensure_user_authenticated(request)
    client = await ensure_client_connected(request)
    if client is None:
        raise HTTPException(
            status_code=500, detail="Failed to connect to Telegram client"
        )
    is_telegram_authorized = await ensure_telegram_authorized(request, client)
    if not is_telegram_authorized:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "TELEGRAM_UNAUTHORIZED",
                "message": "Telegram authorization required",
            },
        )

    logger.info(
        f"Adding selected groups for user {user.id} with group IDs: {selected_groups.group_ids}"
    )

    try:
        groups = []
        # Process groups in batches to improve performance
        for group_id in selected_groups.group_ids:
            # Create selectedGroups relationship if it doesn't exist
            selected_group_stmt = select(SelectedGroup).where(
                SelectedGroup.user_id == user.id,
                SelectedGroup.group_id == str(group_id),
            )
            selected_group_result = await db.execute(selected_group_stmt)
            selected_group = selected_group_result.scalars().first()

            if not selected_group:
                selected_group = SelectedGroup(
                    user_id=user.id,
                    group_id=str(
                        group_id
                    ),  # Explicitly convert to string to match model definition
                )
                db.add(selected_group)

            # Get the group from db
            stmt = select(Group).where(
                Group.user_id == user.id, Group.telegram_id == int(group_id)
            )
            group = await db.execute(stmt)
            db_group = group.scalars().first()
            logger.info(f"Selected group {db_group} for user {user.id}")
            if not db_group:
                # If group doesn't exist, create a minimal entry
                db_group = Group(
                    user_id=user.id,
                    telegram_id=int(group_id),
                    title=f"Group {group_id}",
                    member_count=0,
                    description=None,
                    username=None,
                    is_channel=False,
                    is_monitored=True,  # Mark as monitored
                )
                db.add(db_group)
            else:
                db_group.is_monitored = True
                db.add(db_group)

            try:
                entity = await client.get_entity(int(group_id))
                group_data = {
                    "id": entity.id,
                    "title": entity.title,
                    "member_count": getattr(entity, "participants_count", 0)
                    or 0,  # Ensure it's never None
                    "description": getattr(entity, "about", None),
                    "username": getattr(entity, "username", None),
                    "is_channel": hasattr(entity, "broadcast") and entity.broadcast,
                }
                logger.info(
                    f"Adding group {group_data['title']} ({group_data['id']}) for monitoring"
                )
                groups.append(group_data)
            except Exception as e:
                # If we can't get the entity, add minimal data that satisfies the schema
                logger.warning(f"Could not get entity for group {group_id}: {e}")
                groups.append(
                    {
                        "id": (
                            int(group_id)
                            if isinstance(group_id, str) and group_id.isdigit()
                            else 0
                        ),
                        "title": f"Group {group_id}",
                        "member_count": 0,  # Ensure this is always an integer, never None
                        "description": None,
                        "username": None,
                        "is_channel": False,
                    }
                )

        # Commit all changes at once for better performance
        await db.commit()
        logger.info(f"Added {len(groups)} groups for monitoring for user {user.id}")

        # Restart monitoring with updated group selections (uncomment if needed)
        await set_active_user_id(user.id)
        await start_monitoring(user.id)

        return groups

    except Exception as e:
        logger.error(f"Failed to add selected groups: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to add selected groups: {str(e)}"
        ) from e
