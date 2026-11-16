import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.errors import (
    AccessDeniedError,
    AppError,
    AuthenticationError,
    ConflictError,
    DatabaseUnavailableError,
    InvalidInputError,
    NotFoundError,
)
from app.core.observability import exception_metadata, request_metadata

logger = logging.getLogger(__name__)


def error_status(error: AppError) -> int:
    for kind, status in (
        (AuthenticationError, 401),
        (AccessDeniedError, 403),
        (NotFoundError, 404),
        (ConflictError, 409),
        (InvalidInputError, 422),
        (DatabaseUnavailableError, 503),
    ):
        if isinstance(error, kind):
            return status
    return 500


def error_headers(request: Request) -> dict:
    headers = {"Cache-Control": "no-store"}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers


async def application_error(request: Request, error: AppError):
    status = error_status(error)
    logger.log(
        logging.ERROR if status >= 500 else logging.WARNING,
        "Application request rejected.",
        extra={
            **request_metadata(request.scope),
            "event": "application_error",
            "error_code": error.code,
            "error_type": type(error).__name__,
            "status_code": status,
        },
    )
    return JSONResponse(
        status_code=status, content={"detail": str(error)}, headers=error_headers(request)
    )


async def validation_error(request: Request, error: RequestValidationError):
    # Preserve the existing contract, excluding Pydantic's submitted input/context.
    errors = [{key: item[key] for key in ("loc", "msg", "type")} for item in error.errors()]
    logger.warning(
        "Request validation failed.",
        extra={
            **request_metadata(request.scope),
            "event": "validation_error",
            "status_code": 422,
            "error_code": "validation_error",
        },
    )
    return JSONResponse(status_code=422, content={"detail": errors}, headers=error_headers(request))


async def http_error(request: Request, error: HTTPException):
    # Includes framework 404/405 errors and any explicit HTTPException dependencies.
    return JSONResponse(
        status_code=error.status_code,
        content={"detail": error.detail},
        headers={**error_headers(request), **(error.headers or {})},
    )


async def unexpected_error(request: Request, error: Exception):
    logger.error(
        "Unexpected request failure.",
        extra={
            **request_metadata(request.scope),
            **exception_metadata(error),
            "event": "unexpected_error",
            "error_code": "unexpected_error",
            "status_code": 500,
        },
    )
    return JSONResponse(
        status_code=500,
        content={"detail": AppError.default_message},
        headers=error_headers(request),
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, application_error)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, unexpected_error)
