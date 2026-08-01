from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    marketplace: str = "br"


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthUrlResponse(BaseModel):
    auth_url: str
    marketplace: str
    callback_url: str
    instructions: str


class AuthCallbackInput(BaseModel):
    response_url: str
    email: Optional[str] = "user@audible.com.br"
    marketplace: Optional[str] = "br"


class TokenStatusResponse(BaseModel):
    user_id: int
    email: str
    marketplace: str
    has_active_token: bool
    expires_at: Optional[datetime] = None


class ProfileResponse(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    marketplace: str
    user_id: str
    given_name: Optional[str] = None


class BookResponse(BaseModel):
    id: int
    asin: str
    title: str
    subtitle: Optional[str] = None
    authors: Optional[str] = None
    narrators: Optional[str] = None
    duration_ms: int = 0
    cover_url: Optional[str] = None
    release_date: Optional[str] = None
    download_status: str = "not_downloaded"
    download_progress: int = 0
    local_path: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookSyncStats(BaseModel):
    status: str
    added_count: int
    updated_count: int
    total_books: int
