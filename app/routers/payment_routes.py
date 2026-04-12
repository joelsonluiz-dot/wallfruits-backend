"""
Rotas de pagamento e assinatura via Stripe.
- POST /api/payment/checkout/{plan}    → gera URL de checkout
- POST /api/payment/intent             → cria PaymentIntent (avulso)
- POST /api/payment/webhook            → recebe eventos do Stripe
- GET  /api/payment/subscription       → status da assinatura atual
- DELETE /api/payment/subscription     → cancela assinatura (soft)
"""
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.core.config import settings
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

_VALID_PLANS = {"basic", "pro", "premium"}
_VALID_PIX_KEY_TYPES = {"cpf", "cnpj", "email", "phone", "random"}
_VALID_PAYMENT_METHODS = {"card", "pix"}


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _mask_card_last4(last4: str | None) -> str | None:
    suffix = str(last4 or "").strip()
    if not suffix:
        return None
    return f"**** **** **** {suffix}"


def _mask_pix_key(key: str | None) -> str | None:
    raw = str(key or "").strip()
    if not raw:
        return None
    if len(raw) <= 6:
        return "*" * len(raw)
    return f"{raw[:3]}***{raw[-3:]}"


class BillingAddressIn(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    phone: str = Field(..., min_length=8, max_length=30)
    address_line1: str = Field(..., min_length=3, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str = Field(..., min_length=2, max_length=120)
    state: str = Field(..., min_length=2, max_length=10)
    zip_code: str = Field(..., min_length=8, max_length=20)
    country: str = Field(default="BR", min_length=2, max_length=60)

    @model_validator(mode="after")
    def normalize(self):
        phone_digits = _only_digits(self.phone)
        if len(phone_digits) < 10:
            raise ValueError("Telefone de cobranca invalido")

        zip_digits = _only_digits(self.zip_code)
        if len(zip_digits) != 8:
            raise ValueError("CEP de cobranca invalido")

        state = str(self.state or "").strip().upper()
        if len(state) != 2:
            raise ValueError("UF de cobranca invalida")

        self.phone = phone_digits
        self.zip_code = zip_digits
        self.state = state
        self.country = str(self.country or "BR").strip().upper() or "BR"
        self.address_line2 = (self.address_line2 or "").strip() or None
        return self


class PixPaymentIn(BaseModel):
    key_type: str = Field(default="email", max_length=20)
    key: str = Field(..., min_length=3, max_length=160)
    holder_name: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def normalize(self):
        normalized_type = str(self.key_type or "").strip().lower()
        if normalized_type not in _VALID_PIX_KEY_TYPES:
            raise ValueError("Tipo de chave PIX invalido")

        normalized_key = str(self.key or "").strip()
        if not normalized_key:
            raise ValueError("Chave PIX obrigatoria")

        self.key_type = normalized_type
        self.key = normalized_key
        self.holder_name = (self.holder_name or "").strip() or None
        return self


class CardPaymentIn(BaseModel):
    holder_name: str = Field(..., min_length=2, max_length=150)
    number: str | None = Field(default=None, min_length=12, max_length=25)
    exp_month: int = Field(..., ge=1, le=12)
    exp_year: int = Field(..., ge=2024, le=2100)
    brand: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def normalize(self):
        current_date = datetime.now(timezone.utc)
        if self.exp_year < current_date.year or (
            self.exp_year == current_date.year and self.exp_month < current_date.month
        ):
            raise ValueError("Cartao expirado")

        if self.number is not None:
            digits = _only_digits(self.number)
            if digits and not (13 <= len(digits) <= 19):
                raise ValueError("Numero de cartao invalido")

        self.number = (self.number or "").strip() or None
        self.brand = (self.brand or "").strip().lower() or None
        return self


class PaymentPreferencesIn(BaseModel):
    billing_address: BillingAddressIn
    pix: PixPaymentIn | None = None
    card: CardPaymentIn | None = None
    default_method: str = Field(default="card", max_length=20)
    use_for_subscriptions: bool = True

    @model_validator(mode="after")
    def validate_payload(self):
        method = str(self.default_method or "card").strip().lower()
        if method not in _VALID_PAYMENT_METHODS:
            raise ValueError("Metodo de pagamento padrao invalido")

        if method == "card" and self.card is None:
            raise ValueError("Informe dados de cartao para usar cartao como metodo padrao")

        if method == "pix" and self.pix is None:
            raise ValueError("Informe dados de PIX para usar PIX como metodo padrao")

        self.default_method = method
        return self


def _build_payment_preferences_payload(user: User) -> dict:
    card_last4 = str(user.payment_card_last4 or "").strip() or None
    pix_key = str(user.payment_pix_key or "").strip() or None
    default_method = str(user.payment_default_method or "card").strip().lower()
    if default_method not in _VALID_PAYMENT_METHODS:
        default_method = "card"

    return {
        "billing_address": {
            "full_name": user.payment_billing_name or user.name or "",
            "phone": user.payment_billing_phone or user.phone or "",
            "address_line1": user.payment_billing_address_line1 or "",
            "address_line2": user.payment_billing_address_line2 or "",
            "city": user.payment_billing_city or "",
            "state": user.payment_billing_state or "",
            "zip_code": user.payment_billing_zip or "",
            "country": user.payment_billing_country or "BR",
        },
        "pix": {
            "key_type": user.payment_pix_key_type or "email",
            "key": pix_key or "",
            "key_masked": _mask_pix_key(pix_key),
            "holder_name": user.payment_pix_holder_name or user.payment_billing_name or user.name or "",
        },
        "card": {
            "holder_name": user.payment_card_holder_name or user.payment_billing_name or user.name or "",
            "brand": user.payment_card_brand or "",
            "exp_month": int(user.payment_card_exp_month or 0),
            "exp_year": int(user.payment_card_exp_year or 0),
            "last4": card_last4 or "",
            "number_masked": _mask_card_last4(card_last4),
        },
        "default_method": default_method,
        "use_for_subscriptions": bool(user.payment_use_for_subscriptions),
        "is_ready_for_subscription_upgrade": bool(
            user.payment_use_for_subscriptions
            and user.payment_billing_name
            and user.payment_billing_address_line1
            and user.payment_billing_city
            and user.payment_billing_state
            and user.payment_billing_zip
            and user.payment_card_last4
            and user.payment_card_exp_month
            and user.payment_card_exp_year
        ),
        "updated_at": user.payment_updated_at,
    }


@router.get("/preferences", status_code=status.HTTP_200_OK)
def get_payment_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna as preferencias de pagamento do usuario para checkout e upgrades."""
    db_user = db.get(User, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")
    return _build_payment_preferences_payload(db_user)


@router.put("/preferences", status_code=status.HTTP_200_OK)
def update_payment_preferences(
    payload: PaymentPreferencesIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza preferencias de pagamento (cobranca, PIX e cartao mascarado)."""
    db_user = db.get(User, current_user.id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    billing = payload.billing_address

    db_user.payment_billing_name = billing.full_name
    db_user.payment_billing_phone = billing.phone
    db_user.payment_billing_address_line1 = billing.address_line1
    db_user.payment_billing_address_line2 = billing.address_line2
    db_user.payment_billing_city = billing.city
    db_user.payment_billing_state = billing.state
    db_user.payment_billing_zip = billing.zip_code
    db_user.payment_billing_country = billing.country

    db_user.payment_default_method = payload.default_method
    db_user.payment_use_for_subscriptions = bool(payload.use_for_subscriptions)

    if payload.pix is not None:
        db_user.payment_pix_key_type = payload.pix.key_type
        db_user.payment_pix_key = payload.pix.key
        db_user.payment_pix_holder_name = payload.pix.holder_name or billing.full_name

    if payload.card is not None:
        card_digits = _only_digits(payload.card.number)
        if card_digits:
            db_user.payment_card_last4 = card_digits[-4:]
        elif not db_user.payment_card_last4:
            raise HTTPException(status_code=400, detail="Informe o numero do cartao para o primeiro cadastro")

        db_user.payment_card_holder_name = payload.card.holder_name
        db_user.payment_card_brand = payload.card.brand
        db_user.payment_card_exp_month = int(payload.card.exp_month)
        db_user.payment_card_exp_year = int(payload.card.exp_year)

    db_user.payment_updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(db_user)
    return _build_payment_preferences_payload(db_user)


# ── Checkout ────────────────────────────────────────────────────────

@router.post("/checkout/{plan}", status_code=status.HTTP_200_OK)
def start_checkout(
    plan: str,
    success_url: Optional[str] = Body(None, embed=True),
    cancel_url: Optional[str] = Body(None, embed=True),
    billing_cycle: str = Body("monthly", embed=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Gera uma URL de checkout do Stripe para assinar o plano escolhido.
    Planos disponíveis: **basic** | **pro** | **premium**
    """
    if plan not in _VALID_PLANS:
        raise HTTPException(400, f"Plano inválido: '{plan}'. Use 'basic', 'pro' ou 'premium'.")

    from app.core.config import settings
    s_url = success_url or f"{settings.FRONTEND_URL}/pagamento/sucesso"
    c_url = cancel_url or f"{settings.FRONTEND_URL}/pagamento/cancelado"

    try:
        result = create_checkout_session(
            user=current_user,
            plan=plan,
            billing_cycle=billing_cycle,
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
                "description": "Entrada para operar no marketplace e validar resultados.",
                "monthly_price_brl": 0,
                "yearly_price_brl": 0,
                "yearly_savings_percent": 0,
                "yearly_checkout_enabled": False,
                "recommended": False,
                "target": "Primeiros passos e baixo volume",
                "features": [
                    "Ofertas e negociações no marketplace",
                    "Perfil público e reputação",
                    "Fluxos essenciais da plataforma",
                ],
                "cta": {
                    "label": "Começar agora",
                    "checkout_plan_id": "basic",
                },
            },
            {
                "id": "pro",
                "name": "Pro",
                "description": "Plano mais escolhido para quem quer escalar com previsibilidade.",
                "monthly_price_brl": 99,
                "yearly_price_brl": 990,
                "yearly_savings_percent": 17,
                "yearly_checkout_enabled": bool(settings.STRIPE_PRICE_PRO_YEARLY),
                "recommended": True,
                "target": "Produtores e compradores recorrentes",
                "features": [
                    "Tudo do Básico",
                    "Agenda Inteligente sem janela limitada",
                    "Gestão de carteira com mais capacidade",
                    "Suporte prioritário para operação",
                ],
                "cta": {
                    "label": "Assinar Pro",
                    "checkout_plan_id": "pro",
                },
            },
            {
                "id": "premium",
                "name": "Premium",
                "description": "Camada avançada para operação de alta escala e prioridade máxima.",
                "monthly_price_brl": 249,
                "yearly_price_brl": 2490,
                "yearly_savings_percent": 17,
                "yearly_checkout_enabled": bool(settings.STRIPE_PRICE_PREMIUM_YEARLY),
                "recommended": False,
                "target": "Operações de maior volume e complexidade",
                "features": [
                    "Tudo do Pro",
                    "Intermediação com contrato",
                    "Participação em sorteios",
                    "Gamificação avançada",
                    "Prioridade máxima no suporte",
                ],
                "cta": {
                    "label": "Assinar Premium",
                    "checkout_plan_id": "premium",
                },
            },
        ],
        "conversion": {
            "risk_reversal": "Sem fidelidade. Cancele quando quiser.",
            "checkout_security": "Pagamento processado via Stripe com fluxo seguro.",
            "positioning": "Recomendado manter 3 planos para maximizar conversão sem aumentar fricção.",
        },
    }
