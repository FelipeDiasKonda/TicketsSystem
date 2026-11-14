from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import create_app
from app.models import Ticket, TicketCategory, TicketPriority, User

HEADERS = {"X-CSRF-Protection": "1"}
PASSWORD = "ticket-test-password"


@pytest.fixture
def ticket_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    app = create_app()
    with Session(engine) as db:
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            yield client, db
    engine.dispose()


def register(client, role="employee", email="employee@example.com"):
    response = client.post(
        "/api/auth/register",
        headers=HEADERS,
        json={
            "name": "Ticket Requester",
            "email": email,
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
            "role": role,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def login(client, email):
    assert (
        client.post(
            "/api/auth/login",
            headers=HEADERS,
            json={
                "email": email,
                "password": PASSWORD,
            },
        ).status_code
        == 200
    )


def payload(**changes):
    return {
        "title": "  Cannot access email  ",
        "description": "  Email stops responding when I try to sign in.  ",
        "category": "it",
        "priority": "high",
        **changes,
    }


def create(client, **changes):
    return client.post("/api/tickets", json=payload(**changes), headers=HEADERS)


@pytest.mark.parametrize("role", ["employee", "support"])
def test_both_roles_create_committed_open_tickets(ticket_context, role):
    client, db = ticket_context
    user_id = register(client, role=role)
    response = create(client)
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Cannot access email"
    assert body["description"] == "Email stops responding when I try to sign in."
    assert body["category"] == "it" and body["priority"] == "high"
    assert body["status"] == "open"
    assert body["requester"] == {"id": user_id, "name": "Ticket Requester"}
    assert body["created_at"].endswith("Z")
    assert response.headers["cache-control"] == "no-store"
    with Session(db.get_bind()) as independent_session:
        saved = independent_session.get(Ticket, body["id"])
        assert saved is not None and saved.requester_id == user_id
    listing = client.get("/api/tickets").json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == body["id"]
    assert "description" not in listing["items"][0]
    assert "email" not in listing["items"][0]["requester"]


@pytest.mark.parametrize("category", ["it", "facilities", "hr"])
@pytest.mark.parametrize("priority", ["low", "medium", "high", "urgent"])
def test_all_categories_and_priorities(ticket_context, category, priority):
    client, _ = ticket_context
    register(client)
    assert create(client, category=category, priority=priority).status_code == 201


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "ab"},
        {"title": " " * 10},
        {"title": "x" * 151},
        {"description": "too short"},
        {"description": " " * 20},
        {"description": "x" * 5001},
        {"category": "unknown"},
        {"priority": "critical"},
        {"category": None},
        {"requester_id": 999},
        {"status": "closed"},
        {"created_at": "2020-01-01T00:00:00Z"},
    ],
)
def test_invalid_and_server_owned_fields_are_rejected(ticket_context, changes):
    client, db = ticket_context
    register(client)
    assert create(client, **changes).status_code == 422
    assert db.scalar(select(func.count()).select_from(Ticket)) == 0


def test_length_boundaries_and_required_fields(ticket_context):
    client, _ = ticket_context
    register(client)
    assert create(client, title="abc", description="x" * 10).status_code == 201
    assert create(client, title="x" * 150, description="x" * 5000).status_code == 201
    for key in payload():
        data = payload()
        del data[key]
        assert client.post("/api/tickets", json=data, headers=HEADERS).status_code == 422


def test_employee_scope_and_support_visibility(ticket_context):
    client, _ = ticket_context
    first_employee = register(client)
    first = create(client).json()["id"]
    register(client, email="other@example.com")
    second = create(client, title="Another employee's issue").json()["id"]
    own_list = client.get(f"/api/tickets?requester_id={first_employee}").json()
    assert own_list["total"] == 1
    assert [item["id"] for item in own_list["items"]] == [second]
    register(client, role="support", email="support@example.com")
    third = create(client, title="Support member's issue").json()["id"]
    support_list = client.get("/api/tickets").json()
    assert support_list["total"] == 3
    assert {item["id"] for item in support_list["items"]} == {first, second, third}
    login(client, "employee@example.com")
    first_list = client.get("/api/tickets").json()
    assert first_list["total"] == 1
    assert [item["id"] for item in first_list["items"]] == [first]


def test_default_pagination_and_date_order_with_ties(ticket_context):
    client, db = ticket_context
    user_id = register(client)
    initial = datetime(2026, 1, 1)
    for i in range(25):
        db.add(
            Ticket(
                title=f"Ticket {i}",
                description="A valid description",
                requester_id=user_id,
                category=TicketCategory.IT,
                priority=TicketPriority.LOW,
                created_at=initial + timedelta(seconds=i // 2),
            )
        )
    db.commit()
    # A newer ID with an older date verifies that creation date is the primary sort key.
    db.add(
        Ticket(
            title="Old ticket",
            description="An older description",
            requester_id=user_id,
            category=TicketCategory.IT,
            priority=TicketPriority.LOW,
            created_at=initial - timedelta(days=1),
        )
    )
    db.commit()
    first = client.get("/api/tickets").json()
    second = client.get("/api/tickets?page=2").json()
    assert first["page_size"] == 20 and first["page"] == 1 and first["total"] == 26
    assert [item["id"] for item in first["items"]] == list(range(25, 5, -1))
    assert [item["id"] for item in second["items"]] == [5, 4, 3, 2, 1, 26]
    assert client.get("/api/tickets?page=3").json()["items"] == []
    assert len(client.get("/api/tickets?page_size=5").json()["items"]) == 5


@pytest.mark.parametrize("query", ["page=0", "page=-1", "page_size=0", "page_size=101", "page=abc"])
def test_invalid_pagination(ticket_context, query):
    client, _ = ticket_context
    register(client)
    assert client.get(f"/api/tickets?{query}").status_code == 422


def test_empty_list(ticket_context):
    client, _ = ticket_context
    register(client)
    response = client.get("/api/tickets")
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}
    assert response.headers["cache-control"] == "no-store"


def test_authentication_and_csrf_are_required(ticket_context):
    client, db = ticket_context
    assert client.get("/api/tickets").status_code == 401
    assert create(client).status_code == 401
    register(client)
    assert client.post("/api/tickets", json=payload()).status_code == 403
    assert (
        client.post(
            "/api/tickets",
            json=payload(),
            headers={
                **HEADERS,
                "Origin": "https://untrusted.example",
            },
        ).status_code
        == 403
    )
    db.scalar(select(User)).is_active = False
    db.commit()
    assert client.get("/api/tickets").status_code == 401
    assert create(client).status_code == 401
    assert db.scalar(select(func.count()).select_from(Ticket)) == 0
