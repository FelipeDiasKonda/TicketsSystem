from datetime import timedelta
from secrets import token_urlsafe

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DuplicateEmailError, InvalidCredentialsError
from app.core.observability import logged_operation
from app.core.security import hash_password, hash_token, verify_password
from app.models.auth import AuthSession, User, utc_now
from app.schemas.auth import RegisterRequest


@logged_operation
def register_user(db: Session, data: RegisterRequest) -> User:
    email = str(data.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise DuplicateEmailError
    user = User(
        name=data.name,
        email=email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # A concurrent registration can pass the initial uniqueness check.
        db.rollback()
        if db.scalar(select(User).where(User.email == email)):
            raise DuplicateEmailError from None
        raise
    return user


@logged_operation
def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    valid = verify_password(password, user.password_hash if user else None)
    if not valid or user is None or not user.is_active:
        raise InvalidCredentialsError
    return user


@logged_operation
def revoke_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))


@logged_operation
def create_session(db: Session, user: User, hours: int, previous_token: str | None) -> str:
    token = token_urlsafe(32)
    try:
        revoke_session(db, previous_token)
        db.add(
            AuthSession(
                user_id=user.id,
                token_hash=hash_token(token),
                expires_at=utc_now() + timedelta(hours=hours),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return token


@logged_operation
def find_session_user(db: Session, token: str | None) -> User | None:
    if not token or len(token) > 256:
        return None
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(token),
            AuthSession.expires_at > utc_now(),
        )
    )
    if session and session.user.is_active:
        return session.user
    return None
