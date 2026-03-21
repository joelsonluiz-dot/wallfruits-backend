"""
Serviço de pagamento via Stripe.
- Checkout Session para assinaturas e pagamentos avulsos
- Webhook para processar eventos do Stripe
- Stripe é acessível com login GitHub em dashboard.stripe.com
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.buyer_client import BuyerClientPolicy, BuyerClientSlotPurchase
from app.models.subscription import Subscription
from app.models.user import User
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.services.email_service import send_subscription_confirmation
from app.services.notification_service import create_notification

logger = logging.getLogger("payment_service")

_PLAN_NAMES = {
    "basic": "Básico",
    "premium": "Premium",
}

_PLAN_PRICES = {
    "basic": settings.STRIPE_PRICE_BASIC,
    "premium": settings.STRIPE_PRICE_PREMIUM,
}


def _stripe():
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def is_stripe_configured() -> bool:
    return bool(settings.STRIPE_SECRET_KEY)


# ── Checkout ────────────────────────────────────────────────────────

def create_checkout_session(
    *,
    user: User,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Cria uma Stripe Checkout Session para assinar um plano."""
    if not is_stripe_configured():
        raise ValueError("Stripe não configurado. Defina STRIPE_SECRET_KEY no .env")

    price_id = _PLAN_PRICES.get(plan)
    if not price_id:
        raise ValueError(f"Plano inválido: '{plan}'. Use 'basic' ou 'premium'")

    stripe = _stripe()
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user.email,
        client_reference_id=str(user.id),
        metadata={"user_id": str(user.id), "plan": plan},
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    return {"checkout_url": session.url, "session_id": session.id}


def create_client_slots_checkout_session(
    *,
    user: User,
    quantity: int,
    unit_price_brl: Decimal,
    success_url: str,
    cancel_url: str,
    extra_metadata: Optional[dict] = None,
) -> dict:
    """Cria Stripe Checkout Session para compra avulsa de slots de clientes."""
    if not is_stripe_configured():
        raise ValueError("Stripe não configurado. Defina STRIPE_SECRET_KEY no .env")

    if quantity <= 0:
        raise ValueError("Quantidade de slots inválida")

    unit_amount = int((unit_price_brl * 100).quantize(Decimal("1")))
    if unit_amount <= 0:
        raise ValueError("Valor por slot inválido")

    stripe = _stripe()
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        customer_email=user.email,
        client_reference_id=str(user.id),
        metadata={
            "user_id": str(user.id),
            "checkout_kind": "buyer_client_slots",
            "slot_quantity": str(quantity),
            "slot_unit_price": str(unit_price_brl),
            **(extra_metadata or {}),
        },
        line_items=[
            {
                "price_data": {
                    "currency": "brl",
                    "unit_amount": unit_amount,
                    "product_data": {
                        "name": "Slot de cliente adicional",
                        "description": "Habilita cadastro de cliente na carteira do comprador",
                    },
                },
                "quantity": quantity,
            }
        ],
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    return {"checkout_url": session.url, "session_id": session.id}


def create_payment_intent(
    *,
    user: User,
    amount_brl: Decimal,
    description: str,
    metadata: Optional[dict] = None,
) -> dict:
    """Cria um PaymentIntent (pagamento avulso em R$)."""
    if not is_stripe_configured():
        raise ValueError("Stripe não configurado")

    stripe = _stripe()
    intent = stripe.PaymentIntent.create(
        amount=int(amount_brl * 100),  # centavos
        currency="brl",
        description=description,
        receipt_email=user.email,
        metadata={"user_id": str(user.id), **(metadata or {})},
        payment_method_types=["card"],
    )
    return {
        "client_secret": intent.client_secret,
        "payment_intent_id": intent.id,
        "amount": float(amount_brl),
    }


# ── Webhook ─────────────────────────────────────────────────────────

def handle_stripe_webhook(*, payload: bytes, sig_header: str, db: Session) -> str:
    """Processa eventos do webhook Stripe. Retorna o tipo do evento tratado."""
    if not is_stripe_configured():
        raise ValueError("Stripe não configurado")

    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as exc:
        raise ValueError(f"Assinatura inválida: {exc}") from exc

    event_type = event["type"]
    data_obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _on_checkout_completed(data_obj, db)

    elif event_type == "customer.subscription.deleted":
        _on_subscription_cancelled(data_obj, db)

    elif event_type == "invoice.payment_failed":
        _on_payment_failed(data_obj, db)

    else:
        logger.debug("Stripe event ignorado: %s", event_type)

    return event_type


def _on_checkout_completed(session: dict, db: Session) -> None:
    metadata = session.get("metadata") or {}
    checkout_kind = metadata.get("checkout_kind")
    if checkout_kind == "buyer_client_slots":
        _on_client_slots_checkout_completed(session, db)
        return

    user_id = int(session.get("client_reference_id", 0))
    plan = metadata.get("plan", "basic")
    stripe_subscription_id = session.get("subscription")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error("Stripe checkout: user_id=%s não encontrado", user_id)
        return

    # Criar ou atualizar assinatura local
    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
    if sub:
        sub.plan_type = plan
        sub.status = "active"
    else:
        sub = Subscription(user_id=user_id, plan_type=plan, status="active", auto_renew=True)
        db.add(sub)

    db.commit()
    logger.info("Assinatura '%s' ativada para user_id=%s", plan, user_id)

    plan_name = _PLAN_NAMES.get(plan, plan)
    send_subscription_confirmation(
        to=user.email,
        name=user.name,
        plan=plan_name,
        amount="—",
    )


def _on_subscription_cancelled(sub_obj: dict, db: Session) -> None:
    customer_email = sub_obj.get("customer_email") or ""
    if not customer_email:
        return
    user = db.query(User).filter(User.email == customer_email).first()
    if not user:
        return
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if sub:
        sub.status = "cancelled"
        db.commit()
        logger.info("Assinatura cancelada via Stripe para user_id=%s", user.id)


def _on_payment_failed(invoice: dict, db: Session) -> None:
    customer_email = invoice.get("customer_email") or ""
    logger.warning("Pagamento falhou para e-mail: %s", customer_email)


def _on_client_slots_checkout_completed(session: dict, db: Session) -> None:
    metadata = session.get("metadata") or {}
    user_id = int(metadata.get("user_id") or session.get("client_reference_id") or 0)
    quantity = int(metadata.get("slot_quantity") or 0)
    purchase_id = int(metadata.get("purchase_id") or 0)
    checkout_session_id = session.get("id")
    payment_intent_id = session.get("payment_intent")

    if user_id <= 0 or quantity <= 0:
        logger.error("Checkout de slots inválido: user_id=%s quantity=%s", user_id, quantity)
        return

    purchase = None
    if purchase_id > 0:
        purchase = db.query(BuyerClientSlotPurchase).filter(BuyerClientSlotPurchase.id == purchase_id).first()
    if not purchase and checkout_session_id:
        purchase = (
            db.query(BuyerClientSlotPurchase)
            .filter(BuyerClientSlotPurchase.checkout_session_id == checkout_session_id)
            .first()
        )

    if purchase and purchase.status == "paid":
        logger.info("Checkout de slots já processado: purchase_id=%s", purchase.id)
        return

    policy = db.query(BuyerClientPolicy).filter(BuyerClientPolicy.user_id == user_id).first()
    if not policy:
        policy = BuyerClientPolicy(user_id=user_id)
        db.add(policy)
        db.flush()

    remaining_capacity = max(0, int(policy.max_clients or 0) - int(policy.slots_purchased or 0))
    applied_quantity = min(quantity, remaining_capacity)
    if applied_quantity <= 0:
        logger.warning(
            "Checkout de slots sem capacidade: user_id=%s quantity=%s max_clients=%s purchased=%s",
            user_id,
            quantity,
            policy.max_clients,
            policy.slots_purchased,
        )
        db.commit()
        return

    policy.slots_purchased = int(policy.slots_purchased or 0) + applied_quantity

    if purchase:
        purchase.status = "paid"
        purchase.paid_at = datetime.now(timezone.utc)
        purchase.checkout_session_id = purchase.checkout_session_id or checkout_session_id
        purchase.stripe_payment_intent_id = str(payment_intent_id or "") or purchase.stripe_payment_intent_id

    db.commit()

    create_notification(
        db,
        user_id=user_id,
        notification_type="buyer_client_slots",
        title="Slots de clientes liberados",
        message=f"Pagamento confirmado. {applied_quantity} slot(s) foram adicionados à sua carteira.",
        resource_type="buyer_client_policy",
        resource_id=str(user_id),
    )
    db.commit()
    logger.info("Slots creditados via checkout: user_id=%s quantity=%s", user_id, applied_quantity)
