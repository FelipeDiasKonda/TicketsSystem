from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Tickets System API"
    database_host: str = "127.0.0.1"
    database_port: int = 3306
    database_name: str = "tickets_system"
    database_user: str = "tickets_app"
    database_password: str = "local_dev_password"
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def database_url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
