from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.negotiation import Negotiation
from app.repositories.base_repository import BaseRepository


class NegotiationRepository(BaseRepository[Negotiation]):
    def __init__(self, db: Session):
        super().__init__(db, Negotiation)

    def list_for_profile(self, *, profile_id, status: str | None, skip: int, limit: int) -> list[Negotiation]:
        query = self.db.query(Negotiation).filter(
            or_(
                Negotiation.buyer_profile_id == profile_id,
                Negotiation.seller_profile_id == profile_id,
            )
        )

        if status:
            query = query.filter(Negotiation.status == status)

        return query.order_by(Negotiation.created_at.desc()).offset(skip).limit(limit).all()

    def get_for_profile(self, *, negotiation_id, profile_id) -> Negotiation | None:
        return (
            self.db.query(Negotiation)
            .filter(
                Negotiation.id == negotiation_id,
                or_(
                    Negotiation.buyer_profile_id == profile_id,
                    Negotiation.seller_profile_id == profile_id,
                ),
            )
            .first()
        )
