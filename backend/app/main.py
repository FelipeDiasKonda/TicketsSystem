from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.router import api_router
from app.core.config import get_settings
from app.core.lifespan import lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
