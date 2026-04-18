import json
import mimetypes
import uuid
import shutil
from pathlib import Path
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.core.auth_middleware import get_current_user, require_producer_or_admin
from app.models import User, Offer
from app.services.profile_service import ProfileService
from app.services.supabase_storage_service import (
    SupabaseStorageError,
    build_public_object_url,
    delete_object,
    storage_bucket,
    supabase_storage_enabled,
    try_parse_public_object_url,
    upload_public_object,
)

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"]
)

# Configurações de upload
UPLOAD_DIR = Path("uploads")
IMAGES_DIR = UPLOAD_DIR / "images"
PROFILES_DIR = UPLOAD_DIR / "profiles"
OFFERS_DIR = UPLOAD_DIR / "offers"
SERVICES_DIR = UPLOAD_DIR / "services"

# Criar diretórios se não existirem
for dir_path in [IMAGES_DIR, PROFILES_DIR, OFFERS_DIR, SERVICES_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Como os arquivos são versionados por UUID no nome, é seguro cachear por muito tempo.
PUBLIC_IMAGE_CACHE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365  # 1 ano
PUBLIC_IMAGE_CACHE_CONTROL = f"public, max-age={PUBLIC_IMAGE_CACHE_MAX_AGE_SECONDS}, immutable"


def _local_upload_url(kind: str, filename: str) -> str:
    return f"/api/uploads/{kind}/{filename}"


def _extract_local_upload_filename(kind: str, value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None

    if raw.startswith("http://") or raw.startswith("https://"):
        return None

    prefix = f"/api/uploads/{kind}/"
    if raw.startswith(prefix):
        candidate = raw[len(prefix) :]
        candidate = candidate.split("?", 1)[0].split("#", 1)[0]
        safe = Path(candidate).name
        if safe != candidate:
            return None
        return safe or None

    if raw.startswith("/"):
        return None

    safe = Path(raw).name
    if safe != raw:
        return None
    return safe or None


def _normalize_offer_image_ref(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("/"):
        return raw
    return _local_upload_url("offers", raw)


def _normalize_offer_images_list(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for item in values:
        value = _normalize_offer_image_ref(item)
        if value:
            normalized.append(value)
    return normalized


async def _upload_image(
    *,
    kind: str,
    file: UploadFile,
    destination_dir: Path,
    filename_prefix: str = "",
) -> tuple[str, str]:
    """Faz upload e retorna (filename, url_publica).

    - Se Supabase Storage estiver habilitado: salva em {kind}/{uuid.ext} no bucket e retorna URL pública.
    - Caso contrário: salva localmente e retorna URL via /api/uploads.
    """

    if not file.filename:
        raise HTTPException(400, "Arquivo inválido")

    extension = Path(file.filename).suffix
    safe_prefix = (filename_prefix or "").strip()
    if "/" in safe_prefix or "\\" in safe_prefix:
        raise HTTPException(400, "Prefixo de arquivo inválido")

    filename = f"{safe_prefix}{uuid.uuid4()}{extension}"

    if supabase_storage_enabled():
        bucket = storage_bucket()
        object_path = f"{kind}/{filename}"
        await file.seek(0)
        content = await file.read()
        try:
            await upload_public_object(
                bucket=bucket,
                object_path=object_path,
                content=content,
                content_type=file.content_type,
            )
        except SupabaseStorageError as exc:
            raise HTTPException(exc.status_code, exc.message)

        return filename, build_public_object_url(bucket=bucket, object_path=object_path)

    file_path = destination_dir / filename
    await file.seek(0)
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return filename, _local_upload_url(kind, filename)


async def _delete_known_image_refs(
    *,
    kind: str,
    image_ref: str | None,
    allowed_filename_prefixes: tuple[str, ...] | None = None,
) -> None:
    """Tenta deletar uma imagem anterior (local e/ou Storage) quando a ref é conhecida."""

    if not image_ref:
        return

    filename = _extract_local_upload_filename(kind, image_ref)
    if filename:
        if allowed_filename_prefixes and not filename.startswith(allowed_filename_prefixes):
            return

        local_dir = {
            "profiles": PROFILES_DIR,
            "offers": OFFERS_DIR,
            "services": SERVICES_DIR,
        }.get(kind)

        if local_dir is not None:
            local_path = local_dir / filename
            if local_path.exists():
                local_path.unlink()

        if supabase_storage_enabled():
            try:
                await delete_object(bucket=storage_bucket(), object_path=f"{kind}/{filename}")
            except SupabaseStorageError:
                pass

        return

    parsed = try_parse_public_object_url(image_ref)
    if parsed and supabase_storage_enabled():
        bucket, object_path = parsed
        try:
            if bucket == storage_bucket() and object_path.startswith(f"{kind}/"):
                leaf_name = Path(object_path).name
                if allowed_filename_prefixes and not leaf_name.startswith(allowed_filename_prefixes):
                    return
                await delete_object(bucket=bucket, object_path=object_path)
        except SupabaseStorageError:
            pass


def validate_image(file: UploadFile) -> bool:
    """Valida se o arquivo é uma imagem válida"""
    if not file.filename:
        return False

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False

    # Verificar content type
    if file.content_type and not file.content_type.startswith('image/'):
        return False

    # Verificar tamanho
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to start
    
    if file_size > MAX_FILE_SIZE:
        return False

    return True


def save_upload_file(upload_file: UploadFile, destination: Path) -> str:
    """Salva arquivo de upload e retorna o nome do arquivo"""
    file_extension = Path(upload_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"

    file_path = destination / unique_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return unique_filename


def _parse_offer_images(images_field: str | None) -> List[str]:
    if not images_field:
        return []

    try:
        parsed = json.loads(images_field)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


# -----------------------------
# UPLOAD PROFILE IMAGE
# -----------------------------
@router.post("/profile-image", response_model=dict)
async def upload_profile_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if not validate_image(file):
        raise HTTPException(400, "Arquivo inválido. Use apenas imagens JPG, PNG, GIF ou WebP até 5MB")

    # Remover imagem anterior (seja local, /api/uploads ou Supabase Storage)
    await _delete_known_image_refs(
        kind="profiles",
        image_ref=current_user.profile_image,
        allowed_filename_prefixes=(f"u{current_user.id}_", "public_"),
    )

    filename, url = await _upload_image(
        kind="profiles",
        file=file,
        destination_dir=PROFILES_DIR,
        filename_prefix=f"u{current_user.id}_",
    )
    # Armazenar URL (mantém compatibilidade com resolveAvatar/_normalize_profile_image)
    current_user.profile_image = url
    db.commit()

    return {
        "filename": filename,
        "url": url,
        "message": "Imagem de perfil atualizada com sucesso"
    }


# -----------------------------
# PUBLIC PROFILE IMAGE UPLOAD
# -----------------------------
@router.post("/public-profile-image", response_model=dict)
async def upload_public_profile_image(
    file: UploadFile = File(...),
):
    """Upload público usado no cadastro inicial da conta."""
    if not validate_image(file):
        raise HTTPException(400, "Arquivo inválido. Use apenas imagens JPG, PNG, GIF ou WebP até 5MB")

    filename, url = await _upload_image(
        kind="profiles",
        file=file,
        destination_dir=PROFILES_DIR,
        filename_prefix="public_",
    )

    return {
        "filename": filename,
        "url": url,
        "message": "Imagem enviada com sucesso"
    }


# -----------------------------
# UPLOAD OFFER IMAGES
# -----------------------------
@router.post("/offer-images", response_model=dict)
async def upload_offer_images(
    offer_id: UUID,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(require_producer_or_admin),
    db: Session = Depends(get_db)
):
    profile_service = ProfileService(db)

    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        raise HTTPException(404, "Oferta não encontrada")

    if not profile_service.is_offer_owner(offer=offer, user=current_user):
        raise HTTPException(403, "Apenas o dono da oferta pode enviar imagens")

    if len(files) > 10:
        raise HTTPException(400, "Máximo de 10 imagens por oferta")

    existing_images = _normalize_offer_images_list(_parse_offer_images(offer.images))
    if len(existing_images) + len(files) > 10:
        raise HTTPException(400, "A oferta pode ter no máximo 10 imagens")

    uploaded_files = []

    for file in files:
        if not validate_image(file):
            raise HTTPException(400, f"Arquivo '{file.filename}' inválido. Use apenas imagens JPG, PNG, GIF ou WebP até 5MB")

        filename, url = await _upload_image(kind="offers", file=file, destination_dir=OFFERS_DIR)
        uploaded_files.append({
            "filename": filename,
            "url": url,
            "original_name": file.filename
        })

    offer.images = json.dumps(existing_images + [item["url"] for item in uploaded_files])
    db.commit()

    return {
        "offer_id": str(offer.id),
        "uploaded_files": uploaded_files,
        "total_images": len(existing_images) + len(uploaded_files),
        "message": f"{len(uploaded_files)} imagens enviadas com sucesso"
    }


@router.post("/service-image", response_model=dict)
async def upload_service_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "supplier", "producer"]:
        raise HTTPException(403, "Apenas gestores podem enviar imagens de serviços")

    if not validate_image(file):
        raise HTTPException(400, "Arquivo inválido. Use apenas imagens JPG, PNG, GIF ou WebP até 5MB")

    filename, url = await _upload_image(kind="services", file=file, destination_dir=SERVICES_DIR)

    return {
        "filename": filename,
        "url": url,
        "message": "Imagem de serviço enviada com sucesso"
    }


# -----------------------------
# GET PROFILE IMAGE
# -----------------------------
@router.get("/profiles/{filename}")
async def get_profile_image(filename: str):

    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(400, "Nome de arquivo inválido")

    file_path = PROFILES_DIR / safe_name

    if not file_path.exists():
        if supabase_storage_enabled():
            try:
                bucket = storage_bucket()
                url = build_public_object_url(bucket=bucket, object_path=f"profiles/{safe_name}")
                return RedirectResponse(url=url, status_code=307, headers={"Cache-Control": PUBLIC_IMAGE_CACHE_CONTROL})
            except SupabaseStorageError as exc:
                raise HTTPException(exc.status_code, exc.message)

        raise HTTPException(404, "Imagem não encontrada")

    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=safe_name,
        headers={"Cache-Control": PUBLIC_IMAGE_CACHE_CONTROL},
    )


# -----------------------------
# GET OFFER IMAGE
# -----------------------------
@router.get("/offers/{filename}")
async def get_offer_image(filename: str):

    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(400, "Nome de arquivo inválido")

    file_path = OFFERS_DIR / safe_name

    if not file_path.exists():
        if supabase_storage_enabled():
            try:
                bucket = storage_bucket()
                url = build_public_object_url(bucket=bucket, object_path=f"offers/{safe_name}")
                return RedirectResponse(url=url, status_code=307, headers={"Cache-Control": PUBLIC_IMAGE_CACHE_CONTROL})
            except SupabaseStorageError as exc:
                raise HTTPException(exc.status_code, exc.message)

        raise HTTPException(404, "Imagem não encontrada")

    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=safe_name,
        headers={"Cache-Control": PUBLIC_IMAGE_CACHE_CONTROL},
    )


@router.get("/services/{filename}")
async def get_service_image(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(400, "Nome de arquivo inválido")

    file_path = SERVICES_DIR / safe_name

    if not file_path.exists():
        if supabase_storage_enabled():
            try:
                bucket = storage_bucket()
                url = build_public_object_url(bucket=bucket, object_path=f"services/{safe_name}")
                return RedirectResponse(url=url, status_code=307, headers={"Cache-Control": PUBLIC_IMAGE_CACHE_CONTROL})
            except SupabaseStorageError as exc:
                raise HTTPException(exc.status_code, exc.message)

        raise HTTPException(404, "Imagem não encontrada")

    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=safe_name,
        headers={"Cache-Control": PUBLIC_IMAGE_CACHE_CONTROL},
    )


# -----------------------------
# DELETE IMAGE
# -----------------------------
@router.delete("/images/{filename}", status_code=204)
async def delete_image(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    profile_service = ProfileService(db)


    # Verificar se a imagem pertence ao usuário
    # Esta é uma verificação básica - em produção seria mais robusta

    profile_deleted = False
    offer_deleted = False

    # Profile image (aceita DB armazenando filename ou URL) - com proteção para não apagar arquivos de terceiros.
    ref_filename: str | None = None
    if current_user.profile_image:
        ref_filename = _extract_local_upload_filename("profiles", current_user.profile_image)

        if ref_filename is None:
            parsed = try_parse_public_object_url(current_user.profile_image)
            if parsed and supabase_storage_enabled():
                bucket, object_path = parsed
                try:
                    if bucket == storage_bucket() and object_path == f"profiles/{filename}":
                        ref_filename = filename
                except SupabaseStorageError:
                    pass

    can_delete_profile = bool(
        ref_filename == filename
        and (
            filename.startswith(f"u{current_user.id}_")
            or filename.startswith("public_")
        )
    )

    if can_delete_profile:
        profile_path = PROFILES_DIR / filename
        if profile_path.exists():
            profile_path.unlink()
        current_user.profile_image = None
        profile_deleted = True

        if supabase_storage_enabled():
            try:
                await delete_object(bucket=storage_bucket(), object_path=f"profiles/{filename}")
            except SupabaseStorageError:
                pass

    # Offer images
    offer_candidates = {filename, _local_upload_url("offers", filename)}
    if supabase_storage_enabled():
        try:
            offer_candidates.add(
                build_public_object_url(bucket=storage_bucket(), object_path=f"offers/{filename}")
            )
        except SupabaseStorageError:
            pass

    linked_offers = db.query(Offer).filter(Offer.images.isnot(None)).all()
    for offer in linked_offers:
        if not profile_service.is_offer_owner(offer=offer, user=current_user):
            continue

        images = _parse_offer_images(offer.images)
        if not images:
            continue

        normalized_images = [_normalize_offer_image_ref(item) for item in images]
        kept = [item for item in normalized_images if item not in offer_candidates]

        if len(kept) != len(normalized_images):
            offer.images = json.dumps(kept) if kept else None
            offer_deleted = True

    if offer_deleted:
        offer_path = OFFERS_DIR / filename
        if offer_path.exists():
            offer_path.unlink()

        if supabase_storage_enabled():
            try:
                await delete_object(bucket=storage_bucket(), object_path=f"offers/{filename}")
            except SupabaseStorageError:
                pass

    if not (profile_deleted or offer_deleted):
        raise HTTPException(404, "Imagem não encontrada ou sem permissão para deletar")

    db.commit()