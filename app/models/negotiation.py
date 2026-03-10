import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.domain_enums import NegotiationStatus
from app.database.connection import Base


class Negotiation(Base):
    __tablename__ = "negotiations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True)

    buyer_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)
    seller_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)

    proposed_price = Column(Numeric(12, 2), nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)

    status = Column(String(20), default=NegotiationStatus.OPEN.value, nullable=False, index=True)
    is_intermediated = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    offer = relationship("Offer")
    buyer_profile = relationship("Profile", foreign_keys=[buyer_profile_id], back_populates="buyer_negotiations")
    seller_profile = relationship("Profile", foreign_keys=[seller_profile_id], back_populates="seller_negotiations")
    messages = relationship("NegotiationMessage", back_populates="negotiation", cascade="all, delete-orphan")
