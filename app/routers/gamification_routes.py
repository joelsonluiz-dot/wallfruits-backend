"""Rotas de gamificação — pontos, badges e leaderboard."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.gamification_schema import (
    AdminPointAdjustment,
    BadgeResponse,
    GamificationProfileResponse,
    LeaderboardEntry,
    PointTransactionResponse,
    UserBadgeResponse,
)
from app.services.gamification_service import GamificationService
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/gamification", tags=["gamification"])


def _get_profile_id(user: User, db: Session) -> UUID:
    ps = ProfileService(db)
    profile = ps.get_or_create_profile(user)
    return profile.id


# ── Perfil de gamificação ────────────────────────────────────

@router.get("/me", response_model=GamificationProfileResponse)
def get_my_gamification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_id = _get_profile_id(current_user, db)
    service = GamificationService(db)
    gp = service.get_or_create_profile(profile_id)
    db.commit()
    return gp


@router.get("/profiles/{profile_id}", response_model=GamificationProfileResponse)
def get_gamification_profile(
    profile_id: UUID,
    db: Session = Depends(get_db),
):
    service = GamificationService(db)
    try:
        gp = service.get_or_create_profile(profile_id)
        db.commit()
        return gp
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Histórico de pontos ─────────────────────────────────────

@router.get("/me/points", response_model=list[PointTransactionResponse])
def get_my_point_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_id = _get_profile_id(current_user, db)
    service = GamificationService(db)
    return service.get_point_history(profile_id, skip=skip, limit=limit)


# ── Badges ───────────────────────────────────────────────────

@router.get("/me/badges", response_model=list[UserBadgeResponse])
def get_my_badges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_id = _get_profile_id(current_user, db)
    service = GamificationService(db)
    return service.get_user_badges(profile_id)


@router.get("/badges", response_model=list[BadgeResponse])
def list_all_badges(db: Session = Depends(get_db)):
    service = GamificationService(db)
    return service.list_all_badges()


# ── Leaderboard ──────────────────────────────────────────────

@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def get_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = GamificationService(db)
    return service.get_leaderboard(limit=limit)


# ── Admin ────────────────────────────────────────────────────

@router.post("/admin/profiles/{profile_id}/adjust", response_model=PointTransactionResponse)
def admin_adjust_points(
    profile_id: UUID,
    payload: AdminPointAdjustment,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")

    service = GamificationService(db)
    try:
        tx = service.award_points(
            profile_id=profile_id,
            source=payload.source,
            amount=payload.amount,
            description=payload.description,
        )
        db.commit()
        return tx
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/admin/badges/seed")
def admin_seed_badges(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")

    service = GamificationService(db)
    created = service.ensure_default_badges()
    db.commit()
    return {"created": created}
