from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models import Message, Negotiation, Notification, Offer, Transaction, User
from app.services.notification_service import create_notification

router = APIRouter(prefix="/growth", tags=["growth"])


def _require_admin(user: User) -> None:
    if user.role != "admin" and not user.is_superuser:
        raise HTTPException(status_code=403, detail="Acesso restrito")


@router.get("/ops")
def get_growth_ops(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Métricas de operação de crescimento e confiança transacional."""
    _require_admin(current_user)

    since = datetime.utcnow() - timedelta(days=days)

    total_users = db.query(func.count(User.id)).scalar() or 0
    active_offers = db.query(func.count(Offer.id)).filter(Offer.status == "active").scalar() or 0

    messages = db.query(func.count(Message.id)).filter(Message.created_at >= since).scalar() or 0
    negotiations = db.query(func.count(Negotiation.id)).filter(Negotiation.created_at >= since).scalar() or 0
    transactions_total = db.query(func.count(Transaction.id)).filter(Transaction.created_at >= since).scalar() or 0
    completed = db.query(func.count(Transaction.id)).filter(
        Transaction.created_at >= since,
        Transaction.status == "completed",
    ).scalar() or 0
    cancelled = db.query(func.count(Transaction.id)).filter(
        Transaction.created_at >= since,
        Transaction.status == "cancelled",
    ).scalar() or 0
    disputed = db.query(func.count(Transaction.id)).filter(
        Transaction.created_at >= since,
        Transaction.status == "disputed",
    ).scalar() or 0

    unresolved_reports = db.query(func.count(Notification.id)).filter(
        Notification.notification_type == "admin_alert",
        Notification.is_read.is_(False),
    ).scalar() or 0

    def _pct(num: int, den: int) -> float:
        if den <= 0:
            return 0.0
        return round((num / den) * 100, 2)

    completed_rate = _pct(completed, transactions_total)
    cancel_rate = _pct(cancelled, transactions_total)
    dispute_rate = _pct(disputed, transactions_total)
    negotiation_rate = _pct(negotiations, max(messages, 1))

    confidence_score = max(
        0.0,
        min(
            100.0,
            round(
                60
                + min(completed_rate * 0.5, 25)
                - min(cancel_rate * 0.9, 20)
                - min(dispute_rate * 1.2, 20)
                + min(negotiation_rate * 0.2, 15),
                2,
            ),
        ),
    )

    alerts = []
    if completed_rate < 35:
        alerts.append("Baixa taxa de conclusão transacional.")
    if cancel_rate > 20:
        alerts.append("Cancelamentos elevados no período.")
    if dispute_rate > 8:
        alerts.append("Disputas acima do limite saudável.")
    if active_offers < 25:
        alerts.append("Base de ofertas ativas ainda limitada para escala.")
    if negotiation_rate < 25:
        alerts.append("Conversa com baixa progressão para negociação.")

    actions = []
    if completed_rate < 35:
        actions.append("Implementar SLA de resposta em mensagens e negociação.")
    if cancel_rate > 20 or dispute_rate > 8:
        actions.append("Reforçar regras de confiança e verificação antes de fechar pedido.")
    if active_offers < 25:
        actions.append("Rodar campanha de ativação de produtores com incentivo inicial.")
    if negotiation_rate < 25:
        actions.append("Inserir playbook de abordagem comercial para primeiros contatos.")
    if not actions:
        actions.append("Operação saudável: priorizar expansão geográfica e canais B2B.")

    return {
        "window_days": days,
        "kpis": {
            "total_users": int(total_users),
            "active_offers": int(active_offers),
            "messages": int(messages),
            "negotiations": int(negotiations),
            "transactions_total": int(transactions_total),
            "completed_rate": completed_rate,
            "cancel_rate": cancel_rate,
            "dispute_rate": dispute_rate,
            "negotiation_progress_rate": negotiation_rate,
            "confidence_score": confidence_score,
            "admin_alerts_open": int(unresolved_reports),
        },
        "alerts": alerts,
        "actions": actions,
    }


@router.post("/ops/alert-admins")
def alert_admins(
    title: str = Query(..., min_length=3, max_length=120),
    message: str = Query(..., min_length=3, max_length=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dispara alerta operacional para todos os administradores."""
    _require_admin(current_user)

    admins = db.query(User).filter(User.role == "admin", User.is_active.is_(True)).all()
    sent = 0
    for admin in admins:
        create_notification(
            db,
            user_id=admin.id,
            actor_user_id=current_user.id,
            notification_type="admin_alert",
            title=title,
            message=message,
            resource_type="growth",
            resource_id="ops",
        )
        sent += 1

    db.commit()
    return {"sent": sent}