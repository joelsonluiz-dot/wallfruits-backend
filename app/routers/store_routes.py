from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database.connection import get_db
from app.core.auth_middleware import get_current_user
from app.models.user import User
from app.models.store_models import Product, ProductStatus, Order, OrderItem, OrderStatus, QuoteRequest, QuoteRequestStatus
import re
import unicodedata
import uuid

router = APIRouter(prefix="/store", tags=["Store"])


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
        "status": order.status,
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
    cart.payment_method = (payload.payment_method or "pix").strip().lower() or "pix"
    cart.shipping_address = payload.shipping_address or {}

    db.commit()
    db.refresh(cart)

    return {
        "order_id": cart.id,
        "status": cart.status,
        "total_amount": float(cart.total_amount or 0),
        "message": "Compra finalizada com sucesso",
    }
