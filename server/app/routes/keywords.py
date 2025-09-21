from fastapi import APIRouter, Depends, Request

from server.app.controllers.keywords import (
    get_keywords_controller,
    add_keywords_controller,
    delete_keywords_controller,
)
from server.app.core.auth import require_auth

keywords_routes = APIRouter(dependencies=[Depends(require_auth)])


@keywords_routes.get("/keywords", tags=["Keywords"])
async def get_keywords(request: Request):
    """
    Get the list of keywords for message filtering.
    """
    return await get_keywords_controller(request)


@keywords_routes.post("/add/keywords", tags=["Keywords"])
async def add_keywords(request: Request):
    """
    Add keywords for message filtering.
    """
    return await add_keywords_controller(request)


@keywords_routes.post("/delete/keywords", tags=["Keywords"])
async def delete_keywords(request: Request):
    """
    Delete keywords for message filtering.
    """
    return await delete_keywords_controller(request)
