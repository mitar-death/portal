

from fastapi import APIRouter, Request, Depends

from server.app.schemas.schemas import (
    GroupsResponse,
    SelectedGroupsRequest
)
from server.app.controllers.groups import (
    get_user_groups,
    monitor_groups,
)
from server.app.core.auth import require_auth

groups_routes = APIRouter(dependencies=[Depends(require_auth)]) 


@groups_routes.post('/add/selected-groups', tags=['Groups'], response_model=GroupsResponse)
async def add_selected_groups(
    request: Request,
    selected_groups: SelectedGroupsRequest):
    """
    Add selected Telegram groups for monitoring
    """

    groups = await monitor_groups(request,selected_groups)
    return {"groups": groups}

@groups_routes.get('/telegram/groups', tags=['Groups'], response_model=GroupsResponse)
async def get_groups(
   request: Request):
    """
    Get user's Telegram groups
    """

    groups = await get_user_groups(request)
    return {"groups": groups}

