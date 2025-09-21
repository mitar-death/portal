from fastapi import APIRouter, Request, Depends

from server.app.controllers.diagnostics import (
    get_ai_diagnostics,
    reinitialize_ai_messenger,
)
from server.app.core.auth import require_auth

diagnostics_routes = APIRouter(dependencies=[Depends(require_auth)])


@diagnostics_routes.get("/diagnostics", tags=["Diagnotics"])
async def get_diagnostics(request: Request):
    """
    Get diagnostic information about the AI messenger system.
    Provides detailed status of AI clients, group mappings, and monitoring.
    """
    return await get_ai_diagnostics(request)


@diagnostics_routes.post("/diagnostics/reinitialize", tags=["Diagnotics"])
async def reinitialize_ai(request: Request):
    """
    Force reinitialization of the AI messenger system.
    This can be used to recover from a state where the AI messenger has stopped responding.
    """
    return await reinitialize_ai_messenger(request)
