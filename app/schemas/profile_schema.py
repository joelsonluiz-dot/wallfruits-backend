from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProfileUpsert(BaseModel):
    profile_type: str = Field(..., pattern="^(visitor|producer|broker|company)$")
    document_number: Optional[str] = Field(None, max_length=80)
    company_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)
    state: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=100)


class ProfileResponse(BaseModel):
    id: UUID
    user_id: int
    profile_type: str
    validation_status: str
    document_type: Optional[str]
    document_number: Optional[str]
    document_front_url: Optional[str]
    document_back_url: Optional[str]
    document_selfie_url: Optional[str]
    proof_of_address_url: Optional[str]
    company_name: Optional[str]
    phone: Optional[str]
    state: Optional[str]
    city: Optional[str]
    submitted_at: Optional[datetime]
    validated_at: Optional[datetime]
    validated_by_user_id: Optional[int]
    validation_notes: Optional[str]
    reputation_score: Decimal
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ProfileValidationUpdate(BaseModel):
    validation_status: str = Field(..., pattern="^(pending_validation|approved|rejected|suspended)$")
    validation_notes: Optional[str] = Field(None, max_length=1000)


class ProfileDocumentSubmission(BaseModel):
    document_type: str = Field(..., pattern="^(cpf|cnpj|rg|cnh|ie|outro)$")
    document_number: str = Field(..., min_length=5, max_length=80)
    document_front_url: str = Field(..., min_length=5, max_length=500)
    document_back_url: Optional[str] = Field(None, max_length=500)
    document_selfie_url: Optional[str] = Field(None, max_length=500)
    proof_of_address_url: Optional[str] = Field(None, max_length=500)


class PendingProfileValidationItem(BaseModel):
    id: UUID
    user_id: int
    user_name: str
    user_email: str
    profile_type: str
    validation_status: str
    document_type: Optional[str]
    document_number: Optional[str]
    submitted_at: Optional[datetime]
    created_at: datetime
