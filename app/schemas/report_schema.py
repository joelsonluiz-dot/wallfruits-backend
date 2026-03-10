from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReportCreate(BaseModel):
    reported_profile_id: Optional[UUID] = None
    reported_offer_id: Optional[UUID] = None
    reason: str = Field(..., min_length=10, max_length=1000)

    @model_validator(mode="after")
    def validate_targets(self):
        if not self.reported_profile_id and not self.reported_offer_id:
            raise ValueError("Informe reported_profile_id ou reported_offer_id")
        return self


class ReportReviewUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|under_review|resolved|dismissed)$")
    resolution_notes: Optional[str] = Field(None, max_length=1000)


class ReportResponse(BaseModel):
    id: UUID
    reporter_profile_id: UUID
    reported_profile_id: Optional[UUID]
    reported_offer_id: Optional[UUID]
    reason: str
    status: str
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    resolution_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
