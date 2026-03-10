import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.domain_enums import ProfileType, ValidationStatus
from app.database.connection import Base


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_profiles_user_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    profile_type = Column(String(30), default=ProfileType.VISITOR.value, nullable=False, index=True)
    validation_status = Column(
        String(30),
        default=ValidationStatus.APPROVED.value,
        nullable=False,
        index=True,
    )

    document_number = Column(String(80))
    document_type = Column(String(30))
    document_front_url = Column(String(500))
    document_back_url = Column(String(500))
    document_selfie_url = Column(String(500))
    proof_of_address_url = Column(String(500))
    company_name = Column(String(255))
    phone = Column(String(30))
    state = Column(String(50), index=True)
    city = Column(String(100), index=True)
    submitted_at = Column(DateTime(timezone=True))
    validated_at = Column(DateTime(timezone=True))
    validated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    validation_notes = Column(String(1000))
    reputation_score = Column(Numeric(10, 2), default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="profile", foreign_keys=[user_id])
    validated_by_user = relationship("User", foreign_keys=[validated_by_user_id])
    offers = relationship("Offer", back_populates="owner_profile")

    buyer_negotiations = relationship(
        "Negotiation",
        foreign_keys="Negotiation.buyer_profile_id",
        back_populates="buyer_profile",
    )
    seller_negotiations = relationship(
        "Negotiation",
        foreign_keys="Negotiation.seller_profile_id",
        back_populates="seller_profile",
    )
