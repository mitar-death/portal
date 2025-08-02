from fastapi import HTTPException, Request
from server.app.core.logging import logger
from server.app.services.telegram import get_client


async def check_auth_status(request: Request):
    """
    Check the current Telegram authentication status.
    Returns whether the user is authenticated and if the client is connected.
    """
    try:
        # Get the Telegram client
        client = get_client()
        
        # Check if the client is connected
        is_connected = client.is_connected()
        if not is_connected:
            # Try to connect if not already connected
            await client.connect()
            is_connected = client.is_connected()
        
        # Check if the user is authorized
        is_authorized = await client.is_user_authorized()
        
        # Get user info if authorized
        user_info = None
        if is_authorized:
            me = await client.get_me()
            if me:
                user_info = {
                    "id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "phone": me.phone
                }
        
        # Return the status
        return {
            "is_connected": is_connected,
            "is_authorized": is_authorized,
            "user_info": user_info
        }
    except Exception as e:
        logger.error(f"Error checking authentication status: {e}")
        raise HTTPException(status_code=500, detail=f"Error checking authentication status: {str(e)}")
