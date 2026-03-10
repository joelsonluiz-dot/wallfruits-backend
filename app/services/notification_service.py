from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    db: Session,
    *,
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    actor_user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        actor_user_id=actor_user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(notification)
    return notification
