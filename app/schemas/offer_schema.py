from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Dict
from uuid import UUID
from decimal import Decimal
from datetime import datetime, date
import json


# Valores válidos para dropdowns
QUALITY_CLASSES = ["Primeira", "Segunda", "Casquinhou", "Polpa", "Descarte"]
CERTIFICATIONS = [
    "Orgânicos", "Global GAP", "Fair Trade", "Bonsucro",
    "RainForest Alliance", "UTZ Certified", "ISO 14001"
]
ORIGINS = ["Nacional", "Importado"]
TARGET_MARKETS = ["Interno", "Externo", "Exportação"]
MATURATION_LEVELS = ["Verde", "Maduro", "Super-maduro"]
SHELF_LIFE_OPTIONS = ["3 a 6", "3 a 9", "5 a 15"]


class OfferCreate(BaseModel):
    product_name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)

    quantity: Decimal = Field(..., gt=0)
    price: Decimal = Field(..., gt=0)
    public_price: Optional[Decimal] = Field(None, gt=0)
    private_price: Optional[Decimal] = Field(None, gt=0)
    visibility: str = Field("public", pattern="^(public|premium_only)$")
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

    # Etapa 1 — Detalhes do produto
    variety: Optional[str] = Field(None, max_length=150)
    quality_class: Optional[str] = None
    certification: Optional[str] = None
    box_weight_kg: Optional[Decimal] = Field(None, gt=0)
    price_per_kg: Optional[Decimal] = Field(None, gt=0)
    price_min_kg: Optional[Decimal] = Field(None, ge=0)
    price_avg_kg: Optional[Decimal] = Field(None, ge=0)
    price_max_kg: Optional[Decimal] = Field(None, ge=0)
    available_quantity: Optional[Decimal] = Field(None, ge=0)
    origin: Optional[str] = None
    target_market: Optional[str] = None
    maturation: Optional[str] = None
    shelf_life: Optional[str] = None
    harvest_date_actual: Optional[date] = None
    reservation_start: Optional[date] = None
    reservation_end: Optional[date] = None

    # Etapa 2 — Propriedade e anúncio
    property_name: Optional[str] = Field(None, max_length=255)
    property_address: Optional[str] = Field(None, max_length=500)
    ad_duration_days: Optional[int] = Field(None, gt=0)
    min_boxes_to_negotiate: Optional[int] = Field(None, gt=0)

    @validator('images')
    def validate_images(cls, v):
        if v and len(v) > 10:
            raise ValueError('Máximo de 10 imagens por oferta')
        return v

    @validator('quality_class')
    def validate_quality_class(cls, v):
        if v and v not in QUALITY_CLASSES:
            raise ValueError(f'Qualidade deve ser uma de: {", ".join(QUALITY_CLASSES)}')
        return v

    @validator('certification')
    def validate_certification(cls, v):
        if v and v not in CERTIFICATIONS:
            raise ValueError(f'Certificação deve ser uma de: {", ".join(CERTIFICATIONS)}')
        return v

    @validator('origin')
    def validate_origin(cls, v):
        if v and v not in ORIGINS:
            raise ValueError(f'Origem deve ser uma de: {", ".join(ORIGINS)}')
        return v

    @validator('target_market')
    def validate_target_market(cls, v):
        if v and v not in TARGET_MARKETS:
            raise ValueError(f'Mercado deve ser um de: {", ".join(TARGET_MARKETS)}')
        return v

    @validator('maturation')
    def validate_maturation(cls, v):
        if v and v not in MATURATION_LEVELS:
            raise ValueError(f'Maturação deve ser uma de: {", ".join(MATURATION_LEVELS)}')
        return v

    @validator('shelf_life')
    def validate_shelf_life(cls, v):
        if v and v not in SHELF_LIFE_OPTIONS:
            raise ValueError(f'Prazo de validade deve ser um de: {", ".join(SHELF_LIFE_OPTIONS)}')
        return v

    @validator('reservation_end')
    def validate_reservation_range(cls, v, values):
        if v and values.get('reservation_start') and v < values['reservation_start']:
            raise ValueError('Data final da reserva deve ser posterior à data inicial')
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

    status: Optional[str] = Field(None, pattern="^(active|sold|paused|expired|closed|suspended)$")
    public_price: Optional[Decimal] = Field(None, gt=0)
    private_price: Optional[Decimal] = Field(None, gt=0)
    visibility: Optional[str] = Field(None, pattern="^(public|premium_only)$")
    is_featured: Optional[bool] = None
    is_negotiable: Optional[bool] = None
    min_order: Optional[Decimal] = Field(None, gt=0)

    quality_grade: Optional[str] = Field(None, pattern="^(A|B|C)$")
    organic: Optional[bool] = None
    harvest_date: Optional[datetime] = None

    # Etapa 1
    variety: Optional[str] = Field(None, max_length=150)
    quality_class: Optional[str] = None
    certification: Optional[str] = None
    box_weight_kg: Optional[Decimal] = Field(None, gt=0)
    price_per_kg: Optional[Decimal] = Field(None, gt=0)
    price_min_kg: Optional[Decimal] = Field(None, ge=0)
    price_avg_kg: Optional[Decimal] = Field(None, ge=0)
    price_max_kg: Optional[Decimal] = Field(None, ge=0)
    available_quantity: Optional[Decimal] = Field(None, ge=0)
    origin: Optional[str] = None
    target_market: Optional[str] = None
    maturation: Optional[str] = None
    shelf_life: Optional[str] = None
    harvest_date_actual: Optional[date] = None
    reservation_start: Optional[date] = None
    reservation_end: Optional[date] = None

    # Etapa 2
    property_name: Optional[str] = Field(None, max_length=255)
    property_address: Optional[str] = Field(None, max_length=500)
    ad_duration_days: Optional[int] = Field(None, gt=0)
    min_boxes_to_negotiate: Optional[int] = Field(None, gt=0)


class OfferResponse(BaseModel):
    id: UUID
    user_id: int

    product_name: str
    description: Optional[str]
    category: Optional[str]

    quantity: Decimal
    price: Decimal
    public_price: Optional[Decimal]
    private_price: Optional[Decimal]
    visibility: str
    unit: str

    location: Optional[str] = None
    latitude: Optional[Decimal]
    longitude: Optional[Decimal]

    images: Optional[List[str]]

    status: str
    is_negotiable: bool
    min_order: Decimal

    quality_grade: Optional[str]
    organic: bool
    harvest_date: Optional[datetime]

    # Novos campos
    variety: Optional[str] = None
    quality_class: Optional[str] = None
    certification: Optional[str] = None
    box_weight_kg: Optional[Decimal] = None
    price_per_kg: Optional[Decimal] = None
    price_min_kg: Optional[Decimal] = None
    price_avg_kg: Optional[Decimal] = None
    price_max_kg: Optional[Decimal] = None
    available_quantity: Optional[Decimal] = None
    origin: Optional[str] = None
    target_market: Optional[str] = None
    maturation: Optional[str] = None
    shelf_life: Optional[str] = None
    harvest_date_actual: Optional[date] = None
    reservation_start: Optional[date] = None
    reservation_end: Optional[date] = None
    property_name: Optional[str] = None
    property_address: Optional[str] = None
    ad_duration_days: Optional[int] = None
    min_boxes_to_negotiate: Optional[int] = None
    platform_fee: Optional[Decimal] = None

    views: Optional[int] = 0
    favorites_count: Optional[int] = 0
    owner_profile_id: Optional[UUID] = None
    is_featured: bool = False

    created_at: datetime
    updated_at: Optional[datetime]

    # Dados do proprietário (opcional)
    owner: Optional[Dict] = None
    owner_data: Optional[Dict] = None
    is_favorited: Optional[bool] = False
    contact_locked: bool = False
    private_address_locked: bool = False
    restriction_message: Optional[str] = None

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

    @field_validator("owner", mode="before")
    @classmethod
    def parse_owner(cls, value):
        if value is None:
            return None
        if isinstance(value, dict):
            value = dict(value)
            value["email"] = None
            value["location"] = None
            return value

        # Compatibilidade quando SQLAlchemy retorna a relação owner como objeto ORM.
        return {
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
            "email": None,
            "profile_image": getattr(value, "profile_image", None),
            "rating": getattr(value, "rating", None),
            "total_reviews": getattr(value, "total_reviews", None),
            "location": None,
            "is_verified": getattr(value, "is_verified", None),
        }


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


