from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.dependencies import CurrentUser, Database, require_csrf
from app.core.config import get_settings
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services.auth import (
    DuplicateEmailError,
    InvalidCredentialsError,
    authenticate_user,
    create_session,
    register_user,
    revoke_session,
)

router = APIRouter(prefix="/auth")
write_dependencies = [Depends(require_csrf)]


def set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api",
    )
    response.headers["Cache-Control"] = "no-store"


@router.post(
    "/register", response_model=UserResponse, status_code=201, dependencies=write_dependencies
)
def register(data: RegisterRequest, request: Request, response: Response, db: Database):
    try:
        user = register_user(db, data)
    except DuplicateEmailError:
        raise HTTPException(status_code=409, detail="Este e-mail já está cadastrado.") from None
    settings = get_settings()
    token = create_session(
        db,
        user,
        settings.session_hours,
        request.cookies.get(settings.session_cookie_name),
    )
    set_session_cookie(response, token)
    return user


@router.post("/login", response_model=UserResponse, dependencies=write_dependencies)
def login(data: LoginRequest, request: Request, response: Response, db: Database):
    try:
        user = authenticate_user(db, str(data.email), data.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.") from None
    settings = get_settings()
    token = create_session(
        db,
        user,
        settings.session_hours,
        request.cookies.get(settings.session_cookie_name),
    )
    set_session_cookie(response, token)
    return user


@router.get("/me", response_model=UserResponse)
def me(response: Response, user: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=204, dependencies=write_dependencies)
def logout(request: Request, db: Database):
    settings = get_settings()
    revoke_session(db, request.cookies.get(settings.session_cookie_name))
    db.commit()
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        settings.session_cookie_name,
        path="/api",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )
    return response
