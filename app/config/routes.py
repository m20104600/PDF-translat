"""
User configuration management routes.
Handles per-user settings, translation service configs, and import/export.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
from pathlib import Path

from app.auth.database import get_db
from app.auth.models import User, UserConfig
from app.auth.routes import get_current_user

router = APIRouter(prefix="/config", tags=["Configuration"])


class TranslationServiceConfig(BaseModel):
    """Translation service configuration."""
    service_type: str = "siliconflow_free"  # Default
    # SiliconFlow Free (default)
    siliconflow_api_key: Optional[str] = None
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = "gpt-4o-mini"
    openai_base_url: Optional[str] = None
    # Azure
    azure_api_key: Optional[str] = None
    azure_endpoint: Optional[str] = None
    azure_region: Optional[str] = None
    # Gemini
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = "gemini-pro"


class PDFOutputConfig(BaseModel):
    """PDF output options."""
    output_mode: str = "dual"  # 'mono', 'dual', 'both'
    watermark_enabled: bool = False
    watermark_text: Optional[str] = None
    alternate_pages: bool = False


class AdvancedConfig(BaseModel):
    """Advanced settings."""
    rate_limit: int = 10  # requests per minute
    enable_terminology: bool = False
    babeldoc_threads: int = 4


class UserSettings(BaseModel):
    """Complete user settings."""
    translation_service: TranslationServiceConfig = TranslationServiceConfig()
    pdf_output: PDFOutputConfig = PDFOutputConfig()
    advanced: AdvancedConfig = AdvancedConfig()


@router.get("/", response_model=UserSettings)
def get_user_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's configuration."""
    config = db.query(UserConfig).filter(UserConfig.user_id == user.id).first()
    
    if not config or not config.config_json:
        return UserSettings()
    
    try:
        data = json.loads(config.config_json)
        return UserSettings(**data)
    except (json.JSONDecodeError, ValueError):
        return UserSettings()


@router.put("/")
def update_user_config(
    settings: UserSettings,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user configuration."""
    config = db.query(UserConfig).filter(UserConfig.user_id == user.id).first()
    
    if not config:
        config = UserConfig(user_id=user.id)
        db.add(config)
    
    config.config_json = settings.model_dump_json()
    db.commit()
    
    # Also save to file for persistence
    _save_config_to_file(user.id, settings)
    
    return {"message": "Configuration saved"}


@router.get("/export")
def export_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export user configuration as JSON."""
    config = db.query(UserConfig).filter(UserConfig.user_id == user.id).first()
    
    if not config or not config.config_json:
        data = UserSettings().model_dump()
    else:
        try:
            data = json.loads(config.config_json)
        except json.JSONDecodeError:
            data = UserSettings().model_dump()
    
    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": f"attachment; filename=pdf_translator_config_{user.username}.json"
        }
    )


class ImportConfigRequest(BaseModel):
    config_json: str


@router.post("/import")
def import_config(
    data: ImportConfigRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import configuration from JSON."""
    try:
        config_data = json.loads(data.config_json)
        settings = UserSettings(**config_data)
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid configuration format: {str(e)}"
        )
    
    config = db.query(UserConfig).filter(UserConfig.user_id == user.id).first()
    
    if not config:
        config = UserConfig(user_id=user.id)
        db.add(config)
    
    config.config_json = settings.model_dump_json()
    db.commit()
    
    _save_config_to_file(user.id, settings)
    
    return {"message": "Configuration imported successfully"}


@router.patch("/service")
def update_service_config(
    service_config: TranslationServiceConfig,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Quick update for translation service configuration."""
    config = db.query(UserConfig).filter(UserConfig.user_id == user.id).first()
    
    if not config:
        settings = UserSettings(translation_service=service_config)
        config = UserConfig(user_id=user.id, config_json=settings.model_dump_json())
        db.add(config)
    else:
        try:
            current_data = json.loads(config.config_json) if config.config_json else {}
            settings = UserSettings(**current_data)
        except (json.JSONDecodeError, ValueError):
            settings = UserSettings()
        
        settings.translation_service = service_config
        config.config_json = settings.model_dump_json()
    
    db.commit()
    _save_config_to_file(user.id, settings)
    
    return {"message": "Service configuration updated"}


def _save_config_to_file(user_id: int, settings: UserSettings):
    """Save configuration to file for persistence."""
    config_dir = Path("data") / "config" / str(user_id)
    config_dir.mkdir(parents=True, exist_ok=True)
    
    config_file = config_dir / "settings.json"
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(settings.model_dump_json(indent=2))


def _load_config_from_file(user_id: int) -> Optional[UserSettings]:
    """Load configuration from file."""
    config_file = Path("data") / "config" / str(user_id) / "settings.json"
    
    if not config_file.exists():
        return None
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return UserSettings(**data)
    except (json.JSONDecodeError, ValueError):
        return None
