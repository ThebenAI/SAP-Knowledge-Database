from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
MIN_PASSWORD_LENGTH = 8
MAX_BCRYPT_PASSWORD_BYTES = 72
PASSWORD_LENGTH_ERROR_MESSAGE = (
    f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_BCRYPT_PASSWORD_BYTES} characters."
)


def validate_password_for_bcrypt(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(PASSWORD_LENGTH_ERROR_MESSAGE)
    if len(password) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError(PASSWORD_LENGTH_ERROR_MESSAGE)
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError(PASSWORD_LENGTH_ERROR_MESSAGE)


def hash_password(password: str) -> str:
    validate_password_for_bcrypt(password)
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(subject: str, expires_minutes: int = 60 * 8) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])
    except JWTError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        return None
    return subject
