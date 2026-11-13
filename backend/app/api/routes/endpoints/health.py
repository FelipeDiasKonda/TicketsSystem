from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.database import get_db

router = APIRouter()


@router.get("/health")
def health(request: Request):
    return {"status": "ok", "version": request.app.version}


@router.get("/health/db")
def database_health(db: Annotated[Session, Depends(get_db)]):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok", "database": "mysql"}
