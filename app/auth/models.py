"""
SQLAlchemy models for user system.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.auth.database import Base


class User(Base):
    """User account model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")  # 'admin' or 'user'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    configs = relationship("UserConfig", back_populates="user", cascade="all, delete-orphan")
    history = relationship("TranslationHistory", back_populates="user", cascade="all, delete-orphan")

    def is_admin(self) -> bool:
        return self.role == "admin"


class UserConfig(Base):
    """User configuration storage."""
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    config_json = Column(Text, default="{}")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship
    user = relationship("User", back_populates="configs")


class TranslationHistory(Base):
    """Translation history records."""
    __tablename__ = "translation_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)  # in bytes
    mono_path = Column(String(500), nullable=True)
    dual_path = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="completed")  # 'completed', 'failed', 'processing'

    # Relationship
    user = relationship("User", back_populates="history")
