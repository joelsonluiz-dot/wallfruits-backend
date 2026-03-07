import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database.connection import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Relacionamentos
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    offer_id = Column(UUID(as_uuid=True), ForeignKey("offers.id"), index=True)  # Opcional - mensagem sobre oferta específica

    # Conteúdo
    subject = Column(String(200))
    content = Column(Text, nullable=False)

    # Status
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime(timezone=True))

    # Tipo de mensagem
    message_type = Column(String(50), default="direct")  # direct, system, offer_inquiry

    # Thread de conversa (para agrupar mensagens relacionadas)
    thread_id = Column(UUID(as_uuid=True), index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
    offer = relationship("Offer")