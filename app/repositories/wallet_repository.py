from sqlalchemy.orm import Session

from app.models.wallet import Wallet
from app.repositories.base_repository import BaseRepository


class WalletRepository(BaseRepository[Wallet]):
    def __init__(self, db: Session):
        super().__init__(db, Wallet)

    def by_user_id(self, user_id: int) -> Wallet | None:
        return self.db.query(Wallet).filter(Wallet.user_id == user_id).first()
