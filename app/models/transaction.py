import uuid
from sqlalchemy import Column, String, Numeric, DateTime, Integer, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Relacionamentos
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False, index=True)

    # Detalhes da transação
    quantity = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)

    # Status da transação
    status = Column(String(50), default="pending", index=True)  # pending, confirmed, completed, cancelled, disputed

    # Informações de entrega
    delivery_method = Column(String(50), default="pickup")  # pickup, delivery
    delivery_address = Column(Text)
    delivery_date = Column(DateTime(timezone=True))
    notes = Column(Text)

    # Controle de pagamento
    payment_method = Column(String(50))  # cash, card, transfer
    payment_status = Column(String(50), default="pending")  # pending, paid, refunded

    # Tracking
    tracking_number = Column(String(100))
    qr_code = Column(String(500))  # URL do QR code para verificação

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    buyer = relationship("User", back_populates="transactions")
    offer = relationship("Offer", back_populates="transactions")