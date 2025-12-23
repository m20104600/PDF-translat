"""
File management routes for translation history.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
import os

from app.auth.database import get_db
from app.auth.models import User, TranslationHistory
from app.auth.routes import get_current_user, require_admin

router = APIRouter(prefix="/files", tags=["Files"])


class HistoryItem(BaseModel):
    id: int
    filename: str
    file_size: int
    mono_path: Optional[str]
    dual_path: Optional[str]
    created_at: str
    status: str
    user_id: int
    username: Optional[str] = None


@router.get("/history", response_model=List[HistoryItem])
def get_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get translation history for current user."""
    history = db.query(TranslationHistory).filter(
        TranslationHistory.user_id == user.id
    ).order_by(TranslationHistory.created_at.desc()).all()
    
    return [
        HistoryItem(
            id=h.id,
            filename=h.filename,
            file_size=h.file_size or 0,
            mono_path=h.mono_path,
            dual_path=h.dual_path,
            created_at=h.created_at.isoformat() if h.created_at else "",
            status=h.status,
            user_id=h.user_id
        )
        for h in history
    ]


@router.get("/history/all", response_model=List[HistoryItem])
def get_all_history(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all translation history (admin only)."""
    history = db.query(TranslationHistory).order_by(
        TranslationHistory.created_at.desc()
    ).all()
    
    # Get usernames
    users = {u.id: u.username for u in db.query(User).all()}
    
    return [
        HistoryItem(
            id=h.id,
            filename=h.filename,
            file_size=h.file_size or 0,
            mono_path=h.mono_path,
            dual_path=h.dual_path,
            created_at=h.created_at.isoformat() if h.created_at else "",
            status=h.status,
            user_id=h.user_id,
            username=users.get(h.user_id)
        )
        for h in history
    ]


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a translation record and associated files."""
    record = db.query(TranslationHistory).filter(
        TranslationHistory.id == file_id
    ).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found"
        )
    
    # Check permission: user can only delete own files, admin can delete all
    if record.user_id != user.id and not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete other user's files"
        )
    
    # Delete physical files
    for path in [record.mono_path, record.dual_path]:
        if path and Path(path).exists():
            try:
                os.remove(path)
            except Exception:
                pass  # Ignore file deletion errors
    
    # Delete record
    db.delete(record)
    db.commit()
    
    return {"message": "File deleted successfully"}


@router.delete("/user/{user_id}/all")
def delete_all_user_files(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete all files for a user (admin only)."""
    records = db.query(TranslationHistory).filter(
        TranslationHistory.user_id == user_id
    ).all()
    
    deleted_count = 0
    for record in records:
        # Delete physical files
        for path in [record.mono_path, record.dual_path]:
            if path and Path(path).exists():
                try:
                    os.remove(path)
                    deleted_count += 1
                except Exception:
                    pass
        
        db.delete(record)
    
    db.commit()
    
    return {"message": f"Deleted {len(records)} records"}


@router.get("/download/{file_id}/mono")
def download_mono(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download mono (translated only) version of a file."""
    record = db.query(TranslationHistory).filter(
        TranslationHistory.id == file_id
    ).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found"
        )
    
    # Check permission
    if record.user_id != user.id and not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if not record.mono_path or not Path(record.mono_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mono file not found"
        )
    
    from fastapi.responses import FileResponse
    return FileResponse(
        record.mono_path,
        media_type="application/pdf",
        filename=f"{Path(record.filename).stem}_mono.pdf"
    )


@router.get("/download/{file_id}/dual")
def download_dual(
    file_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download dual (bilingual) version of a file."""
    record = db.query(TranslationHistory).filter(
        TranslationHistory.id == file_id
    ).first()
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Record not found"
        )
    
    # Check permission
    if record.user_id != user.id and not user.is_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if not record.dual_path or not Path(record.dual_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dual file not found"
        )
    
    from fastapi.responses import FileResponse
    return FileResponse(
        record.dual_path,
        media_type="application/pdf",
        filename=f"{Path(record.filename).stem}_dual.pdf"
    )
