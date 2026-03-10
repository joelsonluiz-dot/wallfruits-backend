from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class NegotiationCreate(BaseModel):
    offer_id: UUID
    proposed_price: Decimal = Field(..., gt=0)
    quantity: Decimal = Field(..., gt=0)
    is_intermediated: bool = False
    initial_message: Optional[str] = Field(None, max_length=2000)


class NegotiationStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|countered|accepted|rejected|canceled|completed)$")


class NegotiationUpdate(BaseModel):
    proposed_price: Optional[Decimal] = Field(None, gt=0)
    quantity: Optional[Decimal] = Field(None, gt=0)
    is_intermediated: Optional[bool] = None


class NegotiationCounterOffer(BaseModel):
    proposed_price: Decimal = Field(..., gt=0)
    quantity: Optional[Decimal] = Field(None, gt=0)
    message: Optional[str] = Field(None, max_length=2000)


class NegotiationMessageCreate(BaseModel):
    message_text: str = Field(..., min_length=1, max_length=2000)


class NegotiationMessageResponse(BaseModel):
    id: UUID
    negotiation_id: UUID
    sender_profile_id: UUID
    message_text: str
    is_read: bool
    created_at: datetime
    sender_profile: Optional[dict] = None

    class Config:
        from_attributes = True

    @field_validator("sender_profile", mode="before")
    @classmethod
    def parse_sender_profile(cls, value):
        if value is None or isinstance(value, dict):
            return value

        user = getattr(value, "user", None)
        return {
            "id": str(getattr(value, "id", "")) or None,
            "profile_type": getattr(value, "profile_type", None),
            "validation_status": getattr(value, "validation_status", None),
            "user_name": getattr(user, "name", None) if user else None,
            "user_email": getattr(user, "email", None) if user else None,
        }


class NegotiationResponse(BaseModel):
    id: UUID
    offer_id: UUID
    buyer_profile_id: UUID
    seller_profile_id: UUID
    proposed_price: Decimal
    quantity: Decimal
    status: str
    is_intermediated: bool
    created_at: datetime
    updated_at: Optional[datetime]
    offer: Optional[dict] = None
    buyer_profile: Optional[dict] = None
    seller_profile: Optional[dict] = None

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
            "status": getattr(value, "status", None),
            "public_price": float(getattr(value, "public_price", 0) or 0),
            "visibility": getattr(value, "visibility", None),
        }

    @field_validator("buyer_profile", "seller_profile", mode="before")
    @classmethod
    def parse_profile(cls, value):
        if value is None or isinstance(value, dict):
            return value

        user = getattr(value, "user", None)
        return {
            "id": str(getattr(value, "id", "")) or None,
            "profile_type": getattr(value, "profile_type", None),
            "validation_status": getattr(value, "validation_status", None),
            "user_name": getattr(user, "name", None) if user else None,
            "user_email": getattr(user, "email", None) if user else None,
        }


class IntermediationRequestCreate(BaseModel):
    notes: Optional[str] = Field(None, max_length=500)


class IntermediationRequestReviewUpdate(BaseModel):
    status: str = Field(..., pattern="^(validada|rejeitada)$")
    review_notes: Optional[str] = Field(None, max_length=1000)


class IntermediationContractUpsert(BaseModel):
    file_url: str = Field(..., min_length=5, max_length=500)
    file_name: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = Field(None, max_length=1000)


class IntermediationContractResponse(BaseModel):
    id: UUID
    intermediation_request_id: UUID
    file_url: str
    file_name: Optional[str]
    notes: Optional[str]
    uploaded_by_user_id: int
    created_at: datetime
    updated_at: Optional[datetime]
    uploaded_by_user: Optional[dict] = None

    class Config:
        from_attributes = True

    @field_validator("uploaded_by_user", mode="before")
    @classmethod
    def parse_uploaded_by_user(cls, value):
        if value is None or isinstance(value, dict):
            return value

        return {
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
            "email": getattr(value, "email", None),
            "role": getattr(value, "role", None),
        }


class IntermediationContractVersionResponse(BaseModel):
    id: UUID
    contract_id: UUID
    version_number: int
    file_url: str
    file_name: Optional[str]
    notes: Optional[str]
    uploaded_by_user_id: int
    created_at: datetime
    uploaded_by_user: Optional[dict] = None

    class Config:
        from_attributes = True

    @field_validator("uploaded_by_user", mode="before")
    @classmethod
    def parse_uploaded_by_user(cls, value):
        if value is None or isinstance(value, dict):
            return value

        return {
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
            "email": getattr(value, "email", None),
            "role": getattr(value, "role", None),
        }


class IntermediationRequestResponse(BaseModel):
    id: UUID
    negotiation_id: UUID
    requester_profile_id: UUID
    status: str
    notes: Optional[str]
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    requester_profile: Optional[dict] = None
    reviewed_by_user: Optional[dict] = None
    contract: Optional[IntermediationContractResponse] = None

    class Config:
        from_attributes = True

    @field_validator("requester_profile", mode="before")
    @classmethod
    def parse_requester_profile(cls, value):
        if value is None or isinstance(value, dict):
            return value

        user = getattr(value, "user", None)
        return {
            "id": str(getattr(value, "id", "")) or None,
            "profile_type": getattr(value, "profile_type", None),
            "validation_status": getattr(value, "validation_status", None),
            "user_name": getattr(user, "name", None) if user else None,
            "user_email": getattr(user, "email", None) if user else None,
        }

    @field_validator("reviewed_by_user", mode="before")
    @classmethod
    def parse_reviewed_by_user(cls, value):
        if value is None or isinstance(value, dict):
            return value

        return {
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
            "email": getattr(value, "email", None),
            "role": getattr(value, "role", None),
        }
