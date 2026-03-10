from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.domain_enums import ProfileType
from app.models.transaction import Transaction
from app.models.user import User
from app.services.profile_service import ProfileService


class NegotiationPolicyService:
    VISITOR_MONTHLY_LIMIT = 2

    def __init__(self, db: Session):
        self.db = db
        self.profile_service = ProfileService(db)

    def enforce_monthly_limit(self, user: User) -> None:
        profile = self.profile_service.get_or_create_profile(user)

        if profile.profile_type != ProfileType.VISITOR.value:
            return

        if self.profile_service.is_premium(user.id):
            return

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        count = (
            self.db.query(func.count(Transaction.id))
            .filter(Transaction.buyer_id == user.id, Transaction.created_at >= month_start)
            .scalar()
            or 0
        )

        if count >= self.VISITOR_MONTHLY_LIMIT:
            raise ValueError(
                "Visitante atingiu o limite mensal de 2 negociacoes. "
                "Assine o plano Premium para negociacoes ilimitadas."
            )
