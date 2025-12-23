"""
Authentication routes for user login, registration, and token management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.auth.database import get_db, init_db
from app.auth.models import User, UserConfig
from app.auth.jwt_handler import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()


# Pydantic schemas
class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime
    is_active: bool


# System settings (in-memory, should be persisted)
class SystemSettings:
    allow_registration: bool = True
    is_initialized: bool = False

settings = SystemSettings()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dependency to get current authenticated user."""
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role."""
    if not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


@router.get("/status")
def get_system_status(db: Session = Depends(get_db)):
    """Check if system is initialized (has admin user)."""
    admin_exists = db.query(User).filter(User.role == "admin").first() is not None
    return {
        "initialized": admin_exists,
        "allow_registration": settings.allow_registration
    }


@router.post("/setup", response_model=TokenResponse)
def initial_setup(data: UserRegister, db: Session = Depends(get_db)):
    """First-time setup: create admin account."""
    # Check if admin already exists
    if db.query(User).filter(User.role == "admin").first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System already initialized"
        )
    
    # Create admin user
    admin = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        role="admin"
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    
    # Create default config
    config = UserConfig(user_id=admin.id, config_json="{}")
    db.add(config)
    db.commit()
    
    # Generate tokens
    access_token = create_access_token({"sub": admin.id})
    refresh_token = create_refresh_token({"sub": admin.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": admin.id, "username": admin.username, "role": admin.role}
    )


@router.post("/register", response_model=TokenResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if registration is allowed
    if not settings.allow_registration:
        admin_exists = db.query(User).filter(User.role == "admin").first() is not None
        if admin_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration is disabled"
            )
    
    # Check if username exists
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Create user
    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create default config
    config = UserConfig(user_id=user.id, config_json="{}")
    db.add(config)
    db.commit()
    
    # Generate tokens
    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": user.id, "username": user.username, "role": user.role}
    )


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """Login and get access token."""
    user = db.query(User).filter(User.username == data.username).first()
    
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Generate tokens
    access_token = create_access_token({"sub": user.id})
    refresh_token = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": user.id, "username": user.username, "role": user.role}
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    access_token = create_access_token({"sub": user.id})
    new_refresh_token = create_refresh_token({"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user={"id": user.id, "username": user.username, "role": user.role}
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        created_at=user.created_at,
        is_active=user.is_active
    )
