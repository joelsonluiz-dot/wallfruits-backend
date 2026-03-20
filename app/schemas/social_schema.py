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


class ProfileCommunityPostItem(BaseModel):
    id: int
    content: str
    image_url: Optional[str]
    created_at: datetime
    likes_count: int
    comments_count: int
    shares_count: int


class PublicUserProfileResponse(BaseModel):
    id: int
    name: str
    username: str
    email: Optional[str]
    phone: Optional[str]
    role: str
    bio: Optional[str]
    location: Optional[str]
    profile_image: Optional[str]
    contact_locked: bool = False
    contact_lock_reason: Optional[str] = None

    total_offers: int
    followers_count: int
    following_count: int
    is_following: bool

    offers: list[ProfileOfferItem]
    community_posts: list[ProfileCommunityPostItem]


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
