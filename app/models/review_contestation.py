"""
Modelo de contestação de avaliação de reputação.
Permite que o avaliado conteste uma review; admin revisa.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class ReviewContestation(Base):
    __tablename__ = "review_contestations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    review_id = Column(UUID(as_uuid=True), ForeignKey("reputation_reviews.id"), nullable=False, index=True)
    requester_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)

    reason = Column(String(1000), nullable=False)
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, accepted, rejected

    # Campos de auditoria admin
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(String(1000))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    review = relationship("ReputationReview", backref="contestations")
    requester_profile = relationship("Profile", foreign_keys=[requester_profile_id])
