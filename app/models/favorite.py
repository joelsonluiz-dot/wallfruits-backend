import uuid
from sqlalchemy import Column, DateTime, Integer, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Relacionamentos
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True)

    # Metadata
    notes = Column(Text)  # Notas pessoais do usuário sobre o favorito

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    user = relationship("User", back_populates="favorites")
    offer = relationship("Offer", back_populates="favorites")

    # Constraints únicos
    __table_args__ = (
        {'schema': None},
    )