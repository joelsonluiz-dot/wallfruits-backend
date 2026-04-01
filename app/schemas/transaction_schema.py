from pydantic import BaseModel, Field
from pydantic import field_validator, model_validator
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
    reservation_date: Optional[datetime] = None
    pricing_mode: str = Field("market", pattern="^(market|min|free)$")
    offered_unit_price: Optional[Decimal] = Field(None, gt=0)
    contact_name: Optional[str] = Field(None, max_length=120)
    contact_phone: Optional[str] = Field(None, max_length=40)
    contact_address: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = Field(None, max_length=500)
    payment_method: str = Field(..., pattern="^(cash|card|transfer)$")

    @model_validator(mode="after")
    def validate_pricing_payload(self):
        if self.pricing_mode == "free" and self.offered_unit_price is None:
            raise ValueError("Informe o preço por kg para o modo livre")
        return self


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
    reservation_date: Optional[datetime]
    notes: Optional[str]
    pricing_mode: Optional[str]
    negotiated_unit_price: Optional[Decimal]
    reservation_fee_per_kg: Optional[Decimal]
    reservation_fee_total: Optional[Decimal]
    contact_name: Optional[str]
    contact_phone: Optional[str]
    contact_address: Optional[str]

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

    @field_validator("buyer", mode="before")
    @classmethod
    def parse_buyer(cls, value):
        if value is None or isinstance(value, dict):
            return value

        return {
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
            "email": getattr(value, "email", None),
            "profile_image": getattr(value, "profile_image", None),
        }

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