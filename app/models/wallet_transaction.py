import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.domain_enums import WalletTransactionSource, WalletTransactionType
from app.database.connection import Base


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("wallet.id"), nullable=False, index=True)

    transaction_type = Column(
        String(20),
        default=WalletTransactionType.CREDIT.value,
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(12, 2), nullable=False)
    source = Column(
        String(30),
        default=WalletTransactionSource.BONUS.value,
        nullable=False,
        index=True,
    )
    reference_id = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    wallet = relationship("Wallet", back_populates="transactions")
