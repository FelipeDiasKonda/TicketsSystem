"""Explicit settings for isolated tests and optional browser smoke scripts."""

import os
from secrets import token_hex

TEST_ENV = {
    "APP_NAME": "Tickets System API",
    "DATABASE_HOST": "127.0.0.1",
    "DATABASE_PORT": "3306",
    "DATABASE_NAME": "tickets_test",
    "DATABASE_USER": "test_user",
    "DATABASE_PASSWORD": token_hex(32),
    "CORS_ORIGINS": '["http://localhost:5173"]',
    "SESSION_COOKIE_NAME": "tickets_session",
    "SESSION_HOURS": "8",
    "COOKIE_SECURE": "false",
    "SEED_PASSWORD": "",
}


def configure_test_environment() -> None:
    os.environ.update(TEST_ENV)
