from uuid import UUID
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.core.config import settings
from app.services.file_validator import validate_file_content
from app.services.contract_retention import cleanup_orphan_files
from app.core.domain_permissions import enforce_negotiation_policy
from app.database.connection import get_db
from app.models.intermediation_contract_version import IntermediationContractVersion
from app.models.user import User
from app.schemas.negotiation_schema import (
    IntermediationContractResponse,
    IntermediationContractVersionResponse,
    IntermediationContractUpsert,
    IntermediationRequestCreate,
    IntermediationRequestReviewUpdate,
    IntermediationRequestResponse,
    NegotiationCounterOffer,
    NegotiationCreate,
    NegotiationMessageCreate,
    NegotiationMessageResponse,
    NegotiationResponse,
    NegotiationStatusUpdate,
    NegotiationUpdate,
)
from app.services.negotiation_service import NegotiationService

router = APIRouter(prefix="/negotiations", tags=["negotiations"])

CONTRACTS_DIR = Path("uploads") / "contracts"
CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)


def _http_error_from_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    normalized = detail.lower()

    if (
        "nao encontrada" in normalized
        or "nao encontrado" in normalized
        or "não encontrada" in normalized
        or "não encontrado" in normalized
    ):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    if "não participa" in normalized or "nao participa" in normalized:
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)

    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _allowed_contract_extensions() -> set[str]:
    return {
        f".{item.lower().lstrip('.')}"
        for item in settings.ALLOWED_CONTRACT_EXTENSIONS
        if item and str(item).strip()
    }


def _validate_contract_upload(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo de contrato sem nome")

    ext = Path(file.filename).suffix.lower()
    if ext not in _allowed_contract_extensions():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Extensão de contrato inválida",
        )

    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > settings.MAX_CONTRACT_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo de contrato excede tamanho máximo permitido",
        )

    # Validação de magic bytes — impede arquivos disfarçados
    header_bytes = file.file.read(16)
    file.file.seek(0)
    if not validate_file_content(header_bytes, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conteúdo do arquivo não corresponde à extensão declarada",
        )


@router.post("/", response_model=NegotiationResponse, status_code=status.HTTP_201_CREATED)
def create_negotiation(
    payload: NegotiationCreate,
    _policy_guard: None = Depends(enforce_negotiation_policy),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        return service.create_negotiation(
            user=current_user,
            offer_id=payload.offer_id,
            proposed_price=payload.proposed_price,
            quantity=payload.quantity,
            is_intermediated=payload.is_intermediated,
            initial_message=payload.initial_message,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get(
    "/{negotiation_id}/intermediation",
    response_model=list[IntermediationRequestResponse],
)
def list_negotiation_intermediation_requests(
    negotiation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        return service.list_intermediation_for_negotiation(
            negotiation=negotiation,
            user=current_user,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get("/intermediation/requests", response_model=list[IntermediationRequestResponse])
def list_all_intermediation_requests_admin(
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern="^(em_validacao|validada|rejeitada)$",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito")

    service = NegotiationService(db)
    return service.list_intermediation_requests(status=status_filter, skip=skip, limit=limit)


@router.patch(
    "/intermediation/requests/{request_id}",
    response_model=IntermediationRequestResponse,
)
def review_intermediation_request_admin(
    request_id: UUID,
    payload: IntermediationRequestReviewUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito")

    service = NegotiationService(db)
    try:
        request = service.get_intermediation_request_or_fail(request_id)
        return service.review_intermediation_request(
            request=request,
            reviewed_by_user=current_user,
            new_status=payload.status,
            review_notes=payload.review_notes,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get(
    "/intermediation/requests/{request_id}/contract",
    response_model=IntermediationContractResponse,
)
def get_intermediation_contract(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)
    try:
        request = service.get_intermediation_request_or_fail(request_id)
        return service.get_intermediation_contract(request=request, user=current_user)
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get(
    "/intermediation/requests/{request_id}/contract/versions",
    response_model=list[IntermediationContractVersionResponse],
)
def list_intermediation_contract_versions(
    request_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)
    try:
        request = service.get_intermediation_request_or_fail(request_id)
        return service.list_intermediation_contract_versions(
            request=request,
            user=current_user,
            skip=skip,
            limit=limit,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.post(
    "/intermediation/requests/{request_id}/contract",
    response_model=IntermediationContractResponse,
)
def upsert_intermediation_contract(
    request_id: UUID,
    payload: IntermediationContractUpsert,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)
    try:
        request = service.get_intermediation_request_or_fail(request_id)
        return service.upsert_intermediation_contract(
            request=request,
            user=current_user,
            file_url=payload.file_url,
            file_name=payload.file_name,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.post(
    "/intermediation/requests/{request_id}/contract/upload",
    response_model=IntermediationContractResponse,
)
def upload_intermediation_contract_file(
    request_id: UUID,
    file: UploadFile = File(...),
    notes: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)
    stored_path: Path | None = None

    try:
        request = service.get_intermediation_request_or_fail(request_id)
        _validate_contract_upload(file)

        ext = Path(file.filename or "").suffix.lower()
        stored_filename = f"{uuid.uuid4()}{ext}"
        stored_path = CONTRACTS_DIR / stored_filename

        with stored_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_url = f"/api/negotiations/intermediation/requests/{request_id}/contract/file/{stored_filename}"
        contract = service.upsert_intermediation_contract(
            request=request,
            user=current_user,
            file_url=file_url,
            file_name=file.filename,
            notes=notes,
        )

        return contract
    except ValueError as exc:
        if stored_path and stored_path.exists():
            stored_path.unlink()
        raise _http_error_from_value_error(exc)
    except HTTPException:
        if stored_path and stored_path.exists():
            stored_path.unlink()
        raise
    except Exception:
        if stored_path and stored_path.exists():
            stored_path.unlink()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha ao salvar contrato")
    finally:
        file.file.close()


@router.get(
    "/intermediation/requests/{request_id}/contract/file/{stored_filename}",
)
def download_intermediation_contract_file(
    request_id: UUID,
    stored_filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    safe_name = Path(stored_filename).name
    if safe_name != stored_filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nome de arquivo inválido")

    service = NegotiationService(db)
    try:
        request = service.get_intermediation_request_or_fail(request_id)
        contract = service.get_intermediation_contract(request=request, user=current_user)
    except ValueError as exc:
        raise _http_error_from_value_error(exc)

    expected_url = f"/api/negotiations/intermediation/requests/{request_id}/contract/file/{safe_name}"
    if contract.file_url != expected_url:
        historical_match = (
            db.query(IntermediationContractVersion.id)
            .filter(
                IntermediationContractVersion.contract_id == contract.id,
                IntermediationContractVersion.file_url == expected_url,
            )
            .first()
        )
        if not historical_match:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de contrato não encontrado")

    file_path = CONTRACTS_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de contrato não encontrado")

    return FileResponse(
        path=file_path,
        media_type="application/octet-stream",
        filename=contract.file_name or safe_name,
    )


@router.post(
    "/admin/contracts/cleanup-orphans",
    tags=["admin"],
)
def admin_cleanup_orphan_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin" and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    stats = cleanup_orphan_files(db)
    return stats


@router.get("/my", response_model=list[NegotiationResponse])
def list_my_negotiations(
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern="^(open|countered|accepted|rejected|canceled|completed)$",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        return service.list_for_user(
            user=current_user,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get("/{negotiation_id}", response_model=NegotiationResponse)
def get_negotiation(
    negotiation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        return service.get_for_user(negotiation_id=negotiation_id, user=current_user)
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.put("/{negotiation_id}", response_model=NegotiationResponse)
def update_negotiation(
    negotiation_id: UUID,
    payload: NegotiationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        return service.update_negotiation(
            negotiation=negotiation,
            user=current_user,
            proposed_price=payload.proposed_price,
            quantity=payload.quantity,
            is_intermediated=payload.is_intermediated,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.delete("/{negotiation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_negotiation(
    negotiation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        service.delete_negotiation(negotiation=negotiation, user=current_user)
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.patch("/{negotiation_id}/status", response_model=NegotiationResponse)
def update_negotiation_status(
    negotiation_id: UUID,
    payload: NegotiationStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        return service.update_status(
            negotiation=negotiation,
            user=current_user,
            new_status=payload.status,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.post("/{negotiation_id}/counter", response_model=NegotiationResponse)
def submit_counter_offer(
    negotiation_id: UUID,
    payload: NegotiationCounterOffer,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        return service.counter_offer(
            negotiation=negotiation,
            user=current_user,
            proposed_price=payload.proposed_price,
            quantity=payload.quantity,
            message=payload.message,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.post(
    "/{negotiation_id}/messages",
    response_model=NegotiationMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_negotiation_message(
    negotiation_id: UUID,
    payload: NegotiationMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        return service.add_message(
            negotiation=negotiation,
            user=current_user,
            message_text=payload.message_text,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.get("/{negotiation_id}/messages", response_model=list[NegotiationMessageResponse])
def list_negotiation_messages(
    negotiation_id: UUID,
    mark_as_read: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        return service.list_messages(
            negotiation=negotiation,
            user=current_user,
            mark_as_read=mark_as_read,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)


@router.post(
    "/{negotiation_id}/intermediation",
    response_model=IntermediationRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_intermediation_request(
    negotiation_id: UUID,
    payload: IntermediationRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = NegotiationService(db)

    try:
        negotiation = service.get_for_user(negotiation_id=negotiation_id, user=current_user)
        return service.request_intermediation(
            negotiation=negotiation,
            user=current_user,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc)
