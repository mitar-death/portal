from typing import Optional, Set, Dict, List, Union, Tuple
from server.app.core.logging import logger


def normalize_telegram_id(chat_id: Union[int, str]) -> str:
    """
    Normalize Telegram chat IDs to a consistent format.
    Handles various formats including:
    - Regular group IDs (positive integers)
    - Supergroup IDs with -100 prefix
    - Channel IDs with -100 prefix
    - Negative IDs for regular groups

    Args:
        chat_id: The Telegram chat ID in any format (int or string)

    Returns:
        str: Normalized chat ID as a string
    """
    # Convert to string first
    chat_id_str = str(chat_id)

    # Handle supergroup and channel IDs (starting with -100)
    if chat_id_str.startswith("-100"):
        # Store without the -100 prefix for consistency
        return chat_id_str.replace("-100", "")

    # Handle private chats and regular groups
    return chat_id_str


def format_group_id_for_display(chat_id: Union[int, str]) -> str:
    """
    Format a group ID for display in logs or UI.

    Args:
        chat_id: The normalized or raw Telegram chat ID

    Returns:
        str: Formatted ID for display
    """
    chat_id_str = str(chat_id)

    # If it's already a supergroup format with -100, return as is
    if chat_id_str.startswith("-100"):
        return chat_id_str

    # If it's a numeric ID that doesn't start with -, assume it's a supergroup ID without prefix
    if chat_id_str.isdigit():
        return f"-100{chat_id_str}"

    # If it's already a negative number but not a supergroup, return as is
    return chat_id_str


def normalize_group_ids(group_ids: Set[Union[int, str]]) -> Set[str]:
    """
    Normalize a set of group IDs to a consistent format.

    Args:
        group_ids: Set of group IDs in any format

    Returns:
        Set[str]: Set of normalized group IDs
    """
    return {normalize_telegram_id(gid) for gid in group_ids if gid}


def check_match_with_any_format(
    chat_id: Union[int, str], monitored_ids: Set[str]
) -> Tuple[bool, Optional[str]]:
    """
    Check if a chat ID matches any monitored ID, trying different formats.

    Args:
        chat_id: The chat ID to check
        monitored_ids: Set of monitored chat IDs (already normalized)

    Returns:
        Tuple[bool, Optional[str]]: (is_match, matched_id)
    """
    # Normalize the chat ID
    normalized_id = normalize_telegram_id(chat_id)

    # Direct match with normalized ID
    if normalized_id in monitored_ids:
        return True, normalized_id

    # Try raw string match
    raw_id = str(chat_id)
    if raw_id in monitored_ids:
        return True, raw_id

    # Try with -100 prefix for supergroups
    if not raw_id.startswith("-100") and f"-100{normalized_id}" in monitored_ids:
        return True, f"-100{normalized_id}"

    # Try without -100 prefix
    if raw_id.startswith("-100"):
        without_prefix = raw_id.replace("-100", "")
        if without_prefix in monitored_ids:
            return True, without_prefix

    return False, None


def log_group_monitoring_status(
    monitored_ids: Set[str], title: str = "Current Monitored Groups"
):
    """
    Log the current monitored groups with their different ID formats for debugging.

    Args:
        monitored_ids: Set of monitored group IDs
        title: Title for the log entry
    """
    if not monitored_ids:
        logger.info(f"{title}: No groups currently monitored")
        return

    formatted_groups = [
        f"{gid} (display: {format_group_id_for_display(gid)})" for gid in monitored_ids
    ]

    logger.info(f"{title}: {len(monitored_ids)} groups")
    for group in formatted_groups:
        logger.debug(f"  - {group}")
