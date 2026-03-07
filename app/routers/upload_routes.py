from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import uuid
import shutil
import json
import mimetypes
from pathlib import Path
from typing import List
from uuid import UUID

from app.database.connection import get_db
from app.core.auth_middleware import get_current_user, require_producer_or_admin
from app.models import User, Offer

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"]
)

# Configurações de upload
UPLOAD_DIR = Path("uploads")
IMAGES_DIR = UPLOAD_DIR / "images"
PROFILES_DIR = UPLOAD_DIR / "profiles"
OFFERS_DIR = UPLOAD_DIR / "offers"

# Criar diretórios se não existirem
for dir_path in [IMAGES_DIR, PROFILES_DIR, OFFERS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


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

    # Remover imagem anterior se existir
    if current_user.profile_image:
        old_path = PROFILES_DIR / current_user.profile_image
        if old_path.exists():
            old_path.unlink()

    # Salvar nova imagem
    filename = save_upload_file(file, PROFILES_DIR)
    current_user.profile_image = filename
    db.commit()

    return {
        "filename": filename,
        "url": f"/api/uploads/profiles/{filename}",
        "message": "Imagem de perfil atualizada com sucesso"
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

    offer = db.query(Offer).filter(Offer.id == offer_id).first()

    if not offer:
        raise HTTPException(404, "Oferta não encontrada")

    if offer.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Apenas o dono da oferta pode enviar imagens")

    if len(files) > 10:
        raise HTTPException(400, "Máximo de 10 imagens por oferta")

    existing_images = _parse_offer_images(offer.images)
    if len(existing_images) + len(files) > 10:
        raise HTTPException(400, "A oferta pode ter no máximo 10 imagens")

    uploaded_files = []

    for file in files:
        if not validate_image(file):
            raise HTTPException(400, f"Arquivo '{file.filename}' inválido. Use apenas imagens JPG, PNG, GIF ou WebP até 5MB")

        filename = save_upload_file(file, OFFERS_DIR)
        uploaded_files.append({
            "filename": filename,
            "url": f"/api/uploads/offers/{filename}",
            "original_name": file.filename
        })

    offer.images = json.dumps(existing_images + [item["filename"] for item in uploaded_files])
    db.commit()

    return {
        "offer_id": str(offer.id),
        "uploaded_files": uploaded_files,
        "total_images": len(existing_images) + len(uploaded_files),
        "message": f"{len(uploaded_files)} imagens enviadas com sucesso"
    }


# -----------------------------
# GET PROFILE IMAGE
# -----------------------------
@router.get("/profiles/{filename}")
async def get_profile_image(filename: str):

    file_path = PROFILES_DIR / filename

    if not file_path.exists():
        raise HTTPException(404, "Imagem não encontrada")

    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=filename
    )


# -----------------------------
# GET OFFER IMAGE
# -----------------------------
@router.get("/offers/{filename}")
async def get_offer_image(filename: str):

    file_path = OFFERS_DIR / filename

    if not file_path.exists():
        raise HTTPException(404, "Imagem não encontrada")

    media_type, _ = mimetypes.guess_type(str(file_path))

    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=filename
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

    # Verificar se a imagem pertence ao usuário
    # Esta é uma verificação básica - em produção seria mais robusta

    # Tentar deletar de ambos os diretórios
    profile_path = PROFILES_DIR / filename
    offer_path = OFFERS_DIR / filename

    deleted = False

    if profile_path.exists():
        # Verificar se é a imagem de perfil do usuário
        if current_user.profile_image == filename:
            profile_path.unlink()
            current_user.profile_image = None
            deleted = True

    if offer_path.exists():
        linked_offers = db.query(Offer).filter(Offer.images.isnot(None)).all()
        for offer in linked_offers:
            if offer.user_id != current_user.id and current_user.role != "admin":
                continue

            images = _parse_offer_images(offer.images)
            if filename in images:
                images.remove(filename)
                offer.images = json.dumps(images) if images else None
                deleted = True

        if deleted:
            offer_path.unlink()

    if not deleted:
        raise HTTPException(404, "Imagem não encontrada ou sem permissão para deletar")

    db.commit()