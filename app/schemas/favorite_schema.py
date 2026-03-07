from pydantic import BaseModel, Field
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