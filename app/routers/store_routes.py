from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, model_validator
from datetime import datetime, timezone, timedelta
from app.database.connection import get_db
from app.core.auth_middleware import get_current_user
from app.models.user import User
from app.models.store_models import Product, ProductStatus, Order, OrderItem, OrderStatus, QuoteRequest, QuoteRequestStatus
from app.services.payment_service import create_store_order_checkout_session, is_stripe_configured
import logging
import re
import unicodedata
import uuid

router = APIRouter(prefix="/store", tags=["Store"])
logger = logging.getLogger("store_routes")


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or uuid.uuid4().hex[:8]


def _get_or_create_open_cart(db: Session, user_id: int) -> Order:
    cart = (
        db.query(Order)
        .filter(
            Order.customer_id == user_id,
            Order.status == OrderStatus.PENDING,
            Order.payment_method == "cart_open",
        )
        .first()
    )
    if cart:
        return cart

    cart = Order(
        customer_id=user_id,
        status=OrderStatus.PENDING,
        payment_method="cart_open",
        total_amount=0.0,
    )
    db.add(cart)
    db.flush()
    return cart


def _recompute_order_total(order: Order) -> None:
    order.total_amount = round(sum(float(item.subtotal or 0) for item in order.items), 2)


def _order_status_value(order_status: OrderStatus | str) -> str:
    return order_status.value if isinstance(order_status, OrderStatus) else str(order_status)


def _store_checkout_urls(request: Request) -> tuple[str, str]:
    base_url = str(request.base_url).rstrip("/")
    success_url = f"{base_url}/store/orders?checkout=success"
    cancel_url = f"{base_url}/store/checkout?checkout=cancelled"
    return success_url, cancel_url


def _cart_payload(order: Order) -> dict:
    items_payload = []
    for item in order.items:
        image = None
        if isinstance(item.product.images, list) and item.product.images:
            image = item.product.images[0]

        items_payload.append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_slug": item.product.slug,
                "product_name": item.product.name,
                "unit_price": float(item.unit_price),
                "quantity": int(item.quantity),
                "subtotal": float(item.subtotal),
                "stock_quantity": int(item.product.stock_quantity or 0),
                "image": image,
            }
        )

    return {
        "order_id": order.id,
        "status": _order_status_value(order.status),
        "total_amount": float(order.total_amount or 0),
        "items": items_payload,
    }


class CartAddIn(BaseModel):
    product_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemUpdateIn(BaseModel):
    quantity: int = Field(..., ge=1)


class QuoteRequestIn(BaseModel):
    product_id: int
    quantity: float = Field(..., gt=0)
    target_price: float | None = Field(default=None, gt=0)
    message: str | None = Field(default=None, max_length=1500)


class CheckoutIn(BaseModel):
    payment_method: str = Field(default="pix")
    shipping_address: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_checkout(self):
        allowed_methods = {"pix", "boleto", "cartao", "transferencia"}
        method = (self.payment_method or "pix").strip().lower()
        if method not in allowed_methods:
            raise ValueError("Forma de pagamento invalida")

        if not isinstance(self.shipping_address, dict):
            raise ValueError("Endereco de entrega invalido")

        required_fields = ["name", "phone", "city", "state", "address", "zip"]
        normalized = {}
        for key in required_fields:
            value = str(self.shipping_address.get(key, "") or "").strip()
            if not value:
                raise ValueError(f"Campo obrigatorio ausente em shipping_address: {key}")
            normalized[key] = value

        normalized["state"] = normalized["state"].upper()
        if len(normalized["state"]) != 2:
            raise ValueError("UF invalida no endereco de entrega")

        phone_digits = re.sub(r"\D", "", normalized["phone"])
        if len(phone_digits) < 10:
            raise ValueError("Telefone invalido no endereco de entrega")

        zip_digits = re.sub(r"\D", "", normalized["zip"])
        if len(zip_digits) != 8:
            raise ValueError("CEP invalido no endereco de entrega")

        self.payment_method = method
        self.shipping_address = normalized
        return self


def _build_order_timeline(order: Order) -> list[dict]:
    base = order.created_at
    status_value = str(order.status)
    rank = {
        OrderStatus.PENDING: 0,
        OrderStatus.PAID: 1,
        OrderStatus.SHIPPED: 2,
        OrderStatus.DELIVERED: 3,
        OrderStatus.CANCELLED: -1,
    }

    current_rank = rank.get(order.status, 0)
    steps = [
        ("pending", "Pedido criado", "Seu pedido foi registrado no sistema.", timedelta(minutes=0), 0),
        ("paid", "Pagamento aprovado", "Pagamento confirmado e faturamento iniciado.", timedelta(minutes=5), 1),
        ("shipped", "Pedido em transporte", "Pedido separado e enviado para entrega.", timedelta(days=1), 2),
        ("delivered", "Pedido entregue", "Entrega concluida com sucesso.", timedelta(days=3), 3),
    ]

    timeline = []
    for code, title, description, offset, step_rank in steps:
        done = current_rank >= step_rank and order.status != OrderStatus.CANCELLED
        active = step_rank == current_rank and order.status != OrderStatus.CANCELLED
        eta = (base + offset).isoformat() if base else None
        timeline.append(
            {
                "code": code,
                "title": title,
                "description": description,
                "done": done,
                "active": active,
                "eta": eta,
            }
        )

    if order.status == OrderStatus.CANCELLED:
        timeline.append(
            {
                "code": "cancelled",
                "title": "Pedido cancelado",
                "description": "O pedido foi cancelado antes da conclusao da entrega.",
                "done": True,
                "active": True,
                "eta": order.updated_at.isoformat() if order.updated_at else None,
            }
        )

    return timeline

@router.post("/manage/create")
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    description: str = Form(...),
    stock: int = Form(...),
    brand: str = Form(...),
    unit: str = Form(...),
    package_size: str = Form(...),
    application_mode: str = Form(...),
    target_use: str = Form(...),
    origin: str = Form(...),
    crop_recommendation: str = Form(...),
    technical_sheet_url: str = Form(""),
    active_ingredient: str = Form(""),
    implement_compatibility: str = Form(""),
    ppe_size: str = Form(""),
    image_urls: str = Form(""),
    is_featured: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "supplier", "producer"]:
        raise HTTPException(status_code=403, detail="Acesso negado")
        
    slug = _slugify(f"{name}-{uuid.uuid4().hex[:6]}")
    
    image_list = [item.strip() for item in image_urls.split(",") if item.strip()]
    if not image_list:
        image_list = ["https://placehold.co/800x600/png?text=" + name.replace(" ", "+")]

    specs = {
        "Marca": brand,
        "Unidade": unit,
        "Embalagem": package_size,
        "Aplicacao": application_mode,
        "Uso indicado": target_use,
        "Origem": origin,
        "Culturas recomendadas": crop_recommendation,
    }
    if technical_sheet_url:
        specs["Ficha tecnica"] = technical_sheet_url
    if active_ingredient:
        specs["Principio ativo"] = active_ingredient
    if implement_compatibility:
        specs["Compatibilidade implementos"] = implement_compatibility
    if ppe_size:
        specs["Tamanho vestuario EPI"] = ppe_size

    new_product = Product(
        name=name,
        slug=slug,
        price=price,
        category_id=category_id,
        description=description,
        stock_quantity=stock,
        is_featured=is_featured,
        supplier_id=current_user.id,
        status=ProductStatus.PUBLISHED,
        images=image_list,
        specifications=specs,
    )
    
    db.add(new_product)
    db.commit()
    
    return RedirectResponse(url="/store/manage/dashboard?success=created", status_code=303)

# --- CART & CHECKOUT (SIMULATED) ---

@router.post("/checkout")
async def checkout(request: Request, current_user: User = Depends(get_current_user)):
    # In a real app, process payment here
    return RedirectResponse(url="/store?success=order_placed", status_code=303)


@router.post("/checkout/session")
async def create_store_checkout_session(
    payload: CheckoutIn,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = (
        db.query(Order)
        .filter(
            Order.customer_id == current_user.id,
            Order.status == OrderStatus.PENDING,
            Order.payment_method == "cart_open",
        )
        .first()
    )
    if not cart:
        raise HTTPException(status_code=400, detail="Carrinho nao encontrado")

    if not cart.items:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    if payload.payment_method != "cartao":
        raise HTTPException(
            status_code=400,
            detail="Checkout online no momento disponivel apenas para pagamento via cartao",
        )

    for item in cart.items:
        if int(item.quantity) > int(item.product.stock_quantity or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente para {item.product.name}",
            )

    if not is_stripe_configured():
        raise HTTPException(status_code=400, detail="Stripe nao configurado. Defina STRIPE_SECRET_KEY no .env")

    _recompute_order_total(cart)
    success_url, cancel_url = _store_checkout_urls(request)

    try:
        checkout = create_store_order_checkout_session(
            user=current_user,
            order=cart,
            payment_method=payload.payment_method,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Erro ao criar checkout da loja: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao iniciar checkout online")

    payment_details = dict(cart.payment_details or {})
    payment_details.update(
        {
            "provider": "stripe",
            "checkout_status": "pending",
            "selected_payment_method": payload.payment_method,
            "stripe_checkout_session_id": checkout["session_id"],
        }
    )

    cart.payment_method = "stripe_checkout_pending"
    cart.shipping_address = payload.shipping_address or {}
    cart.payment_details = payment_details

    db.commit()
    db.refresh(cart)

    return {
        "mode": "checkout",
        "order_id": cart.id,
        "status": _order_status_value(cart.status),
        "total_amount": float(cart.total_amount or 0),
        "session_id": checkout["session_id"],
        "checkout_url": checkout["checkout_url"],
        "message": "Checkout criado com sucesso",
    }


@router.get("/cart/items")
async def get_cart_items(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cart = _get_or_create_open_cart(db, current_user.id)
    db.commit()
    db.refresh(cart)
    return _cart_payload(cart)


@router.post("/cart/add")
async def add_to_cart(payload: CartAddIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    product = (
        db.query(Product)
        .filter(Product.id == payload.product_id, Product.status == ProductStatus.PUBLISHED)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    if product.stock_quantity <= 0:
        raise HTTPException(status_code=400, detail="Produto sem estoque no momento")

    cart = _get_or_create_open_cart(db, current_user.id)
    existing_item = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == cart.id, OrderItem.product_id == product.id)
        .first()
    )

    final_quantity = payload.quantity
    if existing_item:
        final_quantity += int(existing_item.quantity)

    if final_quantity > int(product.stock_quantity):
        raise HTTPException(status_code=400, detail="Quantidade solicitada maior que o estoque")

    if existing_item:
        existing_item.quantity = final_quantity
        existing_item.unit_price = float(product.price)
        existing_item.subtotal = round(float(product.price) * final_quantity, 2)
    else:
        db.add(
            OrderItem(
                order_id=cart.id,
                product_id=product.id,
                quantity=final_quantity,
                unit_price=float(product.price),
                subtotal=round(float(product.price) * final_quantity, 2),
            )
        )

    db.flush()
    db.refresh(cart)
    _recompute_order_total(cart)
    db.commit()
    db.refresh(cart)
    return _cart_payload(cart)


@router.patch("/cart/item/{item_id}")
async def update_cart_item(item_id: int, payload: CartItemUpdateIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(
            OrderItem.id == item_id,
            Order.customer_id == current_user.id,
            Order.status == OrderStatus.PENDING,
            Order.payment_method == "cart_open",
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do carrinho nao encontrado")

    if payload.quantity > int(item.product.stock_quantity or 0):
        raise HTTPException(status_code=400, detail="Quantidade acima do estoque disponivel")

    item.quantity = payload.quantity
    item.subtotal = round(float(item.unit_price) * payload.quantity, 2)
    _recompute_order_total(item.order)
    db.commit()
    db.refresh(item.order)
    return _cart_payload(item.order)


@router.delete("/cart/item/{item_id}")
async def remove_cart_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            OrderItem.id == item_id,
            Order.customer_id == current_user.id,
            Order.status == OrderStatus.PENDING,
            Order.payment_method == "cart_open",
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item do carrinho nao encontrado")

    order = item.order
    db.delete(item)
    db.flush()
    _recompute_order_total(order)
    db.commit()
    db.refresh(order)
    return _cart_payload(order)


@router.post("/quote/request")
async def request_volume_quote(payload: QuoteRequestIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    product = (
        db.query(Product)
        .filter(Product.id == payload.product_id, Product.status == ProductStatus.PUBLISHED)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Produto nao encontrado")

    quote = QuoteRequest(
        requester_id=current_user.id,
        supplier_id=product.supplier_id,
        product_id=product.id,
        requested_quantity=float(payload.quantity),
        unit=(product.specifications or {}).get("Unidade", "un"),
        target_price=float(payload.target_price) if payload.target_price else None,
        message=(payload.message or "").strip() or None,
        status=QuoteRequestStatus.PENDING,
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)

    return {
        "id": quote.id,
        "status": quote.status,
        "product_name": product.name,
        "requested_quantity": float(quote.requested_quantity),
    }


@router.get("/quote/my")
async def my_quote_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rows = (
        db.query(QuoteRequest)
        .join(Product, Product.id == QuoteRequest.product_id)
        .filter(QuoteRequest.requester_id == current_user.id)
        .order_by(QuoteRequest.created_at.desc())
        .all()
    )

    return {
        "quotes": [
            {
                "id": row.id,
                "status": row.status,
                "product_id": row.product_id,
                "product_slug": row.product.slug,
                "product_name": row.product.name,
                "requested_quantity": float(row.requested_quantity),
                "unit": row.unit,
                "target_price": float(row.target_price) if row.target_price else None,
                "message": row.message,
                "supplier_name": row.supplier.name if row.supplier else "Fornecedor",
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }


@router.post("/checkout/complete")
async def complete_checkout(payload: CheckoutIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cart = (
        db.query(Order)
        .filter(
            Order.customer_id == current_user.id,
            Order.status == OrderStatus.PENDING,
            Order.payment_method == "cart_open",
        )
        .first()
    )
    if not cart:
        raise HTTPException(status_code=400, detail="Carrinho nao encontrado")

    if not cart.items:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    for item in cart.items:
        if int(item.quantity) > int(item.product.stock_quantity or 0):
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente para {item.product.name}",
            )

    for item in cart.items:
        item.product.stock_quantity = int(item.product.stock_quantity or 0) - int(item.quantity)

    _recompute_order_total(cart)
    cart.status = OrderStatus.PAID
    cart.payment_method = payload.payment_method
    cart.shipping_address = payload.shipping_address or {}
    cart.payment_details = {
        "provider": "simulated",
        "paid_at": datetime.now(timezone.utc).isoformat(),
    }

    db.commit()
    db.refresh(cart)

    return {
        "order_id": cart.id,
        "status": _order_status_value(cart.status),
        "total_amount": float(cart.total_amount or 0),
        "message": "Compra finalizada com sucesso",
    }


@router.get("/orders/my")
async def my_orders(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    orders = (
        db.query(Order)
        .filter(
            Order.customer_id == current_user.id,
            Order.payment_method != "cart_open",
        )
        .order_by(Order.created_at.desc())
        .all()
    )

    payload = []
    for order in orders:
        payload.append(
            {
                "id": order.id,
                "status": _order_status_value(order.status),
                "total_amount": float(order.total_amount or 0),
                "payment_method": order.payment_method,
                "shipping_address": order.shipping_address or {},
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                "items": [
                    {
                        "id": item.id,
                        "product_name": item.product.name,
                        "product_slug": item.product.slug,
                        "quantity": int(item.quantity),
                        "unit_price": float(item.unit_price),
                        "subtotal": float(item.subtotal),
                    }
                    for item in order.items
                ],
                "timeline": _build_order_timeline(order),
            }
        )

    return {"orders": payload, "total": len(payload)}
