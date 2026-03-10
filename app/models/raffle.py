import uuid

from sqlalchemy import Column, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.domain_enums import RaffleStatus
from app.database.connection import Base


class Raffle(Base):
    __tablename__ = "raffles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False)
    description = Column(String(1200), nullable=False)
    ticket_price = Column(Numeric(12, 2), nullable=False)
    total_tickets = Column(Integer, nullable=False)
    draw_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), default=RaffleStatus.OPEN.value, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    tickets = relationship("RaffleTicket", back_populates="raffle", cascade="all, delete-orphan")
