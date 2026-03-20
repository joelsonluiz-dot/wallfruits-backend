from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime


class MessageCreate(BaseModel):
    receiver_id: int
    offer_id: Optional[UUID] = None
    subject: Optional[str] = Field(None, max_length=200)
    content: str = Field(..., max_length=2000)
    message_type: str = Field("direct", pattern="^(direct|system|offer_inquiry)$")
    thread_id: Optional[UUID] = None


class MessageResponse(BaseModel):
    id: UUID
    sender_id: int
    receiver_id: int
    offer_id: Optional[UUID]

    subject: Optional[str]
    content: str
    message_type: str

    is_read: bool
    read_at: Optional[datetime]
    thread_id: Optional[UUID]

    created_at: datetime

    # Dados relacionados
    sender: Optional[Dict] = None
    receiver: Optional[Dict] = None
    offer: Optional[Dict] = None

    class Config:
        from_attributes = True

    @field_validator("sender", mode="before")
    @classmethod
    def parse_sender(cls, value):
        if value is None or isinstance(value, dict):
            return value
        return {
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
            "email": getattr(value, "email", None),
            "profile_image": getattr(value, "profile_image", None),
        }

    @field_validator("receiver", mode="before")
    @classmethod
    def parse_receiver(cls, value):
        if value is None or isinstance(value, dict):
            return value
        return {
            "id": getattr(value, "id", None),
            "name": getattr(value, "name", None),
            "email": getattr(value, "email", None),
            "profile_image": getattr(value, "profile_image", None),
        }

    @field_validator("offer", mode="before")
    @classmethod
    def parse_offer(cls, value):
        if value is None or isinstance(value, dict):
            return value
        return {
            "id": str(getattr(value, "id", "")) or None,
            "product_name": getattr(value, "product_name", None),
            "price": float(getattr(value, "price", 0) or 0),
            "status": getattr(value, "status", None),
        }


class ConversationResponse(BaseModel):
    thread_id: UUID
    other_user: Dict
    last_message: MessageResponse
    unread_count: int
    total_messages: int
    updated_at: datetime