"""
Security/cryptography helpers — password hashing and JWT token operations.
"""


from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from jose import JWTError, jwt
import bcrypt

from app.core.config import settings


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    # bcrypt requires bytes
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = plain.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')
    try:
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except ValueError:
        return False


# ── JWT ────────────────────────────────────────────────────────────────────────

def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    # Add a unique JWT ID (jti) for blacklisting
    payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, extra_claims: dict | None = None) -> str:
    data: dict[str, Any] = {"sub": subject, "type": "access"}
    if extra_claims:
        data.update(extra_claims)
    return _create_token(data, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject: str) -> str:
    return _create_token(
        {"sub": subject, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_verification_token(email: str) -> str:
    return _create_token(
        {"sub": email, "type": "verify"},
        timedelta(hours=24),
    )


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def get_unverified_token_data(token: str) -> dict | None:
    try:
        return jwt.get_unverified_claims(token)
    except Exception:
        return None


def create_password_reset_token(email: str, password_hash: str) -> str:
    secret = f"{settings.SECRET_KEY}:{password_hash}"
    payload = {"sub": email, "type": "reset"}
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=15)
    payload["jti"] = str(uuid.uuid4())
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)


def decode_password_reset_token(token: str, password_hash: str) -> dict | None:
    secret = f"{settings.SECRET_KEY}:{password_hash}"
    try:
        return jwt.decode(token, secret, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

