from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.connection import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    supabase_user_id = Column(String(64), unique=True, index=True, nullable=True)

    # Novos campos para marketplace
    role = Column(String(50), default="buyer", nullable=False)  # buyer, producer, admin
    phone = Column(String(20))
    location = Column(String(150))
    bio = Column(Text)
    profile_image = Column(String(500))  # URL da imagem de perfil

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    rating = Column(Integer, default=0)  # Rating de 0-5
    total_reviews = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    offers = relationship("Offer", back_populates="owner", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="buyer", cascade="all, delete-orphan")
    reviews = relationship(
        "Review",
        foreign_keys="Review.reviewer_id",
        back_populates="reviewer",
        cascade="all, delete-orphan"
    )
    received_reviews = relationship(
        "Review",
        foreign_keys="Review.reviewed_user_id",
        back_populates="reviewed_user"
    )
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")