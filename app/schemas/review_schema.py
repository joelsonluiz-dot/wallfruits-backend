from pydantic import BaseModel, Field
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime


class ReviewCreate(BaseModel):
    offer_id: UUID
    transaction_id: UUID
    reviewed_user_id: int
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    comment: str = Field(..., max_length=1000)
    review_type: str = Field("seller", pattern="^(seller|buyer|product)$")


class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    comment: Optional[str] = Field(None, max_length=1000)


class ReviewResponse(BaseModel):
    id: UUID
    reviewer_id: int
    reviewed_user_id: int
    offer_id: UUID
    transaction_id: UUID

    rating: int
    title: Optional[str]
    comment: str
    review_type: str

    response: Optional[str]
    response_date: Optional[datetime]

    is_verified: bool
    is_helpful: int

    created_at: datetime
    updated_at: Optional[datetime]

    # Dados relacionados
    reviewer: Optional[Dict] = None
    reviewed_user: Optional[Dict] = None
    offer: Optional[Dict] = None

    class Config:
        from_attributes = True


class ReviewStats(BaseModel):
    average_rating: float
    total_reviews: int
    rating_distribution: Dict[int, int]  # {1: count, 2: count, ...}
    verified_reviews: int