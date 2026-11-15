from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.db.database import Base, get_db
from app.main import create_app
from app.models import Ticket, TicketAssignmentHistory, User, UserRole
from app.schemas.ticket import TicketCreate
from app.schemas.ticket_details import AssignmentUpdate
from app.services.ticket import create_ticket
from app.services.ticket_details import AssignmentConflictError, assign_ticket

HEADERS = {"X-CSRF-Protection": "1"}


@pytest.fixture
def details_domain():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = [
            User(
                name=name,
                email=f"{name}@example.com",
                password_hash="unused",
                role=role,
                is_active=active,
            )
            for name, role, active in [
                ("employee", "employee", True),
                ("other", "employee", True),
                ("support", "support", True),
                ("second", "support", True),
                ("inactive", "support", False),
            ]
        ]
        db.add_all(users)
        db.commit()
        ticket = create_ticket(
            db,
            users[0],
            TicketCreate(
                title="Details issue",
                description="The full issue description.",
                category="it",
                priority="high",
            ),
        )
        ticket_id = ticket.id
        yield db, users, ticket_id
    engine.dispose()


@pytest.fixture
def details_context(details_domain):
    db, users, ticket_id = details_domain
    app = create_app()
    current = [users[2]]

    def authenticated():
        if current[0] is None:
            raise HTTPException(401, "Please log in to continue.")
        return current[0]

    app.dependency_overrides[get_current_user] = authenticated
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client, db, users, current, ticket_id


def assign(client, ticket_id, user_id, version=0):
    return client.patch(
        f"/api/tickets/{ticket_id}/assignee",
        headers=HEADERS,
        json={"assignee_id": user_id, "expected_assignment_version": version},
    )


def test_details_and_support_members(details_context):
    client, _, users, current, ticket_id = details_context
    response = client.get(f"/api/tickets/{ticket_id}")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    detail = response.json()
    assert detail["requester"] == {"id": users[0].id, "name": "employee"}
    assert detail["description"] == "The full issue description."
    assert detail["assignee"] is None and detail["assignment_version"] == 0
    assert detail["created_at"].endswith("Z")
    members = client.get("/api/tickets/support-members")
    assert {user["id"] for user in members.json()} == {users[2].id, users[3].id}
    current[0] = users[0]
    assert client.get("/api/tickets/support-members").status_code == 403
    assert client.get(f"/api/tickets/{ticket_id}").status_code == 200


@pytest.mark.parametrize("path", ["", "/comments", "/history"])
def test_private_resources_hide_foreign_and_missing_tickets(details_context, path):
    client, _, users, current, ticket_id = details_context
    current[0] = users[1]
    assert client.get(f"/api/tickets/{ticket_id}{path}").status_code == 404
    assert client.get(f"/api/tickets/9999{path}").status_code == 404
    current[0] = None
    assert client.get(f"/api/tickets/{ticket_id}{path}").status_code == 401


def test_assignment_workflow_history_and_stale_requests(details_context):
    client, db, users, _, ticket_id = details_context
    first = assign(client, ticket_id, users[2].id)
    assert first.status_code == 200 and first.json()["assignee"]["id"] == users[2].id
    assert assign(client, ticket_id, users[3].id).status_code == 409
    assert assign(client, ticket_id, users[3].id, 1).status_code == 200
    assert assign(client, ticket_id, None, 2).status_code == 200
    assert assign(client, ticket_id, users[2].id, 0).status_code == 409
    # A no-op never adds misleading assignment events.
    assert assign(client, ticket_id, None, 3).status_code == 200
    assert db.scalar(select(func.count()).select_from(TicketAssignmentHistory)) == 3
    history = client.get(f"/api/tickets/{ticket_id}/history").json()
    assert history["total"] == 4
    assignments = [item for item in history["items"] if item["event"] == "assignment"]
    assert assignments[0]["previous_assignee"]["id"] == users[3].id
    assert assignments[0]["new_assignee"] is None
    assert assignments[-1]["actor"]["id"] == users[2].id
    assert all(item["changed_at"].endswith("Z") for item in history["items"])


@pytest.mark.parametrize("index", [0, 1, 4, None])
def test_assignee_must_be_active_support(details_context, index):
    client, _, users, _, ticket_id = details_context
    response = assign(client, ticket_id, users[index].id if index is not None else 9999)
    assert response.status_code == 422


def test_write_permissions_and_csrf(details_context):
    client, _, users, current, ticket_id = details_context
    path = f"/api/tickets/{ticket_id}"
    body = {"assignee_id": users[2].id, "expected_assignment_version": 0}
    assert client.patch(path + "/assignee", json=body).status_code == 403
    assert client.post(path + "/comments", json={"body": "test"}).status_code == 403
    assert (
        client.post(
            path + "/comments",
            headers={**HEADERS, "Origin": "https://evil.test"},
            json={"body": "test"},
        ).status_code
        == 403
    )
    current[0] = users[0]
    assert assign(client, ticket_id, users[2].id).status_code == 403
    assert (
        client.post(
            path + "/comments", headers=HEADERS, json={"body": "  Employee comment  "}
        ).status_code
        == 201
    )
    current[0] = users[1]
    assert (
        client.post(
            path + "/comments", headers=HEADERS, json={"body": "Foreign comment"}
        ).status_code
        == 404
    )
    current[0] = None
    assert assign(client, ticket_id, users[2].id).status_code == 401


def test_comments_after_close_and_pagination(details_context):
    client, db, users, current, ticket_id = details_context
    db.get(Ticket, ticket_id).status = "closed"
    db.commit()
    path = f"/api/tickets/{ticket_id}/comments"
    for index in range(23):
        response = client.post(path, headers=HEADERS, json={"body": f"  Comment {index}  "})
        assert response.status_code == 201
        assert response.json()["body"] == f"Comment {index}"
        assert response.json()["author"]["id"] == users[2].id
        assert response.json()["created_at"].endswith("Z")
    first = client.get(path).json()
    second = client.get(path + "?page=2").json()
    assert first["total"] == second["total"] == 23
    assert len(first["items"]) == 20 and len(second["items"]) == 3
    assert first["items"][0]["body"] == "Comment 22"
    assert not ({x["id"] for x in first["items"]} & {x["id"] for x in second["items"]})
    current[0] = users[0]
    assert client.get(path).json()["total"] == 23


@pytest.mark.parametrize("body", ["", "   ", "x" * 5001])
def test_comment_validation(details_context, body):
    client, _, _, _, ticket_id = details_context
    assert (
        client.post(
            f"/api/tickets/{ticket_id}/comments", headers=HEADERS, json={"body": body}
        ).status_code
        == 422
    )


def test_forged_fields_and_pagination_validation(details_context):
    client, _, users, _, ticket_id = details_context
    path = f"/api/tickets/{ticket_id}"
    assert (
        client.post(
            path + "/comments", headers=HEADERS, json={"body": "text", "author_id": users[1].id}
        ).status_code
        == 422
    )
    assert (
        client.patch(path + "/assignee", headers=HEADERS, json={"assignee_id": None}).status_code
        == 422
    )
    for activity in ("comments", "history"):
        for query in ("page=0", "page_size=101", "page_size=0"):
            assert client.get(f"{path}/{activity}?{query}").status_code == 422


def test_combined_history_pagination_snapshot_and_status(details_context):
    client, db, users, _, ticket_id = details_context
    assert assign(client, ticket_id, users[2].id).status_code == 200
    assert (
        client.patch(
            f"/api/tickets/{ticket_id}/status",
            headers=HEADERS,
            json={"expected_status": "open", "status": "in_progress"},
        ).status_code
        == 200
    )
    path = f"/api/tickets/{ticket_id}/history?page_size=1"
    pages = [client.get(path + f"&page={page}").json() for page in (1, 2, 3)]
    assert all(page["total"] == 3 for page in pages)
    assert [page["items"][0]["event"] for page in pages] == ["transition", "assignment", "created"]
    # Legacy tickets keep their true creation date and a separately labeled observed state.
    from app.models import TicketStatusHistory

    entry = db.scalar(select(TicketStatusHistory).where(TicketStatusHistory.event == "created"))
    entry.event = "snapshot"
    entry.changed_by_id = None
    db.commit()
    history = client.get(f"/api/tickets/{ticket_id}/history").json()
    assert history["total"] == 4
    snapshot = next(item for item in history["items"] if item["event"] == "snapshot")
    assert snapshot["actor"] is None


def test_assignment_audit_failure_rolls_back(details_context):
    client, db, users, _, ticket_id = details_context
    engine = db.get_bind()

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO ticket_assignment_history"):
            raise OperationalError("audit insert", {}, Exception("simulated"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(OperationalError):
            assign(client, ticket_id, users[2].id)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    db.expire_all()
    assert db.get(Ticket, ticket_id).assignee_id is None
    assert db.get(Ticket, ticket_id).assignment_version == 0


def test_simultaneous_assignments_only_one_commits(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'assignment.sqlite').as_posix()}", connect_args={"timeout": 10}
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        actor = User(
            name="Support",
            email="support@example.com",
            role=UserRole.SUPPORT,
            password_hash="unused",
        )
        db.add(actor)
        db.commit()
        user_id = actor.id
        ticket_id = create_ticket(
            db,
            actor,
            TicketCreate(
                title="Concurrent ticket",
                description="Concurrency assignment fixture.",
                category="it",
                priority="low",
            ),
        ).id
    barrier = Barrier(2)

    def wait(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE tickets SET assignee_id"):
            barrier.wait(timeout=10)

    def change():
        with Session(engine) as db:
            try:
                assign_ticket(
                    db,
                    db.get(User, user_id),
                    ticket_id,
                    AssignmentUpdate(
                        assignee_id=user_id,
                        expected_assignment_version=0,
                    ),
                )
                return 200
            except AssignmentConflictError:
                return 409

    event.listen(engine, "before_cursor_execute", wait)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(lambda _: change(), range(2))) == [200, 409]
    finally:
        event.remove(engine, "before_cursor_execute", wait)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(TicketAssignmentHistory)) == 1
        assert db.get(Ticket, ticket_id).assignment_version == 1
    engine.dispose()
