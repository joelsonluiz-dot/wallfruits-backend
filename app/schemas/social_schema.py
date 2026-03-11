from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProfileOfferItem(BaseModel):
    id: UUID
    product_name: str
    price: Decimal
    unit: str
    location: Optional[str]
    images: list[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PublicUserProfileResponse(BaseModel):
    id: int
    name: str
    username: str
    email: str
    role: str
    bio: Optional[str]
    location: Optional[str]
    profile_image: Optional[str]

    total_offers: int
    followers_count: int
    following_count: int
    is_following: bool

    offers: list[ProfileOfferItem]


class FollowActionResponse(BaseModel):
    success: bool
    following: bool
    followers_count: int


class NotificationActor(BaseModel):
    id: Optional[int]
    name: Optional[str]
    profile_image: Optional[str]


class NotificationResponse(BaseModel):
    id: int
    notification_type: str
    title: str
    message: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    is_read: bool
    created_at: datetime
    actor: Optional[NotificationActor] = None

    class Config:
        from_attributes = True


class ActiveAccountItem(BaseModel):
    id: int
    name: str
    username: str
    role: str
    location: Optional[str]
    profile_image: Optional[str]
