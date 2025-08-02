from fastapi import Request, HTTPException
from server.app.core.logging import logger
from server.app.services.monitor import diagnostic_check, ensure_messenger_ai_initialized

async def get_ai_diagnostics(request: Request):
    """
    Get diagnostic information about the AI messenger system.
    This includes:
    - Status of telegram clients
    - AI accounts initialization status
    - Group-to-AI mappings
    - Keywords monitoring status
    """
    try:
        # Get diagnostics from the monitor service
        diagnostics = await diagnostic_check()
        
        # Add version and timestamp
        from datetime import datetime
        import platform
        from server.app.core.config import settings
        
        diagnostics["timestamp"] = datetime.now().isoformat()
        diagnostics["system_info"] = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "api_version": getattr(settings, "API_VERSION", "1.0.0")
        }
        
        logger.info(f"AI messenger diagnostics requested")
        return diagnostics
        
    except Exception as e:
        logger.error(f"Error in AI diagnostics controller: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving diagnostics: {str(e)}")


async def reinitialize_ai_messenger(request: Request):
    """
    Force reinitialization of the AI messenger system.
    This can be used to recover from a state where messenger_ai is None.
    """
    try:
        # Force a reinitialization of the messenger_ai
        result = await ensure_messenger_ai_initialized()
        
        if result:
            logger.info("Successfully reinitialized AI messenger")
            # Get updated diagnostics
            diagnostics = await diagnostic_check()
            return {
                "success": True,
                "message": "AI messenger successfully reinitialized",
                "diagnostics": diagnostics
            }
        else:
            logger.warning("Failed to reinitialize AI messenger")
            return {
                "success": False,
                "message": "Failed to reinitialize AI messenger",
                "diagnostics": await diagnostic_check()
            }
    except Exception as e:
        logger.error(f"Error reinitializing AI messenger: {e}")
        raise HTTPException(status_code=500, detail=f"Error reinitializing AI messenger: {str(e)}")
