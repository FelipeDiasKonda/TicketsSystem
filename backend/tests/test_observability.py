import json
import logging

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.api.error_handlers import error_status
from app.core.errors import (
    AccessDeniedError,
    AppError,
    AssignmentConflictError,
    AuthenticationError,
    CsrfError,
    DatabaseUnavailableError,
    DuplicateEmailError,
    InvalidAssigneeError,
    InvalidCredentialsError,
    StatusConflictError,
    TicketNotFoundError,
)
from app.core.observability import (
    JsonLogFormatter,
    configure_logging,
    exception_metadata,
    request_id_context,
    safe_parameters,
)
from app.main import create_app
from app.schemas.auth import LoginRequest
from app.schemas.ticket import TicketListQuery


class InMemoryClient:
    """Drive async test routes with no I/O; fail if an actual async suspension occurs.

    This exercises the real ASGI middleware/handlers without network sockets.
    Existing TestClient suites cover synchronous endpoints and DB dependencies.
    """

    def __init__(self, app):
        self.app = app

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        return self.request("GET", url, headers=headers)

    def post(self, url, headers=None, json=None):
        return self.request("POST", url, headers=headers, body=json)

    def request(self, method, url, headers=None, body=None):
        path, _, query = url.partition("?")
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "scheme": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "root_path": "",
            "server": ("testserver", 80),
            "client": ("testclient", 123),
            "headers": [
                (key.lower().encode(), value.encode()) for key, value in (headers or {}).items()
            ],
        }
        if body is not None:
            scope["headers"].append((b"content-type", b"application/json"))
        messages = []

        async def receive():
            return {
                "type": "http.request",
                "body": json.dumps(body).encode() if body is not None else b"",
                "more_body": False,
            }

        async def send(message):
            messages.append(message)

        task = self.app(scope, receive, send)
        try:
            task.send(None)
        except StopIteration:
            pass
        else:
            raise AssertionError("Async I/O is unsupported by this isolated ASGI test driver.")
        finally:
            task.close()
        start = next(message for message in messages if message["type"] == "http.response.start")
        content = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        return httpx.Response(start["status"], headers=start["headers"], content=content)


@pytest.mark.parametrize(
    "kind,status,message",
    [
        (AuthenticationError, 401, "Please log in to continue."),
        (InvalidCredentialsError, 401, "Invalid email or password."),
        (AccessDeniedError, 403, "Access restricted to support staff."),
        (CsrfError, 403, "Request not authorized."),
        (TicketNotFoundError, 404, "Ticket not found."),
        (DuplicateEmailError, 409, "This email is already registered."),
        (StatusConflictError, 409, "Ticket status has changed. Refresh and try again."),
        (AssignmentConflictError, 409, "Ticket assignment has changed. Refresh and try again."),
        (InvalidAssigneeError, 422, "Assignee must be an active support member."),
        (DatabaseUnavailableError, 503, "Database unavailable"),
        (AppError, 500, "An unexpected error occurred."),
    ],
)
def test_central_error_contract(kind, status, message):
    error = kind()
    assert error_status(error) == status
    assert str(error) == message
    assert isinstance(error.code, str)


def test_logger_configuration_is_idempotent():
    configure_logging()
    configure_logging()
    assert (
        sum(
            getattr(handler, "tickets_handler", False)
            for handler in logging.getLogger("app").handlers
        )
        == 1
    )


def test_parameters_are_allowlisted_and_values_validated():
    assert safe_parameters(
        {
            "ticket_id": "42",
            "page": "2",
            "page_size": "20",
            "status": "open",
            "category": "hr",
            "priority": "high",
            "sort": "priority_desc",
            "password": "SECRET",
            "token": "SECRET",
            "email": "private@example.com",
            "description": "PRIVATE",
            "body": "PRIVATE",
        }
    ) == {
        "ticket_id": 42,
        "page": 2,
        "page_size": 20,
        "status": "open",
        "category": "hr",
        "priority": "high",
        "sort": "priority_desc",
    }
    assert (
        safe_parameters(
            {
                "page": "SECRET",
                "status": "SECRET",
                "category": "SECRET",
                "page_size": "9" * 500,
                "ticket_id": True,
            }
        )
        == {}
    )


def formatted_records(caplog):
    formatter = JsonLogFormatter()
    return [
        json.loads(formatter.format(record))
        for record in caplog.records
        if record.name.startswith("app.")
    ]


def test_service_logs_only_safe_parameters_and_correlates(caplog):
    from app.services.ticket_details import get_ticket  # Existing service retains source identity.

    caplog.set_level(logging.INFO, logger="app")
    token = request_id_context.set("fixture-correlation")

    # Use the real decorated service to check preserved metadata without DB/network.
    class EmptyDatabase:
        def scalar(self, statement):
            return None

    class Support:
        role = "support"

    try:
        with pytest.raises(TicketNotFoundError):
            get_ticket(EmptyDatabase(), Support(), 42)
    finally:
        request_id_context.reset(token)
    records = formatted_records(caplog)
    assert [row["event"] for row in records] == ["operation_started", "operation_failed"]
    assert all(row["request_id"] == "fixture-correlation" for row in records)
    assert all(row["file"] == "ticket_details.py" for row in records)
    assert records[-1]["error_code"] == "ticket_not_found"
    assert records[-1]["parameters"] == {"ticket_id": 42}
    assert request_id_context.get() is None


def test_exception_metadata_never_formats_sql_or_secret_values(caplog):
    caplog.set_level(logging.INFO, logger="app")
    from app.services import ticket_details

    class FailedDatabase:
        def scalar(self, statement):
            raise OperationalError(
                "INSERT SECRET_SQL", {"password": "SECRET_PASSWORD"}, Exception("SECRET_CONNECTION")
            )

    class Support:
        role = "support"

    try:
        ticket_details.get_ticket(FailedDatabase(), Support(), 9)
    except OperationalError as error:
        metadata = exception_metadata(error)
    else:
        pytest.fail("Expected the original exception to propagate unchanged.")
    serialized = json.dumps([formatted_records(caplog), metadata])
    assert "SECRET_" not in serialized
    assert metadata["error_type"] == "OperationalError"
    assert metadata["stack"][-1]["function"] == "scalar"
    assert set(metadata["stack"][-1]) == {"file", "function", "line"}


def test_successful_service_logs_duration_and_filters(caplog):
    from app.services.ticket import list_tickets

    class EmptyRows:
        def all(self):
            return []

    class Database:
        def scalar(self, statement):
            return 0

        def scalars(self, statement):
            return EmptyRows()

    class Support:
        role = "support"

    caplog.set_level(logging.INFO, logger="app")
    assert list_tickets(Database(), Support(), TicketListQuery(category="it")).total == 0
    records = formatted_records(caplog)
    assert records[-1]["event"] == "operation_completed"
    assert records[-1]["duration_ms"] >= 0
    assert records[-1]["parameters"]["category"] == "it"


def test_auth_service_logs_omit_credentials_and_tokens(caplog):
    from app.services.auth import authenticate_user, revoke_session

    class Database:
        def scalar(self, statement):
            return None

        def execute(self, statement):
            pass

    caplog.set_level(logging.INFO, logger="app")
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(Database(), "SECRET_EMAIL@example.com", "SECRET_PASSWORD")
    revoke_session(Database(), "SECRET_SESSION_TOKEN")
    records = formatted_records(caplog)
    assert records and all(row["parameters"] == {} for row in records)
    assert "SECRET" not in json.dumps(records)


@pytest.mark.parametrize("operation", ["create_ticket", "create_session"])
def test_creation_failures_roll_back_before_propagating(operation):
    from app.models.auth import User
    from app.schemas.ticket import TicketCreate
    from app.services.auth import create_session
    from app.services.ticket import create_ticket

    class Database:
        rolled_back = False

        def add(self, value):
            pass

        def flush(self):
            raise OperationalError("write", {}, Exception("fixture failure"))

        def execute(self, value):
            raise OperationalError("write", {}, Exception("fixture failure"))

        def rollback(self):
            self.rolled_back = True

    db = Database()
    actor = User(id=42)
    with pytest.raises(OperationalError):
        if operation == "create_ticket":
            create_ticket(
                db,
                actor,
                TicketCreate(
                    title="Failure test",
                    description="Rollback test.",
                    category="it",
                    priority="low",
                ),
            )
        else:
            create_session(db, actor, 8, "SECRET_SESSION_TOKEN")
    assert db.rolled_back


@pytest.mark.parametrize("kind", [TicketNotFoundError, StatusConflictError, InvalidAssigneeError])
def test_handlers_preserve_json_and_correlation(kind, caplog):
    app = create_app()

    @app.get("/api/log-test/{ticket_id}")
    async def fail(ticket_id: int):
        raise kind()

    caplog.set_level(logging.INFO, logger="app")
    with InMemoryClient(app) as client:
        response = client.get(
            "/api/log-test/42?page=2&password=SECRET",
            headers={"X-Request-ID": "untrusted-id", "Cookie": "SECRET_COOKIE"},
        )
    assert response.status_code == error_status(kind())
    assert response.json() == {"detail": str(kind())}
    assert response.headers["cache-control"] == "no-store"
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 32 and request_id != "untrusted-id"
    records = formatted_records(caplog)
    assert all(row["request_id"] == request_id for row in records)
    complete = next(row for row in records if row["event"] == "request_completed")
    assert complete["route"] == "/api/log-test/{ticket_id}"
    assert complete["parameters"] == {"ticket_id": 42, "page": 2}
    assert complete["operation"] == "fail"
    assert "SECRET" not in json.dumps(records)


def test_unexpected_sql_error_returns_safe_500_and_safe_stack(caplog):
    app = create_app()

    @app.get("/api/log-crash")
    async def crash():
        raise OperationalError("SECRET_SQL", {"token": "SECRET_TOKEN"}, Exception("SECRET_DSN"))

    @app.get("/api/log-ok")
    async def healthy():
        return {"status": "ok"}

    caplog.set_level(logging.INFO, logger="app")
    with InMemoryClient(app) as client:
        response = client.get("/api/log-crash")
        healthy = client.get("/api/log-ok")
    assert response.status_code == 500
    assert response.json() == {"detail": AppError.default_message}
    assert healthy.status_code == 200
    assert response.headers["x-request-id"] != healthy.headers["x-request-id"]
    records = formatted_records(caplog)
    assert "SECRET" not in json.dumps(records)
    error = next(row for row in records if row["event"] == "unexpected_error")
    assert error["error_type"] == "OperationalError" and error["stack"]
    assert error["request_id"] == response.headers["x-request-id"]


def test_validation_and_framework_errors_preserve_contracts(caplog):
    app = create_app()

    @app.post("/api/log-validate")
    async def validate(data: LoginRequest):
        return {"ok": True}

    caplog.set_level(logging.INFO, logger="app")
    with InMemoryClient(app) as client:
        response = client.post(
            "/api/log-validate",
            headers={"X-CSRF-Protection": "1"},
            json={"email": "invalid", "password": "SECRET_PASSWORD"},
        )
        missing = client.get("/api/not-found/SECRET_PATH?token=SECRET_TOKEN")
    assert response.status_code == 422
    assert all(set(item) == {"loc", "msg", "type"} for item in response.json()["detail"])
    assert "SECRET" not in response.text
    assert missing.status_code == 404 and missing.json() == {"detail": "Not Found"}
    assert "SECRET" not in json.dumps(formatted_records(caplog))
