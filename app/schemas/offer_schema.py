from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Dict
from uuid import UUID
from decimal import Decimal
from datetime import datetime
import json


class OfferCreate(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)

    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)

    location: str = Field(..., min_length=2, max_length=150)
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)

    images: Optional[List[str]] = Field(default_factory=list)

    is_negotiable: bool = True
    min_order: Decimal = Field(1, gt=0)

    quality_grade: Optional[str] = Field(None, pattern="^(A|B|C)$")
    organic: bool = False
    harvest_date: Optional[datetime] = None

    @validator('images')
    def validate_images(cls, v):
        if v and len(v) > 10:
            raise ValueError('Máximo de 10 imagens por oferta')
        return v


class OfferUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)

    quantity: Optional[Decimal] = Field(None, gt=0)
    price: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, min_length=1, max_length=50)

    location: Optional[str] = Field(None, min_length=2, max_length=150)
    latitude: Optional[Decimal] = Field(None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(None, ge=-180, le=180)

    images: Optional[List[str]] = None

    status: Optional[str] = Field(None, pattern="^(active|sold|paused|expired)$")
    is_negotiable: Optional[bool] = None
    min_order: Optional[Decimal] = Field(None, gt=0)

    quality_grade: Optional[str] = Field(None, pattern="^(A|B|C)$")
    organic: Optional[bool] = None
    harvest_date: Optional[datetime] = None


class OfferResponse(BaseModel):
    id: UUID
    user_id: int

    product_name: str
    description: Optional[str]
    category: Optional[str]

    quantity: Decimal
    price: Decimal
    unit: str

    location: str
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]

    images: Optional[List[str]]

    status: str
    is_negotiable: bool
    min_order: Decimal

    quality_grade: Optional[str]
    organic: bool
    harvest_date: Optional[datetime]

    views: int
    favorites_count: int

    created_at: datetime
    updated_at: Optional[datetime]

    # Dados do proprietário (opcional)
    owner: Optional[Dict] = None
    owner_data: Optional[Dict] = None
    is_favorited: Optional[bool] = False

    class Config:
        from_attributes = True

    @field_validator("images", mode="before")
    @classmethod
    def parse_images(cls, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return []


class PaginatedOfferResponse(BaseModel):
    total: int
    skip: int
    limit: int
    offers: List[OfferResponse]
    stats: Dict

    class Config:
        from_attributes = True


class OfferSearchFilters(BaseModel):
    search: Optional[str] = None
    category: Optional[str] = None
    location: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    organic: Optional[bool] = None
    quality_grade: Optional[str] = None
    radius: Optional[float] = None  # Raio em km para busca geográfica
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    class Config:
        from_attributes = True


