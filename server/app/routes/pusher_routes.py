"""
Pusher authentication routes for WebSocket communication.
"""

import json
import pusher
from fastapi import APIRouter, Depends, Request, HTTPException
from server.app.core.config import settings
from server.app.core.middlewares import get_current_user
from server.app.models.models import User

pusher_router = APIRouter(prefix="/pusher", tags=["pusher"])

# Initialize Pusher client only if credentials are provided
pusher_client = None
if settings.PUSHER_APP_ID and settings.PUSHER_KEY and settings.PUSHER_SECRET:
    try:
        pusher_client = pusher.Pusher(
            app_id=settings.PUSHER_APP_ID,
            key=settings.PUSHER_KEY,
            secret=settings.PUSHER_SECRET,
            cluster=settings.PUSHER_CLUSTER,
            ssl=True,
        )
    except Exception as e:
        print(f"Failed to initialize Pusher client: {e}")
        pusher_client = None


@pusher_router.post("/auth")
async def pusher_auth(request: Request, user: User = Depends(get_current_user)):
    """Authenticate Pusher private channels"""

    # For public channels, we don't actually need auth
    # This route is kept for backward compatibility and potential future use

    try:
        # Get the socket_id and channel_name from the request body
        data = await request.json()
        socket_id = data.get("socket_id")
        channel_name = data.get("channel_name")

        print(f"Pusher auth data: socket_id={socket_id}, channel_name={channel_name}")

        if not socket_id or not channel_name:
            raise HTTPException(
                status_code=400, detail="Missing socket_id or channel_name"
            )

        # Check if this is a public channel
        if not channel_name.startswith("private-"):
            # For public channels, return a success message
            return {
                "status": "success",
                "message": "No authentication needed for public channels",
            }
    except json.JSONDecodeError as e:
        # Handle JSON decoding errors (empty or malformed body)
        print(f"JSON decode error: {str(e)}")

        # Try to get the raw body for debugging
        try:
            raw_body = await request.body()
            print(f"Raw request body: {raw_body}")
        except Exception as body_err:
            print(f"Error reading raw body: {str(body_err)}")

        raise HTTPException(
            status_code=400, detail=f"Invalid JSON format: {str(e)}"
        ) from e

    # For private channels, authenticate the socket connection
    try:
        # Check if the channel is for this user
        if channel_name.startswith("private-"):
            # Check if pusher_client is initialized before using it
            if pusher_client is None:
                print(
                    "Pusher client is not initialized - cannot authenticate private channels"
                )
                raise HTTPException(
                    status_code=503,
                    detail="Pusher service not available - private channels not supported",
                )

            # For backward compatibility, handle private channels
            auth = pusher_client.authenticate(channel=channel_name, socket_id=socket_id)
            return auth
        # For public channels
        return {
            "status": "success",
            "message": "No authentication needed for public channels",
        }
    except HTTPException:
        # Re-raise HTTPExceptions as-is
        raise
    except Exception as e:
        print(f"Pusher authentication error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Pusher authentication failed: {str(e)}"
        ) from e
