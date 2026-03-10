from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReputationReviewCreate(BaseModel):
    negotiation_id: UUID
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class ReputationReviewResponse(BaseModel):
    id: UUID
    negotiation_id: UUID
    reviewer_profile_id: UUID
    reviewed_profile_id: UUID
    rating: int
    comment: Optional[str]
    is_invalidated: bool = False
    created_at: datetime
    reviewer_profile: Optional[dict] = None
    reviewed_profile: Optional[dict] = None

    class Config:
        from_attributes = True

    @field_validator("reviewer_profile", "reviewed_profile", mode="before")
    @classmethod
    def parse_profile(cls, value):
        if value is None or isinstance(value, dict):
            return value

        user = getattr(value, "user", None)
        return {
            "id": str(getattr(value, "id", "")) or None,
            "profile_type": getattr(value, "profile_type", None),
            "validation_status": getattr(value, "validation_status", None),
            "reputation_score": float(getattr(value, "reputation_score", 0) or 0),
            "user_name": getattr(user, "name", None) if user else None,
            "user_email": getattr(user, "email", None) if user else None,
        }


class ReputationSummaryResponse(BaseModel):
    profile_id: UUID
    average_rating: float
    weighted_average_rating: float
    total_reviews: int
    total_negotiated_value: float
    rating_distribution: dict[int, int]
    contestations: dict[str, int]


# ── Contestação ──────────────────────────────────────────────

class ContestationCreateRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


class ContestationReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(accepted|rejected)$")
    review_notes: Optional[str] = Field(None, max_length=2000)


class ContestationResponse(BaseModel):
    id: UUID
    review_id: UUID
    requester_profile_id: UUID
    reason: str
    status: str
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
