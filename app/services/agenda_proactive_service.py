from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.agenda_event import AgendaEvent
from app.models.notification import Notification


FIXED_HOLIDAYS = {
    "01-01",  # Confraternizacao Universal
    "04-21",  # Tiradentes
    "05-01",  # Dia do Trabalho
    "09-07",  # Independencia
    "10-12",  # Nossa Senhora Aparecida
    "11-02",  # Finados
    "11-15",  # Proclamacao da Republica
    "12-25",  # Natal
}


def is_holiday(dt: datetime) -> bool:
    return dt.astimezone(timezone.utc).strftime("%m-%d") in FIXED_HOLIDAYS


def is_business_hour(dt: datetime) -> bool:
    local = dt.astimezone(timezone.utc)
    if local.weekday() >= 5:
        return False
    start = time(hour=8, minute=0)
    end = time(hour=18, minute=0)
    return start <= local.time() <= end


def event_rule_hints(starts_at: datetime, ends_at: datetime) -> dict:
    return {
        "outside_business_hours": not is_business_hour(starts_at),
        "holiday": is_holiday(starts_at),
        "weekend": starts_at.astimezone(timezone.utc).weekday() >= 5,
        "short_event": (ends_at - starts_at) < timedelta(minutes=20),
    }


def _notification_exists(db: Session, *, user_id: int, resource_type: str, resource_id: str) -> bool:
    row = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.resource_type == resource_type,
            Notification.resource_id == resource_id,
        )
        .first()
    )
    return row is not None


def _create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    message: str,
    notification_type: str,
    resource_type: str,
    resource_id: str,
) -> bool:
    if _notification_exists(db, user_id=user_id, resource_type=resource_type, resource_id=resource_id):
        return False

    db.add(
        Notification(
            user_id=user_id,
            actor_user_id=None,
            notification_type=notification_type,
            title=title,
            message=message,
            resource_type=resource_type,
            resource_id=resource_id,
            is_read=False,
        )
    )
    return True


def maybe_create_rule_notifications(db: Session, *, user_id: int, event: AgendaEvent) -> int:
    hints = event_rule_hints(event.starts_at, event.ends_at)
    created = 0

    if hints["holiday"]:
        if _create_notification(
            db,
            user_id=user_id,
            title="Agenda: evento em feriado",
            message=f"{event.title} está agendado em um feriado. Confirme se deseja manter este horário.",
            notification_type="agenda_rule_alert",
            resource_type="agenda_rule",
            resource_id=f"{event.id}:holiday",
        ):
            created += 1

    if hints["outside_business_hours"]:
        if _create_notification(
            db,
            user_id=user_id,
            title="Agenda: fora do horário comercial",
            message=f"{event.title} está fora do horário comercial (08:00-18:00).",
            notification_type="agenda_rule_alert",
            resource_type="agenda_rule",
            resource_id=f"{event.id}:business_hours",
        ):
            created += 1

    return created


def emit_predictive_notifications_for_user(db: Session, *, user_id: int, now: datetime | None = None) -> int:
    ref = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    horizon = ref + timedelta(hours=25)

    rows = (
        db.query(AgendaEvent)
        .filter(
            AgendaEvent.user_id == user_id,
            AgendaEvent.status == "scheduled",
            AgendaEvent.starts_at >= ref,
            AgendaEvent.starts_at <= horizon,
        )
        .order_by(AgendaEvent.starts_at.asc())
        .all()
    )

    thresholds = [
        (24 * 60, "24h", "Sua reserva começa em cerca de 24 horas."),
        (2 * 60, "2h", "Sua reserva começa em cerca de 2 horas."),
        (30, "30m", "Sua reserva começa em cerca de 30 minutos."),
    ]

    created = 0
    for event in rows:
        delta_minutes = int((event.starts_at - ref).total_seconds() // 60)
        if delta_minutes < 0:
            continue

        for threshold_minutes, tag, copy in thresholds:
            # Janela de tolerancia para disparo seguro sem duplicar.
            if delta_minutes <= threshold_minutes and delta_minutes >= max(0, threshold_minutes - 15):
                if _create_notification(
                    db,
                    user_id=user_id,
                    title=f"Lembrete de agenda ({tag})",
                    message=f"{copy} Evento: {event.title}.",
                    notification_type="agenda_predictive",
                    resource_type="agenda_predictive",
                    resource_id=f"{event.id}:{tag}",
                ):
                    created += 1

    return created


def emit_predictive_notifications_for_all_users(db: Session, *, now: datetime | None = None) -> dict:
    ref = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    horizon = ref + timedelta(hours=25)

    user_rows = (
        db.query(AgendaEvent.user_id)
        .filter(
            AgendaEvent.status == "scheduled",
            AgendaEvent.starts_at >= ref,
            AgendaEvent.starts_at <= horizon,
        )
        .distinct()
        .all()
    )
    user_ids = [int(row[0]) for row in user_rows if row and row[0] is not None]

    created_total = 0
    for user_id in user_ids:
        created_total += emit_predictive_notifications_for_user(db, user_id=user_id, now=ref)

    return {
        "users_scanned": len(user_ids),
        "predictive_notifications_created": int(created_total),
    }
