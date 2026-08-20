import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import jwt
from starlette.concurrency import run_in_threadpool
from app.core.config import settings

_ph = PasswordHasher()


async def hash_password(password: str) -> str:
    return await run_in_threadpool(_ph.hash, password)


async def verify_password(password_hash: str, password: str) -> bool:
    try:
        return await run_in_threadpool(_ph.verify, password_hash, password)
    except VerifyMismatchError:
        return False


def create_access_token(user_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire, "type": "access"},
        settings.JWT_SECRET,
        algorithm="HS256",
    )


def create_refresh_token_value() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
