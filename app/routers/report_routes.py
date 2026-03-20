from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.user import User
from app.schemas.report_schema import ReportCreate, ReportResponse, ReportReviewUpdate
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


def _http_error_from_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    normalized = detail.lower()

    if "não encontrada" in normalized or "nao encontrada" in normalized:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    if "não é permitido" in normalized or "nao e permitido" in normalized:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = ReportService(db)
    try:
        return service.create_report(
            current_user=current_user,
            reported_profile_id=payload.reported_profile_id,
            reported_offer_id=payload.reported_offer_id,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get("/my", response_model=list[ReportResponse])
def list_my_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ReportService(db).list_my_reports(current_user=current_user, skip=skip, limit=limit)


@router.get("", response_model=list[ReportResponse])
@router.get("/", response_model=list[ReportResponse])
def list_reports_admin(
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern="^(pending|under_review|resolved|dismissed)$",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito")

    return ReportService(db).list_reports(status=status_filter, skip=skip, limit=limit)


@router.patch("/{report_id}", response_model=ReportResponse)
def review_report_admin(
    report_id: UUID,
    payload: ReportReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito")

    service = ReportService(db)
    try:
        report = service.get_report_or_fail(report_id)
        return service.review_report(
            report=report,
            reviewer=current_user,
            status=payload.status,
            resolution_notes=payload.resolution_notes,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)
