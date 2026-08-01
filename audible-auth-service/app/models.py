from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    marketplace = Column(String(50), default="br", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    tokens = relationship("Token", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    books = relationship("Book", back_populates="user", cascade="all, delete-orphan")


class Token(Base):
    __tablename__ = "tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Encrypted fields
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    adp_token = Column(Text, nullable=True)
    device_private_key = Column(Text, nullable=True)
    website_cookies = Column(Text, nullable=True)
    device_info = Column(Text, nullable=True)
    customer_info = Column(Text, nullable=True)
    
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="tokens")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    browser_session = Column(Text, nullable=True)
    cookies = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    user = relationship("User", back_populates="sessions")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    asin = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    subtitle = Column(String(255), nullable=True)
    authors = Column(String(255), nullable=True)
    narrators = Column(String(255), nullable=True)
    duration_ms = Column(Integer, default=0)
    cover_url = Column(Text, nullable=True)
    release_date = Column(String(50), nullable=True)
    
    # Status: 'not_downloaded', 'downloading', 'downloaded', 'error'
    download_status = Column(String(50), default="not_downloaded", nullable=False)
    download_progress = Column(Integer, default=0)
    local_path = Column(Text, nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user = relationship("User", back_populates="books")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
