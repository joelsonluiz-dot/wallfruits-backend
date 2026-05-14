import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class ServiceRequest(Base):
    __tablename__ = "service_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    service_id = Column(Integer, ForeignKey("services.id"), nullable=False, index=True)
    requester_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    provider_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    status = Column(String(40), default="pending", index=True)
    priority = Column(String(30), default="normal", index=True)

    requested_date = Column(DateTime(timezone=True))
    budget = Column(Numeric(12, 2))
    location = Column(String(180))
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    service = relationship("Service", backref="service_requests")
    requester = relationship("User", foreign_keys=[requester_user_id], backref="service_requests")
    provider = relationship("User", foreign_keys=[provider_user_id], backref="service_received_requests")