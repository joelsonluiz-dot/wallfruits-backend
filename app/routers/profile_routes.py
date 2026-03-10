from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile_schema import (
    PendingProfileValidationItem,
    ProfileDocumentSubmission,
    ProfileResponse,
    ProfileUpsert,
    ProfileValidationUpdate,
)
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ProfileService(db).get_or_create_profile(current_user)


@router.put("/me", response_model=ProfileResponse)
def upsert_my_profile(
    payload: ProfileUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)
    profile = profile_service.get_or_create_profile(current_user)

    profile.profile_type = payload.profile_type
    profile.document_number = payload.document_number
    profile.company_name = payload.company_name
    profile.phone = payload.phone
    profile.state = payload.state
    profile.city = payload.city

    if payload.profile_type == "visitor":
        profile.validation_status = "approved"
    else:
        profile.validation_status = "pending_validation"

    db.commit()
    db.refresh(profile)
    return profile


@router.patch("/{profile_id}/validation", response_model=ProfileResponse)
def update_validation_status(
    profile_id: UUID,
    payload: ProfileValidationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito")

    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil não encontrado")

    profile.validation_status = payload.validation_status
    profile.validation_notes = payload.validation_notes
    profile.validated_at = datetime.now(timezone.utc)
    profile.validated_by_user_id = current_user.id
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/me/documents", response_model=ProfileResponse)
def submit_documents_for_validation(
    payload: ProfileDocumentSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile_service = ProfileService(db)
    profile = profile_service.get_or_create_profile(current_user)

    profile = profile_service.submit_documents(
        profile=profile,
        document_type=payload.document_type,
        document_number=payload.document_number,
        document_front_url=payload.document_front_url,
        document_back_url=payload.document_back_url,
        document_selfie_url=payload.document_selfie_url,
        proof_of_address_url=payload.proof_of_address_url,
    )

    return profile


@router.get("/pending-validation", response_model=list[PendingProfileValidationItem])
def list_pending_validation_profiles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito")

    rows = ProfileService(db).list_pending_validation()[:limit]

    return [
        PendingProfileValidationItem(
            id=row.id,
            user_id=row.user_id,
            user_name=row.user.name if row.user else "",
            user_email=row.user.email if row.user else "",
            profile_type=row.profile_type,
            validation_status=row.validation_status,
            document_type=row.document_type,
            document_number=row.document_number,
            submitted_at=row.submitted_at,
            created_at=row.created_at,
        )
        for row in rows
    ]
