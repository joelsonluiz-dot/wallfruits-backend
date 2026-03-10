import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class NegotiationMessage(Base):
    __tablename__ = "negotiation_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    negotiation_id = Column(UUID(as_uuid=True), ForeignKey("negotiations.id"), nullable=False, index=True)
    sender_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)

    message_text = Column(String(2000), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    negotiation = relationship("Negotiation", back_populates="messages")
    sender_profile = relationship("Profile")
