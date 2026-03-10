from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    id: UUID
    user_id: int
    balance: Decimal
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class WalletTransactionResponse(BaseModel):
    id: UUID
    wallet_id: UUID
    transaction_type: str
    amount: Decimal
    source: str
    reference_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class WalletManualAdjustment(BaseModel):
    transaction_type: str = Field(..., pattern="^(credit|debit)$")
    amount: Decimal = Field(..., gt=0)
    source: str = Field("bonus", pattern="^(negotiation|bonus|refund|raffle)$")
    reference_id: Optional[str] = Field(None, max_length=80)
