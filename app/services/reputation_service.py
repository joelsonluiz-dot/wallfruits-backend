import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.domain_enums import ContestationStatus, NegotiationStatus, PointSource
from app.models.negotiation import Negotiation
from app.models.profile import Profile
from app.models.reputation_review import ReputationReview
from app.models.review_contestation import ReviewContestation
from app.models.user import User
from app.services.gamification_service import GamificationService
from app.services.profile_service import ProfileService

logger = logging.getLogger("reputation_service")


class ReputationService:
    def __init__(self, db: Session):
        self.db = db
        self.profile_service = ProfileService(db)
        self.gamification_service = GamificationService(db)

    def _get_negotiation_or_fail(self, negotiation_id: UUID) -> Negotiation:
        negotiation = self.db.query(Negotiation).filter(Negotiation.id == negotiation_id).first()
        if not negotiation:
            raise ValueError("Negociação não encontrada")
        return negotiation

    def _recalculate_profile_reputation_score(self, profile_id: UUID) -> None:
        """Recalcula reputation_score como média ponderada pelo valor da negociação.
        Peso = proposed_price * quantity da negociação vinculada.
        Reviews invalidadas (contestação aceita) são excluídas.
        Se não há dados de peso, cai na média simples.
        """
        valid_reviews = (
            self.db.query(
                ReputationReview.rating,
                Negotiation.proposed_price,
                Negotiation.quantity,
            )
            .join(Negotiation, Negotiation.id == ReputationReview.negotiation_id)
            .filter(
                ReputationReview.reviewed_profile_id == profile_id,
                ReputationReview.is_invalidated.is_(False),
            )
            .all()
        )

        profile = self.db.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            return

        if not valid_reviews:
            profile.reputation_score = Decimal("0")
            return

        total_weight = Decimal("0")
        weighted_sum = Decimal("0")
        for rating, price, qty in valid_reviews:
            weight = Decimal(str(price or 0)) * Decimal(str(qty or 1))
            if weight <= 0:
                weight = Decimal("1")
            weighted_sum += Decimal(str(rating)) * weight
            total_weight += weight

        if total_weight > 0:
            score = weighted_sum / total_weight
        else:
            score = Decimal("0")

        profile.reputation_score = Decimal(str(round(float(score), 2)))

    def create_review(
        self,
        *,
        current_user: User,
        negotiation_id: UUID,
        rating: int,
        comment: str | None,
    ) -> ReputationReview:
        negotiation = self._get_negotiation_or_fail(negotiation_id)

        if negotiation.status != NegotiationStatus.COMPLETED.value:
            raise ValueError("A reputação só pode ser registrada após negociação concluída")

        reviewer_profile = self.profile_service.get_or_create_profile(current_user)
        participants = {negotiation.buyer_profile_id, negotiation.seller_profile_id}
        if reviewer_profile.id not in participants:
            raise ValueError("Usuário não participou da negociação")

        reviewed_profile_id = (
            negotiation.seller_profile_id
            if reviewer_profile.id == negotiation.buyer_profile_id
            else negotiation.buyer_profile_id
        )

        existing = (
            self.db.query(ReputationReview)
            .filter(
                ReputationReview.negotiation_id == negotiation.id,
                ReputationReview.reviewer_profile_id == reviewer_profile.id,
            )
            .first()
        )
        if existing:
            raise ValueError("Você já avaliou esta negociação")

        review = ReputationReview(
            negotiation_id=negotiation.id,
            reviewer_profile_id=reviewer_profile.id,
            reviewed_profile_id=reviewed_profile_id,
            rating=rating,
            comment=comment,
        )
        self.db.add(review)

        self._recalculate_profile_reputation_score(reviewed_profile_id)

        # Gamificação: pontos para quem avaliou e quem recebeu
        try:
            self.gamification_service.award_points(
                profile_id=reviewer_profile.id,
                source=PointSource.REVIEW_GIVEN.value,
                reference_id=str(review.id),
                description="Avaliação realizada",
            )
            self.gamification_service.award_points(
                profile_id=reviewed_profile_id,
                source=PointSource.REVIEW_RECEIVED.value,
                reference_id=str(review.id),
                description="Avaliação recebida",
            )
        except Exception as exc:
            logger.warning("Gamificação falhou em review: %s", exc)

        self.db.commit()
        self.db.refresh(review)
        return review

    def list_received_reviews(self, *, current_user: User, skip: int, limit: int) -> list[ReputationReview]:
        profile = self.profile_service.get_or_create_profile(current_user)
        return (
            self.db.query(ReputationReview)
            .filter(ReputationReview.reviewed_profile_id == profile.id)
            .order_by(ReputationReview.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_profile_reviews(self, *, profile_id: UUID, skip: int, limit: int) -> list[ReputationReview]:
        return (
            self.db.query(ReputationReview)
            .filter(ReputationReview.reviewed_profile_id == profile_id)
            .order_by(ReputationReview.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_profile_summary(self, *, profile_id: UUID) -> dict:
        valid_filter = and_(
            ReputationReview.reviewed_profile_id == profile_id,
            ReputationReview.is_invalidated.is_(False),
        )

        total_reviews = (
            self.db.query(func.count(ReputationReview.id))
            .filter(valid_filter)
            .scalar()
            or 0
        )

        avg_rating = (
            self.db.query(func.avg(ReputationReview.rating))
            .filter(valid_filter)
            .scalar()
            or 0
        )

        rows = (
            self.db.query(ReputationReview.rating, func.count(ReputationReview.id))
            .filter(valid_filter)
            .group_by(ReputationReview.rating)
            .all()
        )

        distribution = {i: 0 for i in range(1, 6)}
        for rating, count in rows:
            distribution[int(rating)] = int(count)

        # Calcular score ponderado
        weighted_rows = (
            self.db.query(
                ReputationReview.rating,
                Negotiation.proposed_price,
                Negotiation.quantity,
            )
            .join(Negotiation, Negotiation.id == ReputationReview.negotiation_id)
            .filter(valid_filter)
            .all()
        )

        total_weight = Decimal("0")
        weighted_sum = Decimal("0")
        total_negotiated_value = Decimal("0")
        for rating, price, qty in weighted_rows:
            val = Decimal(str(price or 0)) * Decimal(str(qty or 1))
            weight = max(val, Decimal("1"))
            weighted_sum += Decimal(str(rating)) * weight
            total_weight += weight
            total_negotiated_value += val

        weighted_avg = float(round(float(weighted_sum / total_weight), 2)) if total_weight > 0 else 0.0

        # Contestações
        total_contestations = (
            self.db.query(func.count(ReviewContestation.id))
            .join(ReputationReview, ReputationReview.id == ReviewContestation.review_id)
            .filter(ReputationReview.reviewed_profile_id == profile_id)
            .scalar()
            or 0
        )
        accepted_contestations = (
            self.db.query(func.count(ReviewContestation.id))
            .join(ReputationReview, ReputationReview.id == ReviewContestation.review_id)
            .filter(
                ReputationReview.reviewed_profile_id == profile_id,
                ReviewContestation.status == ContestationStatus.ACCEPTED.value,
            )
            .scalar()
            or 0
        )

        return {
            "profile_id": profile_id,
            "average_rating": float(round(float(avg_rating), 2)),
            "weighted_average_rating": weighted_avg,
            "total_reviews": int(total_reviews),
            "total_negotiated_value": float(total_negotiated_value),
            "rating_distribution": distribution,
            "contestations": {
                "total": int(total_contestations),
                "accepted": int(accepted_contestations),
            },
        }

    # ── Contestação ────────────────────────────────────────────

    def create_contestation(
        self,
        *,
        current_user: User,
        review_id: UUID,
        reason: str,
    ) -> ReviewContestation:
        """O avaliado contesta uma review recebida."""
        review = self.db.query(ReputationReview).filter(ReputationReview.id == review_id).first()
        if not review:
            raise ValueError("Avaliação não encontrada")

        profile = self.profile_service.get_or_create_profile(current_user)
        if profile.id != review.reviewed_profile_id:
            raise ValueError("Somente o avaliado pode contestar esta avaliação")

        if review.is_invalidated:
            raise ValueError("Avaliação já foi invalidada")

        existing = (
            self.db.query(ReviewContestation)
            .filter(
                ReviewContestation.review_id == review_id,
                ReviewContestation.status == ContestationStatus.PENDING.value,
            )
            .first()
        )
        if existing:
            raise ValueError("Já existe uma contestação pendente para esta avaliação")

        contestation = ReviewContestation(
            review_id=review_id,
            requester_profile_id=profile.id,
            reason=reason,
        )
        self.db.add(contestation)
        self.db.commit()
        self.db.refresh(contestation)
        return contestation

    def review_contestation(
        self,
        *,
        contestation_id: UUID,
        admin_user: User,
        new_status: str,
        review_notes: str | None = None,
    ) -> ReviewContestation:
        """Admin aceita ou rejeita uma contestação."""
        if new_status not in {ContestationStatus.ACCEPTED.value, ContestationStatus.REJECTED.value}:
            raise ValueError("Status deve ser 'accepted' ou 'rejected'")

        contestation = (
            self.db.query(ReviewContestation)
            .filter(ReviewContestation.id == contestation_id)
            .first()
        )
        if not contestation:
            raise ValueError("Contestação não encontrada")

        if contestation.status != ContestationStatus.PENDING.value:
            raise ValueError("Contestação já foi revisada")

        contestation.status = new_status
        contestation.reviewed_by_user_id = admin_user.id
        contestation.reviewed_at = datetime.now(timezone.utc)
        contestation.review_notes = review_notes

        if new_status == ContestationStatus.ACCEPTED.value:
            review = contestation.review
            review.is_invalidated = True
            self.db.flush()  # persiste is_invalidated antes de recalcular
            self._recalculate_profile_reputation_score(review.reviewed_profile_id)

        self.db.commit()
        self.db.refresh(contestation)
        return contestation

    def list_pending_contestations(self, *, skip: int = 0, limit: int = 50) -> list[ReviewContestation]:
        return (
            self.db.query(ReviewContestation)
            .filter(ReviewContestation.status == ContestationStatus.PENDING.value)
            .order_by(ReviewContestation.created_at)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_my_contestations(self, *, current_user: User, skip: int = 0, limit: int = 50) -> list[ReviewContestation]:
        profile = self.profile_service.get_or_create_profile(current_user)
        return (
            self.db.query(ReviewContestation)
            .filter(ReviewContestation.requester_profile_id == profile.id)
            .order_by(ReviewContestation.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
