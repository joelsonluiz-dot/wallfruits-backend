from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.reputation_schema import (
    ContestationCreateRequest,
    ContestationResponse,
    ContestationReviewRequest,
    ReputationReviewCreate,
    ReputationReviewResponse,
    ReputationSummaryResponse,
)
from app.services.reputation_service import ReputationService

router = APIRouter(prefix="/reputation", tags=["reputation"])


def _http_error_from_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    normalized = detail.lower()

    if "não encontrada" in normalized or "nao encontrada" in normalized:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    if "não participou" in normalized or "nao participou" in normalized:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post("/reviews", response_model=ReputationReviewResponse, status_code=status.HTTP_201_CREATED)
def create_reputation_review(
    payload: ReputationReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReputationService(db)

    try:
        return service.create_review(
            current_user=current_user,
            negotiation_id=payload.negotiation_id,
            rating=payload.rating,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get("/my/received", response_model=list[ReputationReviewResponse])
def list_my_received_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReputationService(db)
    return service.list_received_reviews(current_user=current_user, skip=skip, limit=limit)


@router.get("/profiles/{profile_id}", response_model=list[ReputationReviewResponse])
def list_profile_reviews(
    profile_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = ReputationService(db)
    return service.list_profile_reviews(profile_id=profile_id, skip=skip, limit=limit)


@router.get("/profiles/{profile_id}/summary", response_model=ReputationSummaryResponse)
def get_profile_reputation_summary(
    profile_id: UUID,
    db: Session = Depends(get_db),
):
    service = ReputationService(db)
    return service.get_profile_summary(profile_id=profile_id)


# ── Contestação ──────────────────────────────────────────────


@router.post(
    "/reviews/{review_id}/contest",
    response_model=ContestationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contestation(
    review_id: UUID,
    payload: ContestationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReputationService(db)
    try:
        return service.create_contestation(
            current_user=current_user,
            review_id=review_id,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get("/my/contestations", response_model=list[ContestationResponse])
def list_my_contestations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReputationService(db)
    return service.list_my_contestations(current_user=current_user, skip=skip, limit=limit)


@router.get("/admin/contestations", response_model=list[ContestationResponse])
def list_pending_contestations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReputationService(db)
    return service.list_pending_contestations(skip=skip, limit=limit)


@router.patch(
    "/admin/contestations/{contestation_id}",
    response_model=ContestationResponse,
)
def review_contestation(
    contestation_id: UUID,
    payload: ContestationReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReputationService(db)
    try:
        return service.review_contestation(
            contestation_id=contestation_id,
            admin_user=current_user,
            new_status=payload.status,
            review_notes=payload.review_notes,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)
