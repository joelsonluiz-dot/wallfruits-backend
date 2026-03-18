from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class CommunityAuthor(BaseModel):
    id: int
    name: str
    role: str
    profile_image: Optional[str] = None


class CommunityCommentCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        content = (value or "").strip()
        if len(content) < 1:
            raise ValueError("Comentário não pode estar vazio")
        if len(content) > 1200:
            raise ValueError("Comentário excede 1200 caracteres")
        return content


class CommunityCommentResponse(BaseModel):
    id: int
    post_id: int
    content: str
    created_at: datetime
    author: CommunityAuthor


class CommunityPostCreate(BaseModel):
    content: Optional[str] = ""
    image_url: Optional[str] = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: Optional[str]) -> str:
        text = (value or "").strip()
        if len(text) > 5000:
            raise ValueError("Post excede 5000 caracteres")
        return text

    @field_validator("image_url")
    @classmethod
    def normalize_image(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        img = value.strip()
        return img or None


class CommunityPostResponse(BaseModel):
    id: int
    content: str
    image_url: Optional[str] = None
    created_at: datetime
    author: CommunityAuthor
    likes_count: int
    comments_count: int
    shares_count: int
    liked_by_me: bool = False

    model_config = ConfigDict(from_attributes=True)


class CommunityLikeToggleResponse(BaseModel):
    success: bool
    liked: bool
    likes_count: int


class CommunityShareResponse(BaseModel):
    success: bool
    shares_count: int
    share_url: str


class CommunityPostListResponse(BaseModel):
    posts: list[CommunityPostResponse]
    total: int


class CommunityModerationActionResponse(BaseModel):
    success: bool
    action: str
    target_type: str
    target_id: int


class CommunityBlockUserRequest(BaseModel):
    reason: Optional[str] = None

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if len(text) > 500:
            raise ValueError("Motivo excede 500 caracteres")
        return text
