from concurrent.futures import ThreadPoolExecutor
from itertools import product
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.database import Base, get_db
from app.main import create_app
from app.models import HistoryEvent, Ticket, TicketStatus, TicketStatusHistory, User, UserRole
from app.schemas.ticket import TicketCreate, TicketStatusUpdate
from app.services.ticket import StatusConflictError, create_ticket, update_ticket_status

HEADERS = {"X-CSRF-Protection": "1"}
PASSWORD = "workflow-test-password"
NEXT = {"open": "in_progress", "in_progress": "resolved", "resolved": "closed"}


@pytest.fixture
def status_context():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    app = create_app()
    with Session(engine) as db:
        employee = User(
            name="Employee",
            email="employee@example.com",
            role=UserRole.EMPLOYEE,
            password_hash=hash_password(PASSWORD),
        )
        support = User(
            name="Support",
            email="support@example.com",
            role=UserRole.SUPPORT,
            password_hash=hash_password(PASSWORD),
        )
        db.add_all([employee, support])
        db.commit()
        employee_id, support_id = employee.id, support.id
        ticket = create_ticket(
            db,
            employee,
            TicketCreate(
                title="Workflow issue",
                description="An issue that needs attention.",
                category="it",
                priority="high",
            ),
        )
        ticket_id = ticket.id
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            login(client, "support")
            yield client, db, ticket_id, employee_id, support_id
    engine.dispose()


def login(client, name):
    assert (
        client.post(
            "/api/auth/login",
            headers=HEADERS,
            json={
                "email": f"{name}@example.com",
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )


def change(client, ticket_id, expected, target):
    return client.patch(
        f"/api/tickets/{ticket_id}/status",
        headers=HEADERS,
        json={"expected_status": expected, "status": target},
    )


@pytest.mark.parametrize("current,target", list(product(TicketStatus, TicketStatus)))
def test_entire_transition_matrix(status_context, current, target):
    client, db, ticket_id, _, support_id = status_context
    db.get(Ticket, ticket_id).status = current
    db.commit()
    response = change(client, ticket_id, current.value, target.value)
    allowed = NEXT.get(current.value) == target.value
    assert response.status_code == (200 if allowed else 409)
    db.expire_all()
    assert db.get(Ticket, ticket_id).status == (target if allowed else current)
    history = db.scalars(select(TicketStatusHistory).order_by(TicketStatusHistory.id)).all()
    assert len(history) == (2 if allowed else 1)
    if allowed:
        assert response.json()["status"] == target.value
        assert response.headers["cache-control"] == "no-store"
        assert history[-1].previous_status == current and history[-1].new_status == target
        assert history[-1].changed_by_id == support_id
        assert history[-1].event == HistoryEvent.TRANSITION


def test_full_workflow_has_creation_and_three_changes(status_context):
    client, db, ticket_id, employee_id, support_id = status_context
    for expected, target in NEXT.items():
        assert change(client, ticket_id, expected, target).status_code == 200
    history = db.scalars(select(TicketStatusHistory).order_by(TicketStatusHistory.id)).all()
    assert [row.new_status.value for row in history] == [
        "open",
        "in_progress",
        "resolved",
        "closed",
    ]
    assert history[0].previous_status is None
    assert history[0].changed_by_id == employee_id and history[0].event == HistoryEvent.CREATED
    assert all(row.changed_by_id == support_id for row in history[1:])
    assert all(row.changed_at is not None for row in history)
    assert change(client, ticket_id, "closed", "open").status_code == 409


def test_stale_requests_cannot_repeat_or_override_a_change(status_context):
    client, db, ticket_id, _, _ = status_context
    assert change(client, ticket_id, "in_progress", "resolved").status_code == 409
    assert change(client, ticket_id, "open", "in_progress").status_code == 200
    stale = change(client, ticket_id, "open", "in_progress")
    assert stale.status_code == 409 and "changed" in stale.json()["detail"]
    assert db.scalar(select(func.count()).select_from(TicketStatusHistory)) == 2


def test_permissions_and_csrf(status_context):
    client, db, ticket_id, _, _ = status_context
    url = f"/api/tickets/{ticket_id}/status"
    body = {"expected_status": "open", "status": "in_progress"}
    assert client.patch(url, json=body).status_code == 403
    assert (
        client.patch(
            url, json=body, headers={**HEADERS, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    login(client, "employee")
    assert client.patch(url, json=body, headers=HEADERS).status_code == 403
    client.cookies.clear()
    assert client.patch(url, json=body, headers=HEADERS).status_code == 401
    assert db.get(Ticket, ticket_id).status == TicketStatus.OPEN


def test_missing_ticket(status_context):
    client, _, _, _, _ = status_context
    assert change(client, 999999, "open", "in_progress").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "in_progress"},
        {"expected_status": "open"},
        {"expected_status": "unknown", "status": "in_progress"},
        {"expected_status": "open", "status": "unknown"},
        {"expected_status": "open", "status": "in_progress", "changed_by_id": 100},
    ],
)
def test_invalid_update_payloads(status_context, body):
    client, _, ticket_id, _, _ = status_context
    assert (
        client.patch(f"/api/tickets/{ticket_id}/status", headers=HEADERS, json=body).status_code
        == 422
    )


def test_failed_history_insert_rolls_back_status(status_context):
    client, db, ticket_id, _, _ = status_context
    engine = db.get_bind()

    def fail_history(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO ticket_status_history"):
            raise OperationalError("history insert", {}, Exception("simulated failure"))

    event.listen(engine, "before_cursor_execute", fail_history)
    try:
        response = change(client, ticket_id, "open", "in_progress")
        assert response.status_code == 500
        assert response.json() == {"detail": "An unexpected error occurred."}
    finally:
        event.remove(engine, "before_cursor_execute", fail_history)
    db.expire_all()
    assert db.get(Ticket, ticket_id).status == TicketStatus.OPEN
    assert db.scalar(select(func.count()).select_from(TicketStatusHistory)) == 1


def test_simultaneous_updates_only_commit_one_transition(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'race.sqlite').as_posix()}", connect_args={"timeout": 10}
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(
            name="Support",
            email="support@example.com",
            role=UserRole.SUPPORT,
            password_hash="unused-fixture-hash",
        )
        db.add(user)
        db.commit()
        user_id = user.id
        ticket = create_ticket(
            db,
            user,
            TicketCreate(
                title="Concurrent issue",
                description="Concurrent status update test.",
                category="it",
                priority="medium",
            ),
        )
        ticket_id = ticket.id
    ready = Barrier(2)

    def wait_before_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE tickets SET status"):
            ready.wait(timeout=10)

    def move():
        with Session(engine) as db:
            actor = db.get(User, user_id)
            try:
                update_ticket_status(
                    db,
                    ticket_id,
                    actor,
                    TicketStatusUpdate(
                        expected_status="open",
                        status="in_progress",
                    ),
                )
                return 200
            except StatusConflictError:
                return 409

    event.listen(engine, "before_cursor_execute", wait_before_update)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: move(), range(2)))
        assert sorted(results) == [200, 409]
    finally:
        event.remove(engine, "before_cursor_execute", wait_before_update)
    with Session(engine) as db:
        assert db.get(Ticket, ticket_id).status == TicketStatus.IN_PROGRESS
        assert db.scalar(select(func.count()).select_from(TicketStatusHistory)) == 2
    engine.dispose()
