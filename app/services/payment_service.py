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
from app.models.store_models import Order, OrderStatus
from app.models.subscription import Subscription
from app.models.user import User
from app.models.wallet import Wallet
from app.models.wallet_transaction import WalletTransaction
from app.services.email_service import send_subscription_confirmation
from app.services.notification_service import create_notification

logger = logging.getLogger("payment_service")

_PLAN_NAMES = {
    "basic": "Básico",
    "pro": "Pro",
    "premium": "Premium",
}

_PLAN_PRICES = {
    "basic": {
        "monthly": settings.STRIPE_PRICE_BASIC,
        "yearly": settings.STRIPE_PRICE_BASIC,
    },
    "pro": {
        "monthly": settings.STRIPE_PRICE_PRO,
        "yearly": settings.STRIPE_PRICE_PRO_YEARLY,
    },
    "premium": {
        "monthly": settings.STRIPE_PRICE_PREMIUM,
        "yearly": settings.STRIPE_PRICE_PREMIUM_YEARLY,
    },
}

_VALID_BILLING_CYCLES = {"monthly", "yearly"}


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
    billing_cycle: str = "monthly",
    success_url: str,
    cancel_url: str,
) -> dict:
    """Cria uma Stripe Checkout Session para assinar um plano."""
    if not is_stripe_configured():
        raise ValueError("Stripe não configurado. Defina STRIPE_SECRET_KEY no .env")

    if plan not in _PLAN_PRICES:
        raise ValueError(f"Plano inválido: '{plan}'. Use 'basic', 'pro' ou 'premium'")

    normalized_cycle = str(billing_cycle or "monthly").strip().lower()
    if normalized_cycle not in _VALID_BILLING_CYCLES:
        raise ValueError("Ciclo de cobrança inválido. Use 'monthly' ou 'yearly'")

    plan_prices = _PLAN_PRICES.get(plan) or {}
    price_id = plan_prices.get(normalized_cycle)
    if normalized_cycle == "yearly" and not price_id:
        raise ValueError(f"Plano '{plan}' ainda nao configurado no Stripe para ciclo '{normalized_cycle}'")

    if not price_id:
        price_id = plan_prices.get("monthly")

    if not price_id:
        raise ValueError(f"Plano '{plan}' ainda nao configurado no Stripe para ciclo '{normalized_cycle}'")

    success_suffix = "&session_id={CHECKOUT_SESSION_ID}" if "?" in success_url else "?session_id={CHECKOUT_SESSION_ID}"

    metadata = {
        "user_id": str(user.id),
        "plan": plan,
        "billing_cycle": normalized_cycle,
        "preferred_method": str(getattr(user, "payment_default_method", "") or "card")[:20],
    }

    billing_name = str(getattr(user, "payment_billing_name", "") or user.name or "").strip()
    billing_zip = str(getattr(user, "payment_billing_zip", "") or "").strip()
    pix_key_type = str(getattr(user, "payment_pix_key_type", "") or "").strip().lower()

    if billing_name:
        metadata["billing_name"] = billing_name[:120]
    if billing_zip:
        metadata["billing_zip"] = billing_zip[:20]
    if pix_key_type:
        metadata["pix_key_type"] = pix_key_type[:20]

    stripe = _stripe()
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        customer_email=user.email,
        client_reference_id=str(user.id),
        metadata=metadata,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + success_suffix,
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

    success_suffix = "&session_id={CHECKOUT_SESSION_ID}" if "?" in success_url else "?session_id={CHECKOUT_SESSION_ID}"

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
        success_url=success_url + success_suffix,
        cancel_url=cancel_url,
    )
    return {"checkout_url": session.url, "session_id": session.id}


def create_store_order_checkout_session(
    *,
    user: User,
    order: Order,
    payment_method: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    """Cria Stripe Checkout Session para pagamento de pedido da loja."""
    if not is_stripe_configured():
        raise ValueError("Stripe nao configurado. Defina STRIPE_SECRET_KEY no .env")

    if not order.items:
        raise ValueError("Pedido sem itens para checkout")

    requested_method = (payment_method or "cartao").strip().lower()
    method_map = {
        "cartao": ["card"],
    }
    stripe_method_types = method_map.get(requested_method)
    if not stripe_method_types:
        raise ValueError("Forma de pagamento nao suportada para checkout online")

    line_items = []
    for item in order.items:
        unit_amount = int((Decimal(str(item.unit_price or 0)) * 100).quantize(Decimal("1")))
        if unit_amount <= 0:
            raise ValueError(f"Item com valor invalido para checkout: item_id={item.id}")

        product_name = item.product.name if item.product else f"Produto {item.product_id}"
        line_items.append(
            {
                "price_data": {
                    "currency": "brl",
                    "unit_amount": unit_amount,
                    "product_data": {
                        "name": product_name,
                    },
                },
                "quantity": int(item.quantity),
            }
        )

    success_suffix = "&session_id={CHECKOUT_SESSION_ID}" if "?" in success_url else "?session_id={CHECKOUT_SESSION_ID}"

    stripe = _stripe()
    session = stripe.checkout.Session.create(
        payment_method_types=stripe_method_types,
        mode="payment",
        customer_email=user.email,
        client_reference_id=str(user.id),
        metadata={
            "user_id": str(user.id),
            "checkout_kind": "store_order",
            "order_id": str(order.id),
            "payment_method": requested_method,
        },
        line_items=line_items,
        success_url=success_url + success_suffix,
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
    if checkout_kind == "store_order":
        _on_store_order_checkout_completed(session, db)
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


def _on_store_order_checkout_completed(session: dict, db: Session) -> None:
    metadata = session.get("metadata") or {}
    user_id = int(metadata.get("user_id") or session.get("client_reference_id") or 0)
    order_id = int(metadata.get("order_id") or 0)
    checkout_session_id = session.get("id")
    payment_intent_id = session.get("payment_intent")

    if user_id <= 0 or order_id <= 0:
        logger.error("Checkout da loja invalido: user_id=%s order_id=%s", user_id, order_id)
        return

    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.customer_id == user_id)
        .first()
    )
    if not order:
        logger.error("Checkout da loja sem pedido local: user_id=%s order_id=%s", user_id, order_id)
        return

    payment_details = dict(order.payment_details or {})
    if (
        order.status == OrderStatus.PAID
        and payment_details.get("stripe_checkout_session_id") == checkout_session_id
    ):
        logger.info("Checkout da loja ja processado: order_id=%s", order_id)
        return

    if not order.items:
        logger.error("Pedido sem itens no webhook Stripe: order_id=%s", order_id)
        return

    for item in order.items:
        available = int(item.product.stock_quantity or 0)
        if int(item.quantity) > available:
            payment_details.update(
                {
                    "provider": "stripe",
                    "checkout_status": "stock_conflict",
                    "stripe_checkout_session_id": checkout_session_id,
                    "stripe_payment_intent_id": str(payment_intent_id or "") or None,
                    "manual_refund_required": True,
                }
            )
            order.payment_details = payment_details
            order.status = OrderStatus.CANCELLED
            db.commit()
            logger.error(
                "Pagamento confirmado sem estoque suficiente: order_id=%s item_id=%s required=%s available=%s",
                order_id,
                item.id,
                item.quantity,
                available,
            )
            return

    for item in order.items:
        item.product.stock_quantity = int(item.product.stock_quantity or 0) - int(item.quantity)

    payment_details.update(
        {
            "provider": "stripe",
            "checkout_status": "paid",
            "stripe_checkout_session_id": checkout_session_id,
            "stripe_payment_intent_id": str(payment_intent_id or "") or None,
            "stripe_payment_status": session.get("payment_status") or "paid",
            "paid_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    order.payment_method = "stripe"
    order.payment_details = payment_details
    order.status = OrderStatus.PAID
    db.commit()
    logger.info("Pedido da loja pago via Stripe: order_id=%s user_id=%s", order_id, user_id)
