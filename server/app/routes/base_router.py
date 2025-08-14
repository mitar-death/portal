from fastapi import APIRouter
from server.app.routes.auth import auth_routes
from server.app.routes.ai import ai_routes
from server.app.routes.diagnostics import diagnostics_routes
from server.app.routes.groups import groups_routes
from server.app.routes.keywords import keywords_routes
from server.app.routes.main import main_routes

router = APIRouter()
router.include_router(main_routes)
router.include_router(auth_routes)
router.include_router(ai_routes)
router.include_router(diagnostics_routes)
router.include_router(groups_routes)
router.include_router(keywords_routes)


