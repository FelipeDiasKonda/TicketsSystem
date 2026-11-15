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

    app_name: str = "Tickets System API"
    database_host: str = "127.0.0.1"
    database_port: int = 3306
    database_name: str = "tickets_system"
    database_user: str = "tickets_app"
    database_password: SecretStr
    cors_origins: list[str] = ["http://localhost:5173"]
    session_cookie_name: str = "tickets_session"
    session_hours: int = Field(default=8, ge=1, le=168)
    cookie_secure: bool = False
    seed_password: SecretStr | None = None

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
