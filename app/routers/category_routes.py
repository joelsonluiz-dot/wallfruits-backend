from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.models import Category, User
from app.schemas import CategoryCreate, CategoryResponse, CategoryUpdate
from app.core.auth_middleware import get_current_user, require_role

router = APIRouter(
    prefix="/categories",
    tags=["categories"]
)


# -----------------------------
# CREATE CATEGORY (ADMIN ONLY)
# -----------------------------
@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category: CategoryCreate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):

    # Verificar se slug já existe
    existing = db.query(Category).filter(Category.slug == category.slug).first()
    if existing:
        raise HTTPException(400, "Slug já existe")

    # Verificar categoria pai se fornecida
    if category.parent_id:
        parent = db.query(Category).filter(Category.id == category.parent_id).first()
        if not parent:
            raise HTTPException(404, "Categoria pai não encontrada")

    new_category = Category(**category.dict())
    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    return new_category


# -----------------------------
# GET ALL CATEGORIES
# -----------------------------
@router.get("", response_model=List[CategoryResponse])
@router.get("/", response_model=List[CategoryResponse])
def get_categories(
    db: Session = Depends(get_db),
    include_inactive: bool = False
):

    query = db.query(Category)

    if not include_inactive:
        query = query.filter(Category.is_active == True)

    categories = query.order_by(Category.name.asc()).all()

    return categories


# -----------------------------
# GET CATEGORY TREE
# -----------------------------
@router.get("/tree")
def get_category_tree(db: Session = Depends(get_db)):

    def build_tree(parent_id=None):
        categories = db.query(Category).filter(
            Category.parent_id == parent_id,
            Category.is_active == True
        ).order_by(Category.name.asc()).all()

        tree = []
        for cat in categories:
            node = {
                "id": cat.id,
                "name": cat.name,
                "slug": cat.slug,
                "description": cat.description,
                "icon": cat.icon,
                "color": cat.color,
                "offer_count": cat.offer_count,
                "subcategories": build_tree(cat.id)
            }
            tree.append(node)

        return tree

    return build_tree()


# -----------------------------
# GET CATEGORY
# -----------------------------
@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: int, db: Session = Depends(get_db)):

    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(404, "Categoria não encontrada")

    return category


# -----------------------------
# UPDATE CATEGORY (ADMIN ONLY)
# -----------------------------
@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):

    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(404, "Categoria não encontrada")

    # Verificar slug único se estiver sendo alterado
    if category_update.slug and category_update.slug != category.slug:
        existing = db.query(Category).filter(Category.slug == category_update.slug).first()
        if existing:
            raise HTTPException(400, "Slug já existe")

    # Verificar categoria pai se estiver sendo alterada
    if category_update.parent_id is not None and category_update.parent_id != category.parent_id:
        if category_update.parent_id:
            parent = db.query(Category).filter(Category.id == category_update.parent_id).first()
            if not parent:
                raise HTTPException(404, "Categoria pai não encontrada")
        # Evitar referência circular
        if category_update.parent_id == category_id:
            raise HTTPException(400, "Uma categoria não pode ser pai de si mesma")

    # Atualizar campos
    for field, value in category_update.dict(exclude_unset=True).items():
        setattr(category, field, value)

    db.commit()
    db.refresh(category)

    return category


# -----------------------------
# DELETE CATEGORY (ADMIN ONLY)
# -----------------------------
@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):

    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(404, "Categoria não encontrada")

    # Verificar se tem subcategorias
    subcategories = db.query(Category).filter(Category.parent_id == category_id).count()
    if subcategories > 0:
        raise HTTPException(400, "Não é possível excluir categoria com subcategorias")

    # Verificar se tem ofertas
    offers_count = category.offer_count
    if offers_count > 0:
        raise HTTPException(400, f"Não é possível excluir categoria com {offers_count} ofertas")

    db.delete(category)
    db.commit()


# -----------------------------
# UPDATE OFFER COUNTS
# -----------------------------
@router.post("/update-counts", status_code=status.HTTP_204_NO_CONTENT)
def update_category_counts(
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db)
):

    from sqlalchemy import func
    from app.models import Offer

    # Atualizar contadores de ofertas por categoria
    categories = db.query(Category).all()

    for category in categories:
        count = db.query(func.count(Offer.id)).filter(
            Offer.category == category.name,
            Offer.status == "active"
        ).scalar()

        category.offer_count = count

    db.commit()