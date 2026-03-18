from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from app.database.connection import get_db
from app.core.auth_middleware import get_current_user_optional, get_current_user
from app.models.user import User
from app.models.store_models import Product, ProductCategory, ProductStatus
from slugify import slugify
import uuid

router = APIRouter(prefix="/store", tags=["Store"])

@router.post("/manage/create")
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    category_id: int = Form(...),
    description: str = Form(""),
    stock: int = Form(0),
    is_featured: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "supplier", "producer"]:
        raise HTTPException(status_code=403, detail="Acesso negado")
        
    slug = slugify(f"{name}-{uuid.uuid4().hex[:6]}")
    
    new_product = Product(
        name=name,
        slug=slug,
        price=price,
        category_id=category_id,
        description=description,
        stock_quantity=stock,
        is_featured=is_featured,
        supplier_id=current_user.id,
        status=ProductStatus.PUBLISHED, # Auto publish for demo
        images=["https://placehold.co/600x400/png?text=" + name.replace(" ", "+")] # Placeholder image
    )
    
    db.add(new_product)
    db.commit()
    
    return RedirectResponse(url="/store/manage/dashboard?success=created", status_code=303)

# --- CART & CHECKOUT (SIMULATED) ---

@router.post("/checkout")
async def checkout(request: Request, current_user: User = Depends(get_current_user)):
    # In a real app, process payment here
    return RedirectResponse(url="/store?success=order_placed", status_code=303)
