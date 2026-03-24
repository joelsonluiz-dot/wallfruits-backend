from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Notification, Profile, Service
from app.models.ai_models import AISuggestion
from app.models.negotiation import Negotiation
from app.models.user import User
from app.realtime.notification_ws import notification_manager


class RuleEngine:
    """Motor de regras para automações de negócio orientadas por evento."""

    def __init__(self, db: Session):
        self.db = db

    async def on_negotiation_closed(self, *, negotiation: Negotiation) -> dict:
        # Quando negociação fecha: cria serviço + agenda eventos + notifica envolvidos.
        generated = {
            "service_created": False,
            "events_scheduled": 0,
            "notified_users": 0,
        }

        service = Service(
            titulo="Serviço originado de negociação fechada",
            descricao=f"Execução operacional vinculada à negociação {negotiation.id}",
            preco=str(negotiation.proposed_price),
            local="A definir com as partes",
            imagem="/static/default-service.jpg",
            ficha_tecnica={
                "origin": "rule_engine",
                "negotiation_id": str(negotiation.id),
                "quantity": str(negotiation.quantity),
            },
            is_active=True,
        )
        self.db.add(service)
        generated["service_created"] = True

        event_base = datetime.utcnow()
        events = [
            ("visit", event_base + timedelta(days=2), "Visita técnica inicial"),
            ("delivery", event_base + timedelta(days=7), "Evento de entrega programado"),
        ]

        target_users = self._resolve_participant_users(negotiation)

        for event_type, due_at, label in events:
            for user in target_users:
                self.db.add(
                    AISuggestion(
                        user_id=user.id,
                        module="rule_engine",
                        suggestion_type=event_type,
                        title="Evento automático criado",
                        content=f"{label} para {due_at.strftime('%d/%m %H:%M')}.",
                        priority="high",
                        confidence=0.91,
                        meta_json={
                            "negotiation_id": str(negotiation.id),
                            "service_id": None,
                            "due_at": due_at.isoformat(),
                        },
                    )
                )
                generated["events_scheduled"] += 1

        self.db.flush()
        service_id = service.id

        for user in target_users:
            notification = Notification(
                user_id=user.id,
                notification_type="negotiation_closed_automation",
                title="Automação executada com sucesso",
                message=(
                    f"Negociação {negotiation.id} fechada: serviço {service_id} criado, "
                    "visita e entrega agendadas."
                ),
                resource_type="negotiation",
                resource_id=str(negotiation.id),
            )
            self.db.add(notification)

        self.db.commit()

        for user in target_users:
            await notification_manager.send_to_user(
                user.id,
                {
                    "event": "automation_completed",
                    "negotiation_id": str(negotiation.id),
                    "service_id": service_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            generated["notified_users"] += 1

        return generated

    def _resolve_participant_users(self, negotiation: Negotiation) -> list[User]:
        rows = (
            self.db.query(User)
            .join(Profile, Profile.user_id == User.id)
            .filter(
                Profile.id.in_([negotiation.buyer_profile_id, negotiation.seller_profile_id]),
            )
            .all()
        )

        if rows:
            return rows

        # Fallback para evitar quebra caso mapeamentos de perfil estejam incompletos.
        admin = self.db.query(User).filter(User.role == "admin").first()
        return [admin] if admin else []
