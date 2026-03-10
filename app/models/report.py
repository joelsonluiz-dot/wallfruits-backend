import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.domain_enums import ReportStatus
from app.database.connection import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    reporter_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=False, index=True)

    reported_profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True, index=True)
    reported_offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True)

    reason = Column(String(1000), nullable=False)
    status = Column(String(20), default=ReportStatus.PENDING.value, nullable=False, index=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True))
    resolution_notes = Column(String(1000))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    reporter_profile = relationship("Profile", foreign_keys=[reporter_profile_id])
    reported_profile = relationship("Profile", foreign_keys=[reported_profile_id])
    reviewed_by_user = relationship("User")
