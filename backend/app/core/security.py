import bcrypt
from datetime import datetime, timedelta, timezone
from uuid import UUID
import uuid

from jose import JWTError, jwt
from app.core.config import settings

BCRYPT_MAX_BYTES = 72


def _truncate_to_bcrypt_limit(plain_password: str) -> bytes:
    password_bytes = plain_password.encode("utf-8")
    truncated_bytes = password_bytes[:BCRYPT_MAX_BYTES]
    return truncated_bytes.decode("utf-8", errors="ignore").encode("utf-8")


def hash_password(plain_password: str) -> str:
    password_bytes = _truncate_to_bcrypt_limit(plain_password)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = _truncate_to_bcrypt_limit(plain_password)
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)

def create_access_token(user_id: UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def create_refresh_token(user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None