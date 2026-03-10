import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.domain_enums import IntermediationStatus
from app.database.connection import Base


class IntermediationRequest(Base):
    __tablename__ = "intermediation_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    negotiation_id = Column(UUID(as_uuid=True), ForeignKey("negotiations.id"), nullable=False, index=True)
    requester_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)

    status = Column(
        String(20),
        default=IntermediationStatus.EM_VALIDACAO.value,
        nullable=False,
        index=True,
    )
    notes = Column(String(500))
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True))
    review_notes = Column(String(1000))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    negotiation = relationship("Negotiation")
    requester_profile = relationship("Profile")
    reviewed_by_user = relationship("User")
    contract = relationship(
        "IntermediationContract",
        back_populates="intermediation_request",
        uselist=False,
        cascade="all, delete-orphan",
    )
