from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    slug: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    slug: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    parent_id: Optional[int] = None
    icon: Optional[str] = None
    color: Optional[str] = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    is_active: Optional[bool] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    parent_id: Optional[int]
    icon: Optional[str]
    color: Optional[str]
    is_active: bool
    offer_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    # Dados relacionados
    parent: Optional[Dict] = None
    subcategories: Optional[List[Dict]] = None

    class Config:
        from_attributes = True