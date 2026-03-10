"""
Rotas de pagamento e assinatura via Stripe.
- POST /api/payment/checkout/{plan}    → gera URL de checkout
- POST /api/payment/intent             → cria PaymentIntent (avulso)
- POST /api/payment/webhook            → recebe eventos do Stripe
- GET  /api/payment/subscription       → status da assinatura atual
- DELETE /api/payment/subscription     → cancela assinatura (soft)
"""
import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.services.payment_service import (
    create_checkout_session,
    create_payment_intent,
    handle_stripe_webhook,
    is_stripe_configured,
)

router = APIRouter(prefix="/payment", tags=["payment"])
logger = logging.getLogger("payment_routes")

_VALID_PLANS = {"basic", "premium"}


# ── Checkout ────────────────────────────────────────────────────────

@router.post("/checkout/{plan}", status_code=status.HTTP_200_OK)
def start_checkout(
    plan: str,
    success_url: Optional[str] = Body(None, embed=True),
    cancel_url: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Gera uma URL de checkout do Stripe para assinar o plano escolhido.
    Planos disponíveis: **basic** | **premium**
    """
    if plan not in _VALID_PLANS:
        raise HTTPException(400, f"Plano inválido: '{plan}'. Use 'basic' ou 'premium'.")

    from app.core.config import settings
    s_url = success_url or f"{settings.FRONTEND_URL}/pagamento/sucesso"
    c_url = cancel_url or f"{settings.FRONTEND_URL}/pagamento/cancelado"

    try:
        result = create_checkout_session(
            user=current_user,
            plan=plan,
            success_url=s_url,
            cancel_url=c_url,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("Erro ao criar checkout: %s", exc, exc_info=True)
        raise HTTPException(500, "Erro ao processar pagamento.")

    return result


# ── PaymentIntent (pagamento avulso) ─────────────────────────────────

@router.post("/intent", status_code=status.HTTP_200_OK)
def create_intent(
    amount: Decimal = Body(..., gt=0),
    description: str = Body(..., min_length=3),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cria um PaymentIntent para pagamento avulso (ex: taxa de intermediação).
    Retorna `client_secret` para confirmar no frontend.
    """
    try:
        result = create_payment_intent(
            user=current_user,
            amount_brl=amount,
            description=description,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.error("Erro ao criar PaymentIntent: %s", exc, exc_info=True)
        raise HTTPException(500, "Erro ao processar pagamento.")

    return result


# ── Webhook Stripe ───────────────────────────────────────────────────

@router.post("/webhook", status_code=status.HTTP_200_OK, include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Endpoint de webhook do Stripe.
    Configure no painel do Stripe: POST /api/payment/webhook
    """
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(400, "Cabeçalho stripe-signature ausente.")
    try:
        event_type = handle_stripe_webhook(
            payload=payload,
            sig_header=stripe_signature,
            db=db,
        )
        return {"received": True, "event": event_type}
    except ValueError as exc:
        logger.warning("Webhook inválido: %s", exc)
        raise HTTPException(400, str(exc))


# ── Assinatura atual ─────────────────────────────────────────────────

@router.get("/subscription", status_code=status.HTTP_200_OK)
def get_my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna o plano de assinatura atual do usuário."""
    sub = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    if not sub:
        return {"plan_type": "none", "status": "inactive"}
    return {
        "plan_type": sub.plan_type,
        "status": sub.status,
        "auto_renew": sub.auto_renew,
        "start_date": sub.start_date,
        "end_date": sub.end_date,
    }


@router.delete("/subscription", status_code=status.HTTP_200_OK)
def cancel_my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancela a renovação automática da assinatura."""
    sub = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    if not sub or sub.status != "active":
        raise HTTPException(404, "Nenhuma assinatura ativa encontrada.")
    sub.auto_renew = False
    sub.status = "cancelled"
    db.commit()
    return {"message": "Assinatura cancelada. O acesso continua até o fim do período atual."}


# ── Info pública ─────────────────────────────────────────────────────

@router.get("/plans", status_code=status.HTTP_200_OK)
def list_plans():
    """Lista os planos disponíveis e se o Stripe está configurado."""
    return {
        "stripe_configured": is_stripe_configured(),
        "plans": [
            {
                "id": "basic",
                "name": "Básico",
                "description": "Publique ofertas e negocie no marketplace.",
                "features": ["Ofertas ilimitadas", "Negociações", "Reputação"],
            },
            {
                "id": "premium",
                "name": "Premium",
                "description": "Acesso completo com intermediação e sorteios.",
                "features": [
                    "Tudo do Básico",
                    "Intermediação com contrato",
                    "Participação em sorteios",
                    "Gamificação avançada",
                    "Suporte prioritário",
                ],
            },
        ],
    }
