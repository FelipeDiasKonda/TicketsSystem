"""Structured application logs with allowlisted request/operation metadata."""

import inspect
import json
import logging
import traceback
from contextvars import ContextVar
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import QueryParams
from starlette.requests import Request

from app.core.errors import AppError

request_id_context = ContextVar("request_id", default=None)
QUERY_VALUES = {
    "status": {"open", "in_progress", "resolved", "closed"},
    "category": {"it", "facilities", "hr"},
    "priority": {"low", "medium", "high", "urgent"},
    "sort": {"created_desc", "created_asc", "priority_desc", "priority_asc"},
}


def safe_parameters(values) -> dict:
    """Never copy arbitrary query strings, payloads, credentials or exception text."""
    result = {}
    for key in ("ticket_id", "page", "page_size"):
        value = values.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            result[key] = value
        elif isinstance(value, str) and value.isascii() and value.isdecimal() and len(value) <= 10:
            result[key] = int(value)
    for key, allowed in QUERY_VALUES.items():
        value = values.get(key)
        if isinstance(value, str) and value in allowed:
            result[key] = value
    return result


def exception_metadata(error: Exception) -> dict:
    # SQLAlchemy exception messages may contain SQL parameters and connection secrets.
    # Record locations, never exception text, source lines, locals or chained exceptions.
    return {
        "error_type": type(error).__name__,
        "stack": [
            {"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
            for frame in traceback.extract_tb(error.__traceback__)
        ],
    }


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "file": getattr(record, "source_file", record.filename),
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_context.get()),
        }
        for key in (
            "event",
            "operation",
            "method",
            "route",
            "parameters",
            "status_code",
            "duration_ms",
            "error_code",
            "error_type",
            "stack",
            "source",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    logger = logging.getLogger("app")
    if not any(getattr(handler, "tickets_handler", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.tickets_handler = True
        handler.setFormatter(JsonLogFormatter())
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def logged_operation(function):
    """Observe service boundaries without catching/translating business failures."""
    logger = logging.getLogger(function.__module__)
    signature = inspect.signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        parameters = safe_parameters(bound.arguments)
        query = bound.arguments.get("query")
        if query is not None:
            parameters.update(safe_parameters(query.model_dump()))
        metadata = {
            "request_id": request_id_context.get(),
            "operation": function.__name__,
            "source": function.__module__,
            "source_file": Path(function.__code__.co_filename).name,
            "parameters": parameters,
        }
        started = perf_counter()
        logger.info("Service operation started.", extra={**metadata, "event": "operation_started"})
        try:
            result = function(*args, **kwargs)
        except Exception as error:
            logger.log(
                logging.WARNING if isinstance(error, AppError) else logging.ERROR,
                "Service operation failed.",
                extra={
                    **metadata,
                    "event": "operation_failed",
                    "error_type": type(error).__name__,
                    "error_code": error.code if isinstance(error, AppError) else "unexpected_error",
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            raise
        logger.info(
            "Service operation completed.",
            extra={
                **metadata,
                "event": "operation_completed",
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return result

    return wrapped


def request_metadata(scope) -> dict:
    endpoint = scope.get("endpoint")
    route = scope.get("route")
    return {
        "request_id": scope.get("state", {}).get("request_id"),
        "method": scope.get("method"),
        "route": getattr(route, "path", "<unmatched>"),
        "source": getattr(endpoint, "__module__", None),
        "source_file": Path(endpoint.__code__.co_filename).name
        if endpoint is not None and hasattr(endpoint, "__code__")
        else "observability.py",
        "operation": getattr(endpoint, "__name__", None),
        "parameters": {
            **safe_parameters(QueryParams(scope.get("query_string", b""))),
            **safe_parameters(scope.get("path_params", {})),
        },
    }


class RequestLoggingMiddleware:
    def __init__(self, app, on_error):
        self.app = app
        self.on_error = on_error

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started = perf_counter()
        status_code = 500
        response_started = False

        async def observed_send(message):
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                message = {
                    **message,
                    "headers": [*headers, (b"x-request-id", request_id.encode("ascii"))],
                }
            await send(message)

        try:
            try:
                await self.app(scope, receive, observed_send)
            except Exception as error:
                # Handle before the server can log an unsanitized SQL/driver exception.
                response = await self.on_error(Request(scope), error)
                if response_started:
                    raise RuntimeError("Response stream failed.") from None
                await response(scope, receive, observed_send)
        finally:
            logging.getLogger("app.http").log(
                logging.ERROR
                if status_code >= 500
                else logging.WARNING
                if status_code >= 400
                else logging.INFO,
                "HTTP request completed.",
                extra={
                    **request_metadata(scope),
                    "event": "request_completed",
                    "status_code": status_code,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            request_id_context.reset(token)
