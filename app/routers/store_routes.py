from fastapi import APIRouter, Request, Depends, Form, File, UploadFile, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database.connection import get_db
from app.core.config import templates
from app.core.auth_middleware import get_current_user_optional, get_current_user
from app.models.user import User
from app.models.store_models import Product, ProductCategory, ProductStatus
from slugify import slugify
import uuid

router = APIRouter(prefix="/store", tags=["Store"])

# --- PUBLIC STORE ---

@router.get("/", response_class=HTMLResponse)
async def store_home(request: Request, category: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional)):
    
    query = db.query(Product).filter(Product.status == ProductStatus.PUBLISHED)
    
    if category:
        query = query.join(ProductCategory).filter(ProductCategory.slug == category)
        
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
        
    products = query.order_by(Product.is_featured.desc(), Product.created_at.desc()).all()
    categories = db.query(ProductCategory).filter(ProductCategory.is_active == True).all()
    
    return templates.TemplateResponse("store/index.html", {
        "request": request,
        "products": products,
        "categories": categories,
        "current_user": current_user,
        "search_query": q,
        "active_category": category
    })

@router.get("/product/{slug}", response_class=HTMLResponse)
async def product_detail(request: Request, slug: str, db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_current_user_optional)):
    product = db.query(Product).filter(Product.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
        
    related = db.query(Product).filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.status == ProductStatus.PUBLISHED
    ).limit(4).all()
    
    return templates.TemplateResponse("store/product_detail.html", {
        "request": request,
        "product": product,
        "related_products": related,
        "current_user": current_user
    })

# --- SUPPLIER DASHBOARD ---

@router.get("/manage/dashboard", response_class=HTMLResponse)
async def supplier_dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Check permissions (admins or suppliers)
    if current_user.role not in ["admin", "supplier", "producer"]:
        return RedirectResponse(url="/store", status_code=303)
        
    my_products = db.query(Product).filter(Product.supplier_id == current_user.id).all()
    categories = db.query(ProductCategory).all() # For creating new products
    
    return templates.TemplateResponse("store/dashboard.html", {
        "request": request,
        "products": my_products,
        "categories": categories,
        "current_user": current_user
    })

@router.post("/manage/create")
async def create_product(
    request: Request,
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

@router.get("/cart", response_class=HTMLResponse)
async def view_cart(request: Request, current_user: Optional[User] = Depends(get_current_user_optional)):
    return templates.TemplateResponse("store/cart.html", {"request": request, "current_user": current_user})

@router.post("/checkout")
async def checkout(request: Request, current_user: User = Depends(get_current_user)):
    # In a real app, process payment here
    return RedirectResponse(url="/store?success=order_placed", status_code=303)
