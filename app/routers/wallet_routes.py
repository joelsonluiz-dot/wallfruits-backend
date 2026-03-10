from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.models.wallet_transaction import WalletTransaction
from app.schemas.wallet_schema import (
    WalletManualAdjustment,
    WalletResponse,
    WalletTransactionResponse,
)
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/me", response_model=WalletResponse)
def get_my_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return WalletService(db).get_or_create_wallet(current_user.id)


@router.get("/me/transactions", response_model=list[WalletTransactionResponse])
def get_my_wallet_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wallet = WalletService(db).get_or_create_wallet(current_user.id)
    return (
        db.query(WalletTransaction)
        .filter(WalletTransaction.wallet_id == wallet.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(100)
        .all()
    )


@router.post("/me/adjust", response_model=WalletTransactionResponse)
def adjust_my_wallet_for_testing(
    payload: WalletManualAdjustment,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas admin pode ajustar wallet manualmente",
        )

    service = WalletService(db)
    try:
        return service.apply_transaction(
            user_id=current_user.id,
            transaction_type=payload.transaction_type,
            amount=Decimal(payload.amount),
            source=payload.source,
            reference_id=payload.reference_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
