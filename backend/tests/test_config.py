import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_database_password_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_PASSWORD", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("password", ["", "   "])
def test_empty_database_password_is_rejected(password):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_password=password)


def test_password_is_redacted_but_available_to_database_driver():
    settings = Settings(_env_file=None, database_password="synthetic-test-value")
    assert "synthetic-test-value" not in repr(settings)
    assert settings.database_url.password == "synthetic-test-value"
