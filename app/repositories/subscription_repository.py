from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.repositories.base_repository import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, db: Session):
        super().__init__(db, Subscription)

    def get_active_by_user(self, user_id: int) -> Subscription | None:
        now = datetime.now(timezone.utc)
        return (
            self.db.query(Subscription)
            .filter(Subscription.user_id == user_id, Subscription.status == "active")
            .filter((Subscription.end_date.is_(None)) | (Subscription.end_date >= now))
            .order_by(Subscription.start_date.desc())
            .first()
        )
