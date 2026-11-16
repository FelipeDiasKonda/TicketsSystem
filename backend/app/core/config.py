from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str
    database_host: str
    database_port: int = Field(ge=1, le=65535)
    database_name: str
    database_user: str
    database_password: SecretStr
    cors_origins: list[str] = Field(min_length=1)
    session_cookie_name: str
    session_hours: int = Field(ge=1, le=168)
    cookie_secure: bool
    seed_password: SecretStr | None

    @field_validator(
        "app_name", "database_host", "database_name", "database_user", "session_cookie_name"
    )
    @classmethod
    def require_nonempty_setting(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Configuration value must not be empty")
        return value.strip()

    @field_validator("cors_origins")
    @classmethod
    def require_nonempty_origins(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("CORS origins must not be empty")
        return values

    @field_validator("seed_password", mode="before")
    @classmethod
    def allow_disabled_seed(cls, value):
        # The ENV key is required; an empty value explicitly disables seed credentials.
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("database_password", mode="before")
    @classmethod
    def require_database_password(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("DATABASE_PASSWORD must not be empty")
        return value

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
