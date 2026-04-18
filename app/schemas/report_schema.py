from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportCreate(BaseModel):
    reported_profile_id: Optional[UUID] = None
    reported_offer_id: Optional[UUID] = None
    reported_post_id: Optional[int] = None
    reason: str = Field(..., min_length=10, max_length=1000)

    @model_validator(mode="after")
    def validate_targets(self):
        targets = [
            self.reported_profile_id,
            self.reported_offer_id,
            self.reported_post_id,
        ]
        if not any(targets):
            raise ValueError("Informe reported_profile_id, reported_offer_id ou reported_post_id")
        if sum(1 for target in targets if target is not None) > 1:
            raise ValueError("Informe apenas um tipo de alvo por denúncia")
        return self


class ReportReviewUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|under_review|resolved|dismissed)$")
    resolution_notes: Optional[str] = Field(None, max_length=1000)


class ReportResponse(BaseModel):
    id: UUID
    reporter_profile_id: UUID
    reported_profile_id: Optional[UUID]
    reported_offer_id: Optional[UUID]
    reported_post_id: Optional[int]
    reason: str
    status: str
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    resolution_notes: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
