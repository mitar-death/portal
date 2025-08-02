async def ensure_messenger_ai_initialized():
    """
    Ensure that the messenger_ai is initialized.
    If it's None, try to reinitialize it.
    
    Returns:
        bool: True if messenger_ai is initialized, False otherwise
    """
    global messenger_ai, active_user_id
    
    if messenger_ai is not None:
        return True
        
    # Validate active_user_id
    if active_user_id is None:
        logger.warning("Cannot initialize MessengerAI: No active user ID")
        return False
        
    if not isinstance(active_user_id, int) or active_user_id <= 0:
        logger.error(f"Invalid active_user_id: {active_user_id}. Cannot initialize MessengerAI.")
        return False
    
    logger.warning(f"MessengerAI is None. Attempting to reinitialize for user {active_user_id}...")
    messenger_ai = MessengerAI()
    ai_initialized = await messenger_ai.initialize(active_user_id)
    
    if ai_initialized:
        logger.info(f"Successfully reinitialized MessengerAI for user {active_user_id}")
        return True
    else:
        logger.error(f"Failed to reinitialize MessengerAI for user {active_user_id}")
        messenger_ai = None
        return False
