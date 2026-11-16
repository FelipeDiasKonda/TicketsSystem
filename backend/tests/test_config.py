import pytest
from environment import TEST_ENV
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("variable", list(TEST_ENV))
def test_every_setting_is_required_from_environment(variable, monkeypatch):
    monkeypatch.delenv(variable, raising=False)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert any(
        item["loc"] == (variable.lower(),) and item["type"] == "missing"
        for item in error.value.errors()
    )


def test_settings_have_no_application_defaults():
    assert all(field.is_required() for field in Settings.model_fields.values())


def test_environment_values_override_example_values(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Custom API")
    monkeypatch.setenv("DATABASE_HOST", "custom-db")
    monkeypatch.setenv("DATABASE_PORT", "3307")
    monkeypatch.setenv("DATABASE_NAME", "custom_database")
    monkeypatch.setenv("DATABASE_USER", "custom_user")
    monkeypatch.setenv("CORS_ORIGINS", '["https://portal.example.com"]')
    monkeypatch.setenv("SESSION_COOKIE_NAME", "custom_session")
    monkeypatch.setenv("SESSION_HOURS", "24")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("SEED_PASSWORD", "synthetic-seed-password")
    settings = Settings(_env_file=None)
    assert settings.app_name == "Custom API"
    assert settings.database_url.host == "custom-db"
    assert settings.database_url.port == 3307
    assert settings.database_url.database == "custom_database"
    assert settings.database_url.username == "custom_user"
    assert settings.cors_origins == ["https://portal.example.com"]
    assert settings.session_cookie_name == "custom_session"
    assert settings.session_hours == 24 and settings.cookie_secure is True
    assert settings.seed_password.get_secret_value() == "synthetic-seed-password"


def test_dotenv_is_read_and_environment_has_precedence(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(f"{key}={value}" for key, value in TEST_ENV.items()), encoding="utf-8"
    )
    for key in TEST_ENV:
        monkeypatch.delenv(key, raising=False)
    assert Settings(_env_file=path).database_user == TEST_ENV["DATABASE_USER"]
    monkeypatch.setenv("DATABASE_USER", "environment_user")
    assert Settings(_env_file=path).database_user == "environment_user"


@pytest.mark.parametrize("value", ["", "   "])
def test_explicit_empty_seed_password_disables_seed(value, monkeypatch):
    monkeypatch.setenv("SEED_PASSWORD", value)
    assert Settings(_env_file=None).seed_password is None


@pytest.mark.parametrize(
    "variable,value",
    [
        ("DATABASE_PORT", "0"),
        ("DATABASE_PORT", "65536"),
        ("DATABASE_PORT", "invalid"),
        ("SESSION_HOURS", "0"),
        ("SESSION_HOURS", "169"),
        ("COOKIE_SECURE", "invalid"),
        ("APP_NAME", ""),
        ("DATABASE_HOST", " "),
        ("DATABASE_NAME", ""),
        ("DATABASE_USER", ""),
        ("SESSION_COOKIE_NAME", ""),
        ("CORS_ORIGINS", "[]"),
        ("CORS_ORIGINS", '[""]'),
        ("CORS_ORIGINS", "{}"),
    ],
)
def test_invalid_configuration_is_rejected(variable, value, monkeypatch):
    monkeypatch.setenv(variable, value)
    with pytest.raises((ValidationError, ValueError)):
        Settings(_env_file=None)


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
