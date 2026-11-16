from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers, unexpected_error
from app.api.routes.router import api_router
from app.core.config import get_settings
from app.core.lifespan import lifespan
from app.core.observability import RequestLoggingMiddleware, configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.0.0", lifespan=lifespan)

    register_error_handlers(app)
    app.add_middleware(RequestLoggingMiddleware, on_error=unexpected_error)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Protection"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()
