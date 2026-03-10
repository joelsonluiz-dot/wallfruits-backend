from sqlalchemy.orm import Session

from app.models.negotiation_message import NegotiationMessage
from app.repositories.base_repository import BaseRepository


class NegotiationMessageRepository(BaseRepository[NegotiationMessage]):
    def __init__(self, db: Session):
        super().__init__(db, NegotiationMessage)

    def list_by_negotiation(self, negotiation_id) -> list[NegotiationMessage]:
        return (
            self.db.query(NegotiationMessage)
            .filter(NegotiationMessage.negotiation_id == negotiation_id)
            .order_by(NegotiationMessage.created_at.asc())
            .all()
        )
