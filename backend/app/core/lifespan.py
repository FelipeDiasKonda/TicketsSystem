from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        engine.dispose()
