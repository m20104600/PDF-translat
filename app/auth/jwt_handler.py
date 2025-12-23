"""
JWT token handling for authentication.
"""
import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext

# Secret key for JWT (should be set via environment variable in production)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "pdf-translator-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# Session persistence
from pathlib import Path
import json

SESSION_DIR = Path("data") / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_session(user_id: int, refresh_token: str) -> None:
    """Save user session for persistence."""
    session_file = SESSION_DIR / f"{user_id}.json"
    session_data = {
        "user_id": user_id,
        "refresh_token": refresh_token,
        "created_at": datetime.utcnow().isoformat()
    }
    with open(session_file, "w") as f:
        json.dump(session_data, f)


def load_session(user_id: int) -> Optional[str]:
    """Load user session refresh token."""
    session_file = SESSION_DIR / f"{user_id}.json"
    if not session_file.exists():
        return None
    try:
        with open(session_file, "r") as f:
            data = json.load(f)
            return data.get("refresh_token")
    except (json.JSONDecodeError, IOError):
        return None


def clear_session(user_id: int) -> None:
    """Clear user session."""
    session_file = SESSION_DIR / f"{user_id}.json"
    if session_file.exists():
        session_file.unlink()


def cleanup_expired_sessions() -> int:
    """Clean up expired session files. Returns count of removed sessions."""
    removed = 0
    for session_file in SESSION_DIR.glob("*.json"):
        try:
            with open(session_file, "r") as f:
                data = json.load(f)
            token = data.get("refresh_token")
            if token and decode_token(token) is None:
                session_file.unlink()
                removed += 1
        except (json.JSONDecodeError, IOError):
            session_file.unlink()
            removed += 1
    return removed
