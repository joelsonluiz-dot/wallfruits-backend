import uuid
from decimal import Decimal

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, event, inspect
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.connection import Base


class Wallet(Base):
    __tablename__ = "wallet"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    balance = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="wallet")
    transactions = relationship(
        "WalletTransaction",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )


@event.listens_for(Wallet, "before_update")
def prevent_direct_balance_update(mapper, connection, target):
    del mapper, connection  # assinatura exigida
    history = inspect(target).attrs.balance.history
    if history.has_changes() and not getattr(target, "_allow_balance_update", False):
        raise ValueError("Saldo da wallet nao pode ser alterado diretamente")
