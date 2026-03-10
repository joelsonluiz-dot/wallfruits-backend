"""Schemas Pydantic para gamificação."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GamificationProfileResponse(BaseModel):
    id: UUID
    profile_id: UUID
    total_points: int
    level: int
    xp: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PointTransactionResponse(BaseModel):
    id: UUID
    gamification_profile_id: UUID
    amount: int
    source: str
    reference_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BadgeResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    category: Optional[str] = None
    points_required: int

    class Config:
        from_attributes = True


class UserBadgeResponse(BaseModel):
    id: UUID
    badge: BadgeResponse
    unlocked_at: datetime

    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    profile_id: UUID
    total_points: int
    level: int
    rank: int


class AdminPointAdjustment(BaseModel):
    amount: int = Field(..., description="Pontos a adicionar (positivo) ou remover (negativo)")
    source: str = Field(default="admin_adjustment")
    description: Optional[str] = Field(None, max_length=255)
