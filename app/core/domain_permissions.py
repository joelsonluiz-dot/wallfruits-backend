from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.profile import Profile
from app.models.user import User
from app.services.negotiation_policy_service import NegotiationPolicyService
from app.services.profile_service import ProfileService


def get_current_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    return ProfileService(db).get_or_create_profile(current_user)


def require_approved_offer_publisher(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    if current_user.role == "admin":
        return current_user

    profile_service = ProfileService(db)
    profile = profile_service.get_or_create_profile(current_user)

    can_publish, reason = profile_service.can_publish_offer(profile)
    if not can_publish:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    return current_user


def enforce_negotiation_policy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    if current_user.role == "admin":
        return

    policy_service = NegotiationPolicyService(db)
    try:
        policy_service.enforce_monthly_limit(current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
