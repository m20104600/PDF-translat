"""
Admin routes for user management and system settings.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import os

from app.auth.database import get_db
from app.auth.models import User, TranslationHistory
from app.auth.routes import require_admin, settings as system_settings

router = APIRouter(prefix="/admin", tags=["Admin"])


class UserStats(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    file_count: int
    total_size: int  # bytes
    created_at: str


class SystemStats(BaseModel):
    total_users: int
    total_files: int
    total_size: int  # bytes
    total_size_mb: float


class AdminSettings(BaseModel):
    allow_registration: Optional[bool] = None


@router.get("/users", response_model=List[UserStats])
def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all users with storage statistics."""
    users = db.query(User).all()
    result = []
    
    for user in users:
        # Get file stats
        history = db.query(TranslationHistory).filter(
            TranslationHistory.user_id == user.id
        ).all()
        
        file_count = len(history)
        total_size = sum(h.file_size or 0 for h in history)
        
        result.append(UserStats(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            file_count=file_count,
            total_size=total_size,
            created_at=user.created_at.isoformat() if user.created_at else ""
        ))
    
    return result


@router.get("/stats", response_model=SystemStats)
def get_system_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system-wide statistics."""
    total_users = db.query(User).count()
    total_files = db.query(TranslationHistory).count()
    
    # Calculate total size
    size_result = db.query(func.sum(TranslationHistory.file_size)).scalar()
    total_size = size_result or 0
    
    return SystemStats(
        total_users=total_users,
        total_files=total_files,
        total_size=total_size,
        total_size_mb=round(total_size / (1024 * 1024), 2)
    )


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a user and all their data."""
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete user data directory
    user_data_dir = Path("data") / "webui" / str(user_id)
    if user_data_dir.exists():
        import shutil
        shutil.rmtree(user_data_dir)
    
    # Delete user (cascades to configs and history)
    db.delete(user)
    db.commit()
    
    return {"message": f"User {user.username} deleted"}


@router.patch("/settings")
def update_settings(
    data: AdminSettings,
    admin: User = Depends(require_admin)
):
    """Update system settings."""
    if data.allow_registration is not None:
        system_settings.allow_registration = data.allow_registration
    
    return {
        "allow_registration": system_settings.allow_registration
    }


@router.patch("/users/{user_id}/toggle")
def toggle_user_status(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Enable/disable a user account."""
    if admin.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify yourself"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = not user.is_active
    db.commit()
    
    return {"id": user.id, "is_active": user.is_active}
