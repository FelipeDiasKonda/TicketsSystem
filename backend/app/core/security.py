from hashlib import sha256

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_dummy_hash = password_hasher.hash("unused-password-for-timing")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str | None) -> bool:
    try:
        matches = password_hasher.verify(stored_hash or _dummy_hash, password)
        return matches and stored_hash is not None
    except VerificationError, InvalidHashError:
        return False


def hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()
