"""
Modelo de transação de pontos de gamificação.
Registro auditável de cada ganho/gasto de pontos.
"""
import uuid

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    gamification_profile_id = Column(UUID(as_uuid=True), ForeignKey("gamification_profiles.id"), nullable=False, index=True)

    amount = Column(Integer, nullable=False)  # positivo = ganho, negativo = gasto
    source = Column(String(50), nullable=False, index=True)  # enum PointSource
    reference_id = Column(String(120))  # ID da entidade originadora (negociação, avaliação, etc.)
    description = Column(String(255))

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    gamification_profile = relationship("GamificationProfile", back_populates="point_transactions")
