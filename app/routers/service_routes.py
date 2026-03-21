from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.service import Service
from app.models.user import User

router = APIRouter(prefix="/services", tags=["Services"])


DEFAULT_SERVICES = [
    {
        "titulo": "Analise de Solo",
        "descricao": "Diagnostico completo da fertilidade com recomendacao tecnica para correcao e produtividade.",
        "preco": "R$ 100",
        "local": "Petrolina - PE",
        "imagem": "https://images.unsplash.com/photo-1501004318641-b39e6451bec6?auto=format&fit=crop&w=1000&q=80",
    },
    {
        "titulo": "Pulverizacao com Drone",
        "descricao": "Aplicacao de defensivos com precisao em areas de dificil acesso e menor desperdicio.",
        "preco": "R$ 250",
        "local": "Juazeiro - BA",
        "imagem": "https://images.unsplash.com/photo-1472145246862-b24cf25c4a36?auto=format&fit=crop&w=1000&q=80",
    },
    {
        "titulo": "Mapeamento de Irrigacao",
        "descricao": "Levantamento tecnico para distribuir agua com eficiencia e reduzir custos operacionais.",
        "preco": "R$ 180",
        "local": "Limoeiro do Norte - CE",
        "imagem": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=1000&q=80",
    },
]


class ServiceIn(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=160)
    descricao: str = Field(..., min_length=10, max_length=4000)
    preco: str = Field(..., min_length=2, max_length=40)
    local: str = Field(..., min_length=2, max_length=140)
    imagem: str = Field(..., min_length=8, max_length=700)
    categoria: str | None = Field(default=None, max_length=80)
    unidade: str | None = Field(default=None, max_length=40)
    prazo_atendimento: str | None = Field(default=None, max_length=80)
    disponibilidade: str | None = Field(default=None, max_length=120)
    area_atuacao: str | None = Field(default=None, max_length=160)
    tempo_execucao: str | None = Field(default=None, max_length=80)
    equipamentos: str | None = Field(default=None, max_length=500)
    observacoes: str | None = Field(default=None, max_length=900)
    is_active: bool = True


class ServiceUpdateIn(BaseModel):
    titulo: str | None = Field(default=None, min_length=3, max_length=160)
    descricao: str | None = Field(default=None, min_length=10, max_length=4000)
    preco: str | None = Field(default=None, min_length=2, max_length=40)
    local: str | None = Field(default=None, min_length=2, max_length=140)
    imagem: str | None = Field(default=None, min_length=8, max_length=700)
    categoria: str | None = Field(default=None, max_length=80)
    unidade: str | None = Field(default=None, max_length=40)
    prazo_atendimento: str | None = Field(default=None, max_length=80)
    disponibilidade: str | None = Field(default=None, max_length=120)
    area_atuacao: str | None = Field(default=None, max_length=160)
    tempo_execucao: str | None = Field(default=None, max_length=80)
    equipamentos: str | None = Field(default=None, max_length=500)
    observacoes: str | None = Field(default=None, max_length=900)
    is_active: bool | None = None


FICHA_FIELDS = [
    "categoria",
    "unidade",
    "prazo_atendimento",
    "disponibilidade",
    "area_atuacao",
    "tempo_execucao",
    "equipamentos",
    "observacoes",
]


def _ensure_service_manager(current_user: User) -> None:
    if current_user.role not in ["admin", "supplier", "producer"]:
        raise HTTPException(status_code=403, detail="Acesso negado")


def _ensure_seed_services(db: Session) -> None:
    if db.query(Service).count() > 0:
        return

    for item in DEFAULT_SERVICES:
        db.add(Service(**item, is_active=True))
    db.commit()


def _service_payload(item: Service) -> dict:
    ficha = item.ficha_tecnica if isinstance(item.ficha_tecnica, dict) else {}
    return {
        "id": str(item.id),
        "titulo": item.titulo,
        "descricao": item.descricao,
        "preco": item.preco,
        "local": item.local,
        "imagem": item.imagem,
        "ficha_tecnica": ficha,
        "is_active": bool(item.is_active),
    }


def _build_ficha_from_payload(payload: ServiceIn | ServiceUpdateIn, *, current: dict | None = None) -> dict:
    base = dict(current or {})
    data = payload.model_dump(exclude_unset=True)

    for field in FICHA_FIELDS:
        if field not in data:
            continue

        raw = data.get(field)
        if raw is None:
            base.pop(field, None)
            continue

        value = str(raw).strip()
        if value:
            base[field] = value
        else:
            base.pop(field, None)

    return base


@router.get("")
async def list_services(db: Session = Depends(get_db)):
    _ensure_seed_services(db)

    services = (
        db.query(Service)
        .filter(Service.is_active == True)
        .order_by(Service.id.desc())
        .all()
    )
    payload = [_service_payload(item) for item in services]
    return {"services": payload, "total": len(payload)}


@router.get("/manage/list")
async def list_services_manage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_service_manager(current_user)
    _ensure_seed_services(db)

    services = db.query(Service).order_by(Service.id.desc()).all()
    payload = [_service_payload(item) for item in services]
    return {"services": payload, "total": len(payload)}


@router.get("/{service_id}")
async def get_service(service_id: int, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Servico nao encontrado")
    return _service_payload(service)


@router.post("")
async def create_service(
    payload: ServiceIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_service_manager(current_user)

    item = Service(
        titulo=payload.titulo.strip(),
        descricao=payload.descricao.strip(),
        preco=payload.preco.strip(),
        local=payload.local.strip(),
        imagem=payload.imagem.strip(),
        ficha_tecnica=_build_ficha_from_payload(payload),
        is_active=bool(payload.is_active),
        created_by_user_id=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _service_payload(item)


@router.patch("/{service_id}")
async def update_service(
    service_id: int,
    payload: ServiceUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_service_manager(current_user)

    item = db.query(Service).filter(Service.id == service_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Servico nao encontrado")

    update_data = payload.model_dump(exclude_unset=True)
    if "titulo" in update_data:
        item.titulo = str(update_data["titulo"]).strip()
    if "descricao" in update_data:
        item.descricao = str(update_data["descricao"]).strip()
    if "preco" in update_data:
        item.preco = str(update_data["preco"]).strip()
    if "local" in update_data:
        item.local = str(update_data["local"]).strip()
    if "imagem" in update_data:
        item.imagem = str(update_data["imagem"]).strip()
    if "is_active" in update_data:
        item.is_active = bool(update_data["is_active"])

    current_ficha = item.ficha_tecnica if isinstance(item.ficha_tecnica, dict) else {}
    item.ficha_tecnica = _build_ficha_from_payload(payload, current=current_ficha)

    db.commit()
    db.refresh(item)
    return _service_payload(item)


@router.delete("/{service_id}")
async def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_service_manager(current_user)

    item = db.query(Service).filter(Service.id == service_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Servico nao encontrado")

    item.is_active = False
    db.commit()
    db.refresh(item)
    return {"ok": True, "id": str(item.id)}