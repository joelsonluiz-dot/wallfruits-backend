from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.core.auth_middleware import get_current_user
from app.models.user import User
from app.models.store_models import Product, ProductStatus
import re
import unicodedata
import uuid

router = APIRouter(prefix="/store", tags=["Store"])


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return slug or uuid.uuid4().hex[:8]

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
