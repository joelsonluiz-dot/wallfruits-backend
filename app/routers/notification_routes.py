from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models import Notification, User
from app.schemas.social_schema import NotificationActor, NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
@router.get("/", response_model=list[NotificationResponse])
def list_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=200),
    notification_type: str | None = Query(None, min_length=1, max_length=50),
    only_unread: bool = Query(False),
):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)

    if only_unread:
        query = query.filter(Notification.is_read.is_(False))

    rows = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    return [
        NotificationResponse(
            id=item.id,
            notification_type=item.notification_type,
            title=item.title,
            message=item.message,
            resource_type=item.resource_type,
            resource_id=item.resource_id,
            is_read=item.is_read,
            created_at=item.created_at,
            actor=NotificationActor(
                id=item.actor.id if item.actor else None,
                name=item.actor.name if item.actor else None,
                profile_image=item.actor.profile_image if item.actor else None,
            ) if item.actor else None,
        )
        for item in rows
    ]


@router.get("/unread-count")
def unread_notifications_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .scalar()
        or 0
    )
    return {"unread": int(count)}


@router.post("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if row:
        row.is_read = True
        db.commit()
    return {"success": True}


@router.post("/read-all")
def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read.is_(False),
    ).update({"is_read": True})
    db.commit()
    return {"success": True}
