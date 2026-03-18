from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    profile_image: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)
    role: str = Field("buyer", pattern="^(buyer|producer|supplier)$")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    profile_image: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)


class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    is_verified: bool
    rating: int
    total_reviews: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserProfile(UserResponse):
    """Perfil completo do usuário com estatísticas"""
    total_offers: int = 0
    total_sales: int = 0
    total_purchases: int = 0
    favorite_count: int = 0
    unread_messages: int = 0

    class Config:
        from_attributes = True