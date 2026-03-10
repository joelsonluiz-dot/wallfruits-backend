"""
Modelos de badges (conquistas) e vínculo com perfil.
"""
import uuid

from sqlalchemy import Column, DateTime, Integer, String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class Badge(Base):
    """Definição de um badge (pré-cadastrado pelo sistema/admin)."""
    __tablename__ = "badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # ex: "first_sale", "negotiator_10"
    name = Column(String(120), nullable=False)
    description = Column(String(500))
    icon_url = Column(String(500))
    category = Column(String(50), index=True)  # ex: "trading", "community", "milestone"
    points_required = Column(Integer, default=0)  # 0 = desbloqueado por evento, não por pontos
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserBadge(Base):
    """Badge desbloqueado por um perfil."""
    __tablename__ = "user_badges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    gamification_profile_id = Column(UUID(as_uuid=True), ForeignKey("gamification_profiles.id"), nullable=False, index=True)
    badge_id = Column(UUID(as_uuid=True), ForeignKey("badges.id"), nullable=False, index=True)
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    gamification_profile = relationship("GamificationProfile", back_populates="badges")
    badge = relationship("Badge")

    __table_args__ = (
        UniqueConstraint("gamification_profile_id", "badge_id", name="uq_user_badge"),
    )
