"""
Serviço de gamificação — pontos, níveis e badges.
Separado e independente da wallet (financeiro).
"""
import logging
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.domain_enums import PointSource
from app.models.badge import Badge, UserBadge
from app.models.gamification_profile import GamificationProfile
from app.models.point_transaction import PointTransaction
from app.models.profile import Profile

logger = logging.getLogger("gamification_service")

# ── Configuração de níveis ──────────────────────────────────
# XP necessário para avançar de nível: level N → N+1 exige XP_PER_LEVEL * N
XP_PER_LEVEL = 100

# Tabela de pontos por evento
POINTS_TABLE: dict[str, int] = {
    PointSource.NEGOTIATION_COMPLETED.value: 50,
    PointSource.REVIEW_GIVEN.value: 10,
    PointSource.REVIEW_RECEIVED.value: 5,
    PointSource.OFFER_PUBLISHED.value: 15,
    PointSource.FIRST_SALE.value: 100,
    PointSource.RAFFLE_TICKET.value: -20,  # custo em pontos
}

# Badges automáticos por milestone
_AUTO_BADGES: list[dict] = [
    {"code": "first_negotiation", "after_event": PointSource.NEGOTIATION_COMPLETED.value, "min_count": 1},
    {"code": "negotiator_10", "after_event": PointSource.NEGOTIATION_COMPLETED.value, "min_count": 10},
    {"code": "negotiator_50", "after_event": PointSource.NEGOTIATION_COMPLETED.value, "min_count": 50},
    {"code": "first_review", "after_event": PointSource.REVIEW_GIVEN.value, "min_count": 1},
    {"code": "reviewer_10", "after_event": PointSource.REVIEW_GIVEN.value, "min_count": 10},
    {"code": "first_offer", "after_event": PointSource.OFFER_PUBLISHED.value, "min_count": 1},
    {"code": "first_sale", "after_event": PointSource.FIRST_SALE.value, "min_count": 1},
]


class GamificationService:
    def __init__(self, db: Session):
        self.db = db

    # ── Perfil ──────────────────────────────────────────────

    def get_or_create_profile(self, profile_id: UUID) -> GamificationProfile:
        """Obtém ou cria o perfil de gamificação vinculado ao profile de domínio."""
        gp = (
            self.db.query(GamificationProfile)
            .filter(GamificationProfile.profile_id == profile_id)
            .first()
        )
        if gp:
            return gp

        # Verificar que o profile de domínio existe
        exists = self.db.query(Profile.id).filter(Profile.id == profile_id).first()
        if not exists:
            raise ValueError("Perfil não encontrado")

        gp = GamificationProfile(profile_id=profile_id)
        self.db.add(gp)
        self.db.flush()
        return gp

    # ── Pontos ──────────────────────────────────────────────

    def award_points(
        self,
        *,
        profile_id: UUID,
        source: str,
        amount: int | None = None,
        reference_id: str | None = None,
        description: str | None = None,
    ) -> PointTransaction:
        """
        Concede pontos a um perfil.
        Se amount não for fornecido, usa POINTS_TABLE[source].
        Atualiza total_points, XP e nível automaticamente.
        """
        pts = amount if amount is not None else POINTS_TABLE.get(source, 0)
        if pts == 0:
            raise ValueError("Quantidade de pontos inválida")

        gp = self.get_or_create_profile(profile_id)

        # Impedir saldo negativo
        if pts < 0 and (gp.total_points + pts) < 0:
            raise ValueError("Pontos insuficientes")

        tx = PointTransaction(
            gamification_profile_id=gp.id,
            amount=pts,
            source=source,
            reference_id=reference_id,
            description=description,
        )
        self.db.add(tx)

        gp.total_points += pts
        if pts > 0:
            gp.xp += pts
            self._check_level_up(gp)

        self.db.flush()

        # Verificar badges automáticos
        if pts > 0:
            self._check_auto_badges(gp, source)

        return tx

    def _check_level_up(self, gp: GamificationProfile) -> None:
        """Sobe de nível enquanto XP for suficiente."""
        while gp.xp >= XP_PER_LEVEL * gp.level:
            gp.xp -= XP_PER_LEVEL * gp.level
            gp.level += 1
            logger.info(
                "Perfil %s subiu para nível %d", gp.profile_id, gp.level
            )

    def _check_auto_badges(self, gp: GamificationProfile, source: str) -> None:
        """Verifica e concede badges automáticos baseados em milestones."""
        event_count = (
            self.db.query(func.count(PointTransaction.id))
            .filter(
                PointTransaction.gamification_profile_id == gp.id,
                PointTransaction.source == source,
                PointTransaction.amount > 0,
            )
            .scalar()
            or 0
        )

        for rule in _AUTO_BADGES:
            if rule["after_event"] != source:
                continue
            if event_count < rule["min_count"]:
                continue

            badge = (
                self.db.query(Badge)
                .filter(Badge.code == rule["code"], Badge.is_active.is_(True))
                .first()
            )
            if not badge:
                continue

            already = (
                self.db.query(UserBadge.id)
                .filter(
                    UserBadge.gamification_profile_id == gp.id,
                    UserBadge.badge_id == badge.id,
                )
                .first()
            )
            if already:
                continue

            ub = UserBadge(gamification_profile_id=gp.id, badge_id=badge.id)
            self.db.add(ub)
            logger.info(
                "Badge '%s' desbloqueado para perfil %s", badge.code, gp.profile_id
            )

    # ── Consultas ───────────────────────────────────────────

    def get_point_history(
        self, profile_id: UUID, *, skip: int = 0, limit: int = 50
    ) -> list[PointTransaction]:
        gp = self.get_or_create_profile(profile_id)
        return (
            self.db.query(PointTransaction)
            .filter(PointTransaction.gamification_profile_id == gp.id)
            .order_by(PointTransaction.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_user_badges(self, profile_id: UUID) -> list[UserBadge]:
        gp = self.get_or_create_profile(profile_id)
        return (
            self.db.query(UserBadge)
            .filter(UserBadge.gamification_profile_id == gp.id)
            .order_by(UserBadge.unlocked_at.desc())
            .all()
        )

    def get_leaderboard(self, *, limit: int = 20) -> list[dict]:
        rows = (
            self.db.query(GamificationProfile)
            .order_by(GamificationProfile.total_points.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "profile_id": str(row.profile_id),
                "total_points": row.total_points,
                "level": row.level,
                "rank": idx + 1,
            }
            for idx, row in enumerate(rows)
        ]

    # ── Badges administrativos ──────────────────────────────

    def list_all_badges(self) -> list[Badge]:
        return self.db.query(Badge).order_by(Badge.code).all()

    def ensure_default_badges(self) -> int:
        """Cria badges padrão se não existirem. Retorna quantidade criada."""
        defaults = [
            {"code": "first_negotiation", "name": "Primeira Negociação", "description": "Completou sua primeira negociação", "category": "trading"},
            {"code": "negotiator_10", "name": "Negociador Ativo", "description": "Completou 10 negociações", "category": "trading"},
            {"code": "negotiator_50", "name": "Mestre Negociador", "description": "Completou 50 negociações", "category": "trading"},
            {"code": "first_review", "name": "Primeira Avaliação", "description": "Fez sua primeira avaliação", "category": "community"},
            {"code": "reviewer_10", "name": "Avaliador Dedicado", "description": "Fez 10 avaliações", "category": "community"},
            {"code": "first_offer", "name": "Primeira Oferta", "description": "Publicou sua primeira oferta", "category": "milestone"},
            {"code": "first_sale", "name": "Primeira Venda", "description": "Concluiu sua primeira venda", "category": "milestone"},
        ]
        created = 0
        for d in defaults:
            exists = self.db.query(Badge.id).filter(Badge.code == d["code"]).first()
            if not exists:
                self.db.add(Badge(**d))
                created += 1
        if created:
            self.db.flush()
        return created
