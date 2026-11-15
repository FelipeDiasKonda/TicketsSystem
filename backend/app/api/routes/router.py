from fastapi import APIRouter

from app.api.routes.endpoints.auth import router as auth_router
from app.api.routes.endpoints.health import router as health_router
from app.api.routes.endpoints.ticket_details import router as ticket_details_router
from app.api.routes.endpoints.tickets import router as tickets_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(tickets_router, tags=["tickets"])
api_router.include_router(ticket_details_router, tags=["tickets"])
