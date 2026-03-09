import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Relacionamentos
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    reviewed_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True)

    # Conteúdo da avaliação
    rating = Column(Integer, nullable=False)  # 1-5 estrelas
    title = Column(String(200))
    comment = Column(Text)

    # Tipo de avaliação
    review_type = Column(String(50), default="seller")  # seller, buyer, product

    # Resposta do avaliado (opcional)
    response = Column(Text)
    response_date = Column(DateTime(timezone=True))

    # Controle de qualidade
    is_verified = Column(Boolean, default=False)  # Se foi após transação real
    is_helpful = Column(Integer, default=0)  # Votos de utilidade

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviews")
    reviewed_user = relationship("User", foreign_keys=[reviewed_user_id], back_populates="received_reviews")
    offer = relationship("Offer", back_populates="reviews")
    transaction = relationship("Transaction")