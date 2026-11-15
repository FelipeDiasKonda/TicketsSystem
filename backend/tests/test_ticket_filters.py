from datetime import datetime, timedelta
from itertools import product

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.database import Base, get_db
from app.main import create_app
from app.models import Ticket, TicketCategory, TicketPriority, TicketStatus, User, UserRole

PASSWORD = "filter-test-password"


@pytest.fixture
def filter_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = create_app()
    with Session(engine) as db:
        users = [
            User(
                name=name,
                email=f"{name}@example.com",
                role=role,
                password_hash=hash_password(PASSWORD),
            )
            for name, role in (
                ("first", UserRole.EMPLOYEE),
                ("second", UserRole.EMPLOYEE),
                ("support", UserRole.SUPPORT),
            )
        ]
        db.add_all(users)
        db.flush()
        employee_id = users[0].id
        records = []
        for user, status, category, priority in product(
            users,
            TicketStatus,
            TicketCategory,
            TicketPriority,
        ):
            ticket = Ticket(
                title=f"Filter test {len(records) + 1}",
                description="A test support request.",
                requester_id=user.id,
                status=status,
                category=category,
                priority=priority,
                created_at=datetime(2026, 1, 1) + timedelta(seconds=len(records) // 2),
            )
            db.add(ticket)
            db.flush()
            records.append(
                {
                    "id": ticket.id,
                    "requester_id": user.id,
                    "status": status.value,
                    "category": category.value,
                    "priority": priority.value,
                }
            )
        db.commit()
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            login(client, "support")
            yield client, db, records, employee_id
    engine.dispose()


def login(client, name):
    response = client.post(
        "/api/auth/login",
        headers={"X-CSRF-Protection": "1"},
        json={
            "email": f"{name}@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200


FILTERS = (
    [{"status": status.value} for status in TicketStatus]
    + [{"category": category.value} for category in TicketCategory]
    + [{"priority": priority.value} for priority in TicketPriority]
    + [
        {"status": "open", "category": "it"},
        {"status": "resolved", "priority": "urgent"},
        {"category": "hr", "priority": "low"},
        {"status": "closed", "category": "facilities", "priority": "high"},
    ]
)


@pytest.mark.parametrize("filters", FILTERS)
def test_independent_and_combined_filters_use_filtered_total(filter_context, filters):
    client, _, records, _ = filter_context
    response = client.get("/api/tickets", params={**filters, "page_size": 100})
    assert response.status_code == 200
    expected = [
        row["id"]
        for row in reversed(records)
        if all(row[field] == value for field, value in filters.items())
    ]
    body = response.json()
    assert body["total"] == len(expected)
    assert [item["id"] for item in body["items"]] == expected


@pytest.mark.parametrize("sort,descending", [("created_desc", True), ("created_asc", False)])
def test_creation_order_and_timestamp_ties(filter_context, sort, descending):
    client, _, _, _ = filter_context
    response = client.get("/api/tickets", params={"sort": sort, "page_size": 100})
    expected = list(range(144, 44, -1)) if descending else list(range(1, 101))
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == expected
    if descending:
        default = client.get("/api/tickets", params={"page_size": 100})
        assert default.json() == response.json()


@pytest.mark.parametrize(
    "sort,priorities",
    [
        ("priority_desc", ["urgent", "high", "medium", "low"]),
        ("priority_asc", ["low", "medium", "high", "urgent"]),
    ],
)
def test_business_priority_order_and_newest_first_ties(filter_context, sort, priorities):
    client, _, _, _ = filter_context
    body = client.get(
        "/api/tickets",
        params={
            "sort": sort,
            "category": "it",
            "page_size": 100,
        },
    ).json()
    assert body["total"] == 48
    assert [item["priority"] for item in body["items"]] == [
        p for p in priorities for _ in range(12)
    ]
    for priority in priorities:
        ties = [
            (item["created_at"], item["id"])
            for item in body["items"]
            if item["priority"] == priority
        ]
        assert ties == sorted(ties, reverse=True)


@pytest.mark.parametrize("sort", ["created_desc", "created_asc", "priority_desc", "priority_asc"])
def test_filtered_pagination_has_no_gaps_or_duplicates(filter_context, sort):
    client, _, _, _ = filter_context
    filters = {"status": "open", "category": "it", "sort": sort}
    all_items = client.get("/api/tickets", params={**filters, "page_size": 100}).json()
    collected = []
    for page in range(1, 7):
        body = client.get(
            "/api/tickets",
            params={
                **filters,
                "page_size": 2,
                "page": page,
            },
        ).json()
        assert body["total"] == 12 and body["page"] == page and body["page_size"] == 2
        collected.extend(item["id"] for item in body["items"])
    assert collected == [item["id"] for item in all_items["items"]]
    assert len(set(collected)) == 12
    assert (
        client.get(
            "/api/tickets",
            params={
                **filters,
                "page_size": 2,
                "page": 7,
            },
        ).json()["items"]
        == []
    )


@pytest.mark.parametrize("sort", ["created_desc", "created_asc", "priority_desc", "priority_asc"])
def test_filters_never_expand_employee_scope(filter_context, sort):
    client, _, records, employee_id = filter_context
    filters = {"status": "open", "category": "it", "priority": "urgent", "sort": sort}
    assert client.get("/api/tickets", params=filters).json()["total"] == 3
    login(client, "first")
    body = client.get("/api/tickets", params={**filters, "requester_id": 3}).json()
    expected = [
        row["id"]
        for row in records
        if row["requester_id"] == employee_id
        and all(row[key] == filters[key] for key in ("status", "category", "priority"))
    ]
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == expected


def test_no_matching_tickets_returns_empty_filtered_result(filter_context):
    client, db, _, _ = filter_context
    db.execute(
        delete(Ticket).where(
            Ticket.category == TicketCategory.HR,
            Ticket.status == TicketStatus.CLOSED,
            Ticket.priority == TicketPriority.LOW,
        )
    )
    db.commit()
    body = client.get(
        "/api/tickets",
        params={
            "category": "hr",
            "status": "closed",
            "priority": "low",
        },
    ).json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 20}
    assert client.get("/api/tickets").json()["total"] == 141


@pytest.mark.parametrize(
    "query",
    [
        {"status": "unknown"},
        {"category": "finance"},
        {"priority": "critical"},
        {"sort": "title"},
        {"sort": "priority; DROP TABLE tickets"},
        {"status": ""},
        {"category": ""},
        {"priority": ""},
        {"sort": ""},
    ],
)
def test_invalid_filter_and_sort_values_are_rejected(filter_context, query):
    client, _, _, _ = filter_context
    assert client.get("/api/tickets", params=query).status_code == 422


def test_openapi_documents_all_query_parameters(filter_context):
    client, _, _, _ = filter_context
    parameters = client.get("/openapi.json").json()["paths"]["/api/tickets"]["get"]["parameters"]
    assert {parameter["name"] for parameter in parameters} == {
        "page",
        "page_size",
        "status",
        "category",
        "priority",
        "sort",
    }
