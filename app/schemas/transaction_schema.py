from pydantic import BaseModel, Field
from typing import Optional, Dict
from uuid import UUID
from decimal import Decimal
from datetime import datetime


class TransactionCreate(BaseModel):
    offer_id: UUID
    quantity: Decimal = Field(..., gt=0)
    delivery_method: str = Field("pickup", pattern="^(pickup|delivery)$")
    delivery_address: Optional[str] = None
    delivery_date: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    payment_method: str = Field(..., pattern="^(cash|card|transfer)$")


class TransactionUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|confirmed|completed|cancelled|disputed)$")
    delivery_date: Optional[datetime] = None
    delivery_address: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)
    payment_status: Optional[str] = Field(None, pattern="^(pending|paid|refunded)$")
    tracking_number: Optional[str] = Field(None, max_length=100)


class TransactionResponse(BaseModel):
    id: UUID
    buyer_id: int
    offer_id: UUID

    quantity: Decimal
    unit_price: Decimal
    total_price: Decimal

    status: str
    delivery_method: str
    delivery_address: Optional[str]
    delivery_date: Optional[datetime]
    notes: Optional[str]

    payment_method: str
    payment_status: str
    tracking_number: Optional[str]
    qr_code: Optional[str]

    created_at: datetime
    updated_at: Optional[datetime]

    # Dados relacionados
    buyer: Optional[Dict] = None
    offer: Optional[Dict] = None

    class Config:
        from_attributes = True