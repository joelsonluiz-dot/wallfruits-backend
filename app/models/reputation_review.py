import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class ReputationReview(Base):
    __tablename__ = "reputation_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    negotiation_id = Column(UUID(as_uuid=True), ForeignKey("negotiations.id"), nullable=False, index=True)
    reviewer_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)
    reviewed_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)

    rating = Column(Integer, nullable=False)
    comment = Column(String(1000))
    is_invalidated = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    negotiation = relationship("Negotiation")
    reviewer_profile = relationship("Profile", foreign_keys=[reviewer_profile_id])
    reviewed_profile = relationship("Profile", foreign_keys=[reviewed_profile_id])
