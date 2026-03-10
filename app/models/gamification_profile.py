"""
Modelo de perfil de gamificação — pontos, XP e nível por perfil.
Separado da wallet (financeiro).
"""
import uuid

from sqlalchemy import Column, DateTime, Integer, Numeric, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class GamificationProfile(Base):
    __tablename__ = "gamification_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), unique=True, nullable=False, index=True)

    total_points = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    xp = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    profile = relationship("Profile", backref="gamification_profile", uselist=False)
    point_transactions = relationship("PointTransaction", back_populates="gamification_profile", cascade="all, delete-orphan")
    badges = relationship("UserBadge", back_populates="gamification_profile", cascade="all, delete-orphan")
