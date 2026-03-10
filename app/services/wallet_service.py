from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.domain_enums import WalletTransactionType
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.repositories.wallet_repository import WalletRepository


class WalletService:
    def __init__(self, db: Session):
        self.db = db
        self.wallet_repo = WalletRepository(db)

    def get_or_create_wallet(self, user_id: int) -> Wallet:
        wallet = self.wallet_repo.by_user_id(user_id)
        if wallet:
            return wallet

        wallet = Wallet(user_id=user_id)
        self.wallet_repo.add(wallet)
        self.db.commit()
        self.db.refresh(wallet)
        return wallet

    def apply_transaction(
        self,
        *,
        user_id: int,
        transaction_type: str,
        amount: Decimal,
        source: str,
        reference_id: str | None = None,
    ) -> WalletTransaction:
        if amount <= 0:
            raise ValueError("Valor da transacao deve ser maior que zero")

        wallet = self.get_or_create_wallet(user_id)
        current = Decimal(wallet.balance or 0)

        if transaction_type == WalletTransactionType.CREDIT.value:
            new_balance = current + amount
        elif transaction_type == WalletTransactionType.DEBIT.value:
            if current < amount:
                raise ValueError("Saldo insuficiente na wallet")
            new_balance = current - amount
        else:
            raise ValueError("Tipo de transacao invalido")

        wallet._allow_balance_update = True
        wallet.balance = new_balance

        tx = WalletTransaction(
            wallet_id=wallet.id,
            transaction_type=transaction_type,
            amount=amount,
            source=source,
            reference_id=reference_id,
        )

        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)

        wallet._allow_balance_update = False
        return tx
