from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user, get_current_user_optional
from app.database.connection import get_db
from app.models import Follow, Offer, User
from app.schemas.social_schema import ActiveAccountItem, FollowActionResponse, PublicUserProfileResponse
from app.services.notification_service import create_notification

router = APIRouter(prefix="/social", tags=["social"])


def _username_from_email(email: str, user_id: int) -> str:
    if "@" in email:
        return f"@{email.split('@')[0]}"
    return f"@user{user_id}"


def _offer_images(offer: Offer) -> list[str]:
    from app.schemas.offer_schema import OfferResponse

    return OfferResponse.parse_images(offer.images)


@router.get("/users/{user_id}", response_model=PublicUserProfileResponse)
def get_public_user_profile(
    user_id: int,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
    limit: int = Query(24, ge=1, le=100),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    offers = (
        db.query(Offer)
        .filter(Offer.user_id == user.id)
        .order_by(Offer.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/users/search", response_model=list[ActiveAccountItem])
def search_active_accounts(
    q: str = Query("", min_length=0, max_length=80),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.is_active.is_(True), User.id != current_user.id)

    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                User.name.ilike(term),
                User.email.ilike(term),
                User.location.ilike(term),
            )
        )

    rows = query.order_by(User.created_at.desc()).limit(limit).all()

    return [
        ActiveAccountItem(
            id=user.id,
            name=user.name,
            username=_username_from_email(user.email, user.id),
            role=user.role,
            location=user.location,
            profile_image=user.profile_image,
        )
        for user in rows
    ]

    followers_count = db.query(func.count(Follow.id)).filter(Follow.followed_id == user.id).scalar() or 0
    following_count = db.query(func.count(Follow.id)).filter(Follow.follower_id == user.id).scalar() or 0

    is_following = False
    if current_user:
        is_following = (
            db.query(Follow)
            .filter(Follow.follower_id == current_user.id, Follow.followed_id == user.id)
            .first()
            is not None
        )

    return PublicUserProfileResponse(
        id=user.id,
        name=user.name,
        username=_username_from_email(user.email, user.id),
        email=user.email,
        role=user.role,
        bio=user.bio,
        location=user.location,
        profile_image=user.profile_image,
        total_offers=len(offers),
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
        offers=[
            {
                "id": offer.id,
                "product_name": offer.product_name,
                "price": offer.price,
                "unit": offer.unit,
                "location": offer.location,
                "images": _offer_images(offer),
                "status": offer.status,
                "created_at": offer.created_at,
            }
            for offer in offers
        ],
    )


@router.post("/users/{user_id}/follow", response_model=FollowActionResponse)
def follow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Você não pode seguir a si mesmo")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    existing = (
        db.query(Follow)
        .filter(Follow.follower_id == current_user.id, Follow.followed_id == target_user.id)
        .first()
    )
    if existing:
        followers_count = db.query(func.count(Follow.id)).filter(Follow.followed_id == target_user.id).scalar() or 0
        return FollowActionResponse(success=True, following=True, followers_count=followers_count)

    db.add(Follow(follower_id=current_user.id, followed_id=target_user.id))

    create_notification(
        db,
        user_id=target_user.id,
        actor_user_id=current_user.id,
        notification_type="follow",
        title="Novo seguidor",
        message=f"{current_user.name} começou a seguir você.",
        resource_type="user",
        resource_id=str(current_user.id),
    )

    db.commit()

    followers_count = db.query(func.count(Follow.id)).filter(Follow.followed_id == target_user.id).scalar() or 0
    return FollowActionResponse(success=True, following=True, followers_count=followers_count)


@router.delete("/users/{user_id}/follow", response_model=FollowActionResponse)
def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    follow_rel = (
        db.query(Follow)
        .filter(Follow.follower_id == current_user.id, Follow.followed_id == user_id)
        .first()
    )

    if follow_rel:
        db.delete(follow_rel)
        db.commit()

    followers_count = db.query(func.count(Follow.id)).filter(Follow.followed_id == user_id).scalar() or 0
    return FollowActionResponse(success=True, following=False, followers_count=followers_count)
