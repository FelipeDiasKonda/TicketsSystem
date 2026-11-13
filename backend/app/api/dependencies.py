from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.auth import User, UserRole
from app.services.auth import find_session_user

Database = Annotated[Session, Depends(get_db)]


def require_csrf(
    request: Request,
    csrf_protection: Annotated[str | None, Header(alias="X-CSRF-Protection")] = None,
) -> None:
    # A non-simple header forces a CORS preflight for cross-origin browser requests.
    origin = request.headers.get("origin")
    if csrf_protection != "1" or (
        origin is not None and origin not in get_settings().cors_origins
    ):
        raise HTTPException(status_code=403, detail="Request not authorized.")


def get_current_user(request: Request, db: Database) -> User:
    user = find_session_user(db, request.cookies.get(get_settings().session_cookie_name))
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_support(user: CurrentUser) -> User:
    if user.role != UserRole.SUPPORT:
        raise HTTPException(status_code=403, detail="Access restricted to support staff.")
    return user
