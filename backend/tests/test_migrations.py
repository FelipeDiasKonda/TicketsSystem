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
