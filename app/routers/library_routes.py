import logging
import re
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user, get_current_user_optional
from app.database.connection import get_db
from app.models.library_item import LibraryItem
from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import create_notification

router = APIRouter(prefix="/library", tags=["Library"])
logger = logging.getLogger("library_routes")


def _is_admin_user(user: User | None) -> bool:
    if not user:
        return False

    return str(user.role or "").strip().lower() == "admin" or bool(user.is_superuser)


def _assert_library_admin(user: User | None) -> None:
    if _is_admin_user(user):
        return

    raise HTTPException(status_code=403, detail="Somente admins podem publicar na biblioteca")


def _slugify_book_id(raw_id: str | None, *, fallback_title: str) -> str:
    base = str(raw_id or "").strip() or str(fallback_title or "").strip()
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    if not normalized:
        normalized = "leitura"
    return normalized[:180]


def _notify_admins_sync_issue(
    db: Session,
    *,
    current_user_id: int,
    issue_code: str,
    message: str,
) -> None:
    admins = (
        db.query(User)
        .filter(or_(User.role == "admin", User.is_superuser.is_(True)))
        .all()
    )
    if not admins:
        return

    for admin in admins:
        create_notification(
            db,
            user_id=admin.id,
            actor_user_id=current_user_id,
            notification_type="library_sync_issue",
            title="Falha de sincronizacao da biblioteca",
            message=message,
            resource_type="library_sync",
            resource_id=issue_code,
        )

    db.commit()


def _mark_admin_sync_issue_resolved(
    db: Session,
    *,
    issue_code: str,
) -> None:
    db.query(Notification).filter(
        Notification.notification_type == "library_sync_issue",
        Notification.resource_type == "library_sync",
        Notification.resource_id == issue_code,
        Notification.is_read.is_(False),
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()


class LibraryItemUpsertIn(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=180)
    title: str = Field(..., min_length=1, max_length=300)
    author: str | None = Field(default=None, max_length=180)
    category: str | None = Field(default=None, max_length=120)
    read_time: str | None = Field(default=None, max_length=40)
    cover: str | None = Field(default=None, max_length=700)
    text: str | None = None
    is_favorite: bool = False
    is_offline: bool = False


class LibraryItemBatchUpsertIn(BaseModel):
    items: list[LibraryItemUpsertIn] = Field(default_factory=list, max_length=300)


class LibraryCatalogUpsertIn(BaseModel):
    id: str | None = Field(default=None, min_length=1, max_length=180)
    title: str = Field(..., min_length=2, max_length=300)
    author: str | None = Field(default=None, max_length=180)
    category: str | None = Field(default=None, max_length=120)
    read_time: str | None = Field(default=None, max_length=40)
    cover: str | None = Field(default=None, max_length=700)
    text: str = Field(..., min_length=20)


def _apply_item_update(item: LibraryItem, payload: LibraryItemUpsertIn) -> None:
    item.title = payload.title.strip()
    item.author = (payload.author or "").strip() or None
    item.category = (payload.category or "").strip() or None
    item.read_time = (payload.read_time or "").strip() or None
    item.cover = (payload.cover or "").strip() or None
    item.text = payload.text if payload.text is not None else item.text
    item.is_favorite = bool(payload.is_favorite)
    item.is_offline = bool(payload.is_offline)


def _item_payload(item: LibraryItem) -> dict:
    return {
        "id": item.book_id,
        "title": item.title,
        "author": item.author,
        "category": item.category,
        "read_time": item.read_time,
        "cover": item.cover,
        "text": item.text,
        "is_favorite": bool(item.is_favorite),
        "is_offline": bool(item.is_offline),
    }


def _catalog_item_payload(item: LibraryItem) -> dict:
    payload = _item_payload(item)
    payload["is_favorite"] = False
    payload["is_offline"] = False
    payload["published_by_user_id"] = item.user_id
    payload["is_published"] = True
    return payload


def _apply_catalog_item_update(item: LibraryItem, payload: LibraryCatalogUpsertIn) -> None:
    item.title = payload.title.strip()
    item.author = (payload.author or "").strip() or None
    item.category = (payload.category or "").strip() or None
    item.read_time = (payload.read_time or "").strip() or None
    item.cover = (payload.cover or "").strip() or None
    item.text = payload.text.strip()
    item.is_favorite = False
    item.is_offline = False


@router.get("/catalog")
async def list_library_catalog(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    del current_user
    admin_items = (
        db.query(LibraryItem)
        .join(User, User.id == LibraryItem.user_id)
        .filter(or_(User.role == "admin", User.is_superuser.is_(True)))
        .order_by(LibraryItem.updated_at.desc().nullslast(), LibraryItem.id.desc())
        .all()
    )

    deduped_items: dict[str, dict] = {}
    for row in admin_items:
        key = str(row.book_id or "").strip()
        if not key or key in deduped_items:
            continue
        deduped_items[key] = _catalog_item_payload(row)

    items = list(deduped_items.values())
    return {"items": items, "total": len(items)}


@router.post("/catalog")
async def publish_library_catalog_item(
    payload: LibraryCatalogUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_library_admin(current_user)

    book_id = _slugify_book_id(payload.id, fallback_title=payload.title)
    item = (
        db.query(LibraryItem)
        .join(User, User.id == LibraryItem.user_id)
        .filter(LibraryItem.book_id == book_id, or_(User.role == "admin", User.is_superuser.is_(True)))
        .order_by(LibraryItem.updated_at.desc().nullslast(), LibraryItem.id.desc())
        .first()
    )

    if not item:
        item = LibraryItem(user_id=current_user.id, book_id=book_id)
        db.add(item)

    _apply_catalog_item_update(item, payload)
    db.commit()
    db.refresh(item)
    return _catalog_item_payload(item)


@router.put("/catalog/{book_id}")
async def update_library_catalog_item(
    book_id: str,
    payload: LibraryCatalogUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_library_admin(current_user)

    item = (
        db.query(LibraryItem)
        .join(User, User.id == LibraryItem.user_id)
        .filter(LibraryItem.book_id == str(book_id), or_(User.role == "admin", User.is_superuser.is_(True)))
        .order_by(LibraryItem.updated_at.desc().nullslast(), LibraryItem.id.desc())
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="Leitura nao encontrada no catalogo")

    _apply_catalog_item_update(item, payload)
    db.commit()
    db.refresh(item)
    return _catalog_item_payload(item)


@router.delete("/catalog/{book_id}")
async def delete_library_catalog_item(
    book_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _assert_library_admin(current_user)

    items = (
        db.query(LibraryItem)
        .join(User, User.id == LibraryItem.user_id)
        .filter(LibraryItem.book_id == str(book_id), or_(User.role == "admin", User.is_superuser.is_(True)))
        .all()
    )

    if not items:
        return {"ok": True, "deleted": False, "removed": 0}

    for item in items:
        db.delete(item)

    db.commit()
    return {"ok": True, "deleted": True, "removed": len(items)}


@router.get("/items")
async def list_library_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = (
        db.query(LibraryItem)
        .filter(LibraryItem.user_id == current_user.id)
        .order_by(LibraryItem.updated_at.desc().nullslast(), LibraryItem.id.desc())
        .all()
    )
    return {"items": [_item_payload(item) for item in items], "total": len(items)}


@router.put("/items/{book_id}")
async def upsert_library_item(
    book_id: str,
    payload: LibraryItemUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(LibraryItem)
        .filter(LibraryItem.user_id == current_user.id, LibraryItem.book_id == str(book_id))
        .first()
    )

    if not item:
        item = LibraryItem(user_id=current_user.id, book_id=str(book_id))
        db.add(item)

    _apply_item_update(item, payload)

    db.commit()
    db.refresh(item)
    return _item_payload(item)


@router.post("/items/batch")
async def batch_upsert_library_items(
    payload: LibraryItemBatchUpsertIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started_at = perf_counter()
    input_count = len(payload.items)

    try:
        if not payload.items:
            logger.info(
                "library_batch_sync user_id=%s input_count=0 created=0 updated=0 returned=0 duration_ms=%.2f",
                current_user.id,
                (perf_counter() - started_at) * 1000,
            )
            return {"ok": True, "saved": 0, "items": []}

        saved_items: dict[str, dict] = {}
        created_count = 0
        updated_count = 0

        for raw in payload.items:
            book_id = str(getattr(raw, "id", "") or "").strip()
            if not book_id:
                # Compatibilidade: quando vier por alias externo sem id no model, usa título+autor.
                title = (raw.title or "Livro").strip()
                author = (raw.author or "Autor").strip()
                book_id = f"{title}-{author}"

            item = (
                db.query(LibraryItem)
                .filter(LibraryItem.user_id == current_user.id, LibraryItem.book_id == book_id)
                .first()
            )

            if not item:
                item = LibraryItem(user_id=current_user.id, book_id=book_id)
                db.add(item)
                created_count += 1
            else:
                updated_count += 1

            _apply_item_update(item, raw)

        db.commit()

        items = (
            db.query(LibraryItem)
            .filter(LibraryItem.user_id == current_user.id)
            .order_by(LibraryItem.updated_at.desc().nullslast(), LibraryItem.id.desc())
            .all()
        )

        for item in items:
            if item.book_id not in saved_items:
                saved_items[item.book_id] = _item_payload(item)

        logger.info(
            "library_batch_sync user_id=%s input_count=%s created=%s updated=%s returned=%s duration_ms=%.2f",
            current_user.id,
            input_count,
            created_count,
            updated_count,
            len(saved_items),
            (perf_counter() - started_at) * 1000,
        )

        issue_code = f"batch_sync_error_user_{current_user.id}"
        try:
            _mark_admin_sync_issue_resolved(db, issue_code=issue_code)
        except Exception:
            db.rollback()
            logger.exception(
                "library_batch_sync_mark_resolved_failed user_id=%s issue_code=%s",
                current_user.id,
                issue_code,
            )

        return {"ok": True, "saved": len(saved_items), "items": list(saved_items.values())}

    except Exception as exc:
        db.rollback()

        issue_code = f"batch_sync_error_user_{current_user.id}"
        alert_message = (
            f"Usuario {current_user.id} encontrou falha no sync em lote da biblioteca "
            f"(input_count={input_count}). Erro: {str(exc)[:400]}"
        )

        try:
            _notify_admins_sync_issue(
                db,
                current_user_id=current_user.id,
                issue_code=issue_code,
                message=alert_message,
            )
        except Exception:
            db.rollback()
            logger.exception(
                "library_batch_sync_admin_notify_failed user_id=%s issue_code=%s",
                current_user.id,
                issue_code,
            )

        logger.exception(
            "library_batch_sync_failed user_id=%s input_count=%s duration_ms=%.2f",
            current_user.id,
            input_count,
            (perf_counter() - started_at) * 1000,
        )
        raise HTTPException(status_code=500, detail="Falha ao sincronizar biblioteca")


@router.delete("/items/{book_id}")
async def delete_library_item(
    book_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(LibraryItem)
        .filter(LibraryItem.user_id == current_user.id, LibraryItem.book_id == str(book_id))
        .first()
    )
    if not item:
        return {"ok": True, "deleted": False}

    db.delete(item)
    db.commit()
    return {"ok": True, "deleted": True}
