import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class IntermediationContract(Base):
    __tablename__ = "intermediation_contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    intermediation_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intermediation_requests.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255))
    notes = Column(String(1000))

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    intermediation_request = relationship("IntermediationRequest", back_populates="contract")
    uploaded_by_user = relationship("User")
    versions = relationship(
        "IntermediationContractVersion",
        back_populates="contract",
        cascade="all, delete-orphan",
        order_by="IntermediationContractVersion.version_number.desc()",
    )
