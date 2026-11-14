from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, verify_password
from app.db.database import Base, get_db
from app.main import create_app
from app.models import (
    AuthSession,
    Ticket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    User,
    UserRole,
)
from app.models.auth import utc_now
from app.services.seed import SeedPasswordError, seed_demo_data

PASSWORD = "Seed-test-password-123"


@pytest.fixture
def seed_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    yield engine, factory
    engine.dispose()


def test_seed_is_repeatable_with_three_tickets_owned_by_employees(seed_context):
    _, factory = seed_context
    with factory() as db:
        first = seed_demo_data(db, PASSWORD)
    assert (first.users_created, first.users_updated, first.tickets_created) == (6, 0, 3)
    with factory() as db:
        second = seed_demo_data(db, PASSWORD)
    assert (second.users_created, second.users_updated, second.tickets_created) == (0, 6, 0)
    with factory() as db:
        users = db.scalars(select(User)).all()
        tickets = db.scalars(select(Ticket)).all()
        assert len(users) == 6 and len(tickets) == 3
        assert sum(user.role == UserRole.EMPLOYEE for user in users) == 3
        assert sum(user.role == UserRole.SUPPORT for user in users) == 3
        assert {user.email for user in users} == {
            f"{prefix}{index}@gmail.com"
            for prefix in ("funcionario", "suporte")
            for index in range(1, 4)
        }
        assert len({user.password_hash for user in users}) == 6
        for user in users:
            assert user.is_active and verify_password(PASSWORD, user.password_hash)
        assert {ticket.category for ticket in tickets} == set(TicketCategory)
        assert all(ticket.status == TicketStatus.OPEN for ticket in tickets)
        assert all(ticket.requester.role == UserRole.EMPLOYEE for ticket in tickets)
        assert len({ticket.requester_id for ticket in tickets}) == 3


@pytest.mark.parametrize("prefix,expected_total", [("funcionario", 1), ("suporte", 3)])
def test_seeded_accounts_can_login_and_see_the_correct_scope(seed_context, prefix, expected_total):
    _, factory = seed_context
    with factory() as db:
        seed_demo_data(db, PASSWORD)
    app = create_app()

    def database():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        for index in range(1, 4):
            response = client.post(
                "/api/auth/login",
                headers={"X-CSRF-Protection": "1"},
                json={
                    "email": f"{prefix}{index}@gmail.com",
                    "password": PASSWORD,
                },
            )
            assert response.status_code == 200
            assert client.get("/api/tickets").json()["total"] == expected_total


def test_refresh_demo_accounts_preserves_other_data_and_existing_demo_tickets(seed_context):
    _, factory = seed_context
    with factory() as db:
        outsider = User(
            name="Existing User",
            email="existing@example.com",
            role=UserRole.SUPPORT,
            password_hash=hash_password("Unrelated-user-password"),
            is_active=True,
        )
        demo = User(
            name="Old demo name",
            email="funcionario1@gmail.com",
            role=UserRole.SUPPORT,
            password_hash=hash_password("Previous-demo-password"),
            is_active=False,
        )
        db.add_all([outsider, demo])
        db.flush()
        outsider_id, demo_id = outsider.id, demo.id
        outsider_hash = outsider.password_hash
        db.add(
            Ticket(
                title="Existing request",
                description="An unrelated support request.",
                category=TicketCategory.IT,
                priority=TicketPriority.LOW,
                requester_id=outsider_id,
            )
        )
        for user, token in [(outsider, "unrelated"), (demo, "old-demo")]:
            db.add(
                AuthSession(
                    user_id=user.id,
                    token_hash=token,
                    expires_at=utc_now() + timedelta(hours=1),
                )
            )
        db.commit()
    with factory() as db:
        seed_demo_data(db, PASSWORD)
    with factory() as db:
        assert db.get(User, outsider_id).password_hash == outsider_hash
        demo = db.get(User, demo_id)
        assert demo.name == "Funcionário 1" and demo.role == UserRole.EMPLOYEE and demo.is_active
        assert verify_password(PASSWORD, demo.password_hash)
        assert (
            db.scalar(select(AuthSession).where(AuthSession.token_hash == "unrelated")) is not None
        )
        assert db.scalar(select(AuthSession).where(AuthSession.token_hash == "old-demo")) is None
        ticket = db.scalar(select(Ticket).where(Ticket.requester_id == demo_id))
        ticket.status = TicketStatus.RESOLVED
        ticket.description = "Updated description that must not be reset."
        ticket_id = ticket.id
        db.commit()
    with factory() as db:
        seed_demo_data(db, PASSWORD)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 7
        assert db.scalar(select(func.count()).select_from(Ticket)) == 4
        assert db.get(Ticket, ticket_id).status == TicketStatus.RESOLVED
        assert (
            db.get(Ticket, ticket_id).description == "Updated description that must not be reset."
        )


@pytest.mark.parametrize("password", [None, "", "short", " " * 12, "x" * 129])
def test_invalid_password_does_not_modify_database(seed_context, password):
    _, factory = seed_context
    with factory() as db, pytest.raises(SeedPasswordError):
        seed_demo_data(db, password)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0


def test_seed_rolls_back_all_changes_if_any_insert_fails(seed_context):
    engine, factory = seed_context
    ticket_inserts = 0

    def fail_second_ticket(connection, cursor, statement, parameters, context, executemany):
        nonlocal ticket_inserts
        if statement.startswith("INSERT INTO tickets"):
            ticket_inserts += 1
            if ticket_inserts == 2:
                raise RuntimeError("Simulated seed failure")

    event.listen(engine, "before_cursor_execute", fail_second_ticket)
    try:
        with factory() as db, pytest.raises(RuntimeError, match="Simulated seed failure"):
            seed_demo_data(db, PASSWORD)
    finally:
        event.remove(engine, "before_cursor_execute", fail_second_ticket)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 0
        assert db.scalar(select(func.count()).select_from(Ticket)) == 0
