import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class IntermediationContractVersion(Base):
    __tablename__ = "intermediation_contract_versions"
    __table_args__ = (
        UniqueConstraint("contract_id", "version_number", name="uq_contract_version_number"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    contract_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intermediation_contracts.id"),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    file_url = Column(String(500), nullable=False)
    file_name = Column(String(255))
    notes = Column(String(1000))

    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    contract = relationship("IntermediationContract", back_populates="versions")
    uploaded_by_user = relationship("User")