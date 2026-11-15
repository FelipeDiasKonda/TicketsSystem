from datetime import timedelta
from secrets import token_urlsafe

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, hash_token, verify_password
from app.models.auth import AuthSession, User, utc_now
from app.schemas.auth import RegisterRequest


class DuplicateEmailError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


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


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    valid = verify_password(password, user.password_hash if user else None)
    if not valid or user is None or not user.is_active:
        raise InvalidCredentialsError
    return user


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))


def create_session(db: Session, user: User, hours: int, previous_token: str | None) -> str:
    revoke_session(db, previous_token)
    token = token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utc_now() + timedelta(hours=hours),
        )
    )
    db.commit()
    return token


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
