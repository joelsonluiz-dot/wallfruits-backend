from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime


class FavoriteCreate(BaseModel):
    offer_id: UUID
    notes: Optional[str] = Field(None, max_length=500)


class FavoriteUpdate(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


class FavoriteResponse(BaseModel):
    id: UUID
    user_id: int
    offer_id: UUID
    notes: Optional[str]
    created_at: datetime

    # Dados da oferta (opcional)
    offer: Optional[Dict] = None

    class Config:
        from_attributes = True

    @field_validator("offer", mode="before")
    @classmethod
    def parse_offer(cls, value):
        if value is None or isinstance(value, dict):
            return value
        return {
            "id": str(getattr(value, "id", "")) or None,
            "product_name": getattr(value, "product_name", None),
            "price": float(getattr(value, "price", 0) or 0),
            "status": getattr(value, "status", None),
        }