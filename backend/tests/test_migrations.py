from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.db.database import Base
from app.models import AuthSession, User  # noqa: F401


def test_migration_upgrade_matches_models_and_can_downgrade():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) == {
            "users",
            "auth_sessions",
            "alembic_version",
            "tickets",
            "ticket_status_history",
            "ticket_comments",
            "ticket_assignment_history",
        }
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
        command.downgrade(config, "base")
        assert set(inspect(connection).get_table_names()) == {"alembic_version"}
    engine.dispose()


def test_ticket_migration_preserves_existing_users_and_sessions():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
        connection.execute(
            User.__table__.insert().values(
                id=1,
                name="Existing User",
                email="existing@example.com",
                password_hash="unused-fixture-hash",
                role="employee",
                is_active=True,
                created_at=datetime(2026, 1, 1),
            )
        )
        connection.execute(
            AuthSession.__table__.insert().values(
                user_id=1,
                token_hash="fixture-token-hash",
                expires_at=datetime(2027, 1, 1),
                created_at=datetime(2026, 1, 1),
            )
        )
        command.upgrade(config, "head")
        assert connection.scalar(text("SELECT name FROM users WHERE id=1")) == "Existing User"
        assert connection.scalar(text("SELECT count(*) FROM auth_sessions")) == 1
        command.downgrade(config, "0001")
        assert "tickets" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT count(*) FROM users")) == 1
        assert connection.scalar(text("SELECT count(*) FROM auth_sessions")) == 1
    engine.dispose()


def test_history_migration_snapshots_existing_state_without_inventing_actor():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0002")
        connection.execute(
            text(
                "INSERT INTO users (id, name, email, password_hash, role, is_active, created_at) "
                "VALUES (1, 'Existing', 'existing@example.com', 'fixture', "
                "'employee', 1, '2026-01-01')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO tickets (id, title, description, category, priority, status, "
                "requester_id, created_at) VALUES (1, 'Existing ticket', 'An existing request', "
                "'it', 'high', 'resolved', 1, '2026-01-01')"
            )
        )
        command.upgrade(config, "head")
        history = connection.execute(text("SELECT * FROM ticket_status_history")).mappings().one()
        assert history["event"] == "snapshot" and history["new_status"] == "resolved"
        assert history["previous_status"] is None and history["changed_by_id"] is None
        assert history["changed_at"] > "2026-01-01"
        command.downgrade(config, "0002")
        assert "ticket_status_history" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT status FROM tickets WHERE id=1")) == "resolved"
    engine.dispose()
