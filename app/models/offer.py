import uuid
from sqlalchemy import Column, String, Numeric, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Offer(Base):

    __tablename__ = "offers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Relacionamento com usuário
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    product_name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100), index=True)  # frutas, verduras, etc.

    quantity = Column(Numeric(10, 2), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    unit = Column(String(50), nullable=False)  # kg, unidade, caixa, etc.

    location = Column(String(150), index=True)
    latitude = Column(Numeric(10, 8))  # Para geolocalização
    longitude = Column(Numeric(11, 8))

    # Imagens do produto
    images = Column(Text)  # JSON array de URLs

    # Status e controle
    status = Column(String(50), default="active", index=True)  # active, sold, paused, expired
    is_negotiable = Column(Boolean, default=True)
    min_order = Column(Numeric(10, 2), default=1)

    # Estatísticas
    views = Column(Integer, default=0)
    favorites_count = Column(Integer, default=0)

    # Controle de qualidade
    quality_grade = Column(String(20))  # A, B, C
    organic = Column(Boolean, default=False)
    harvest_date = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    owner = relationship("User", back_populates="offers")
    transactions = relationship("Transaction", back_populates="offer", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="offer", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="offer", cascade="all, delete-orphan")