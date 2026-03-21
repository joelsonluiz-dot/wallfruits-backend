from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth_middleware import get_current_user
from app.database.connection import get_db
from app.models.service import Service
from app.models.user import User

router = APIRouter(prefix="/services", tags=["Services"])


AGRICULTURAL_SERVICE_CATEGORIES = [
    {"slug": "analise-solo", "label": "Análise e Correção de Solo"},
    {"slug": "plantio-semeadura", "label": "Plantio e Semeadura"},
    {"slug": "preparo-terreno", "label": "Preparo de Solo e Terreno"},
    {"slug": "irrigacao", "label": "Irrigação e Manejo Hídrico"},
    {"slug": "pulverizacao", "label": "Pulverização e Aplicação"},
    {"slug": "controle-pragas", "label": "Controle de Pragas e Doenças"},
    {"slug": "adubacao", "label": "Adubação e Nutrição de Plantas"},
    {"slug": "colheita", "label": "Colheita"},
    {"slug": "pos-colheita", "label": "Pós-colheita e Beneficiamento"},
    {"slug": "mecanizacao", "label": "Mecanização Agrícola"},
    {"slug": "drones", "label": "Serviços com Drone"},
    {"slug": "georreferenciamento", "label": "Georreferenciamento e Mapeamento"},
    {"slug": "assistencia-tecnica", "label": "Assistência Técnica Agronômica"},
    {"slug": "consultoria", "label": "Consultoria em Gestão Rural"},
    {"slug": "podas", "label": "Podas e Tratos Culturais"},
    {"slug": "silagem", "label": "Silagem e Forragens"},
    {"slug": "pastagem", "label": "Formação e Manejo de Pastagem"},
    {"slug": "cafe", "label": "Serviços para Cafeicultura"},
    {"slug": "fruticultura", "label": "Serviços para Fruticultura"},
    {"slug": "horticultura", "label": "Serviços para Horticultura"},
    {"slug": "avicultura", "label": "Serviços para Avicultura"},
    {"slug": "bovinocultura", "label": "Serviços para Bovinocultura"},
    {"slug": "suinocultura", "label": "Serviços para Suinocultura"},
    {"slug": "agricultura-precision", "label": "Agricultura de Precisão"},
]


DEFAULT_SERVICES = [
    {
        "titulo": "Analise de Solo",
        "descricao": "Diagnostico completo da fertilidade com recomendacao tecnica para correcao e produtividade.",
        "preco": "R$ 100",
        "local": "Petrolina - PE",
        "imagem": "https://images.unsplash.com/photo-1501004318641-b39e6451bec6?auto=format&fit=crop&w=1000&q=80",
        "ficha_tecnica": {"categoria": "Análise e Correção de Solo"},
    },
    {
        "titulo": "Pulverizacao com Drone",
        "descricao": "Aplicacao de defensivos com precisao em areas de dificil acesso e menor desperdicio.",
        "preco": "R$ 250",
        "local": "Juazeiro - BA",
        "imagem": "https://images.unsplash.com/photo-1472145246862-b24cf25c4a36?auto=format&fit=crop&w=1000&q=80",
        "ficha_tecnica": {"categoria": "Serviços com Drone"},
    },
    {
        "titulo": "Mapeamento de Irrigacao",
        "descricao": "Levantamento tecnico para distribuir agua com eficiencia e reduzir custos operacionais.",
        "preco": "R$ 180",
        "local": "Limoeiro do Norte - CE",
        "imagem": "https://images.unsplash.com/photo-1464226184884-fa280b87c399?auto=format&fit=crop&w=1000&q=80",
        "ficha_tecnica": {"categoria": "Irrigação e Manejo Hídrico"},
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

    provider_user = (
        db.query(User)
        .filter(User.is_active == True, User.role.in_(["admin", "supplier", "producer"]))
        .order_by(User.id.asc())
        .first()
    )

    for item in DEFAULT_SERVICES:
        db.add(
            Service(
                **item,
                is_active=True,
                created_by_user_id=provider_user.id if provider_user else None,
            )
        )
    db.commit()


def _service_payload(item: Service) -> dict:
    ficha = item.ficha_tecnica if isinstance(item.ficha_tecnica, dict) else {}
    created_by = item.created_by

    return {
        "id": str(item.id),
        "titulo": item.titulo,
        "descricao": item.descricao,
        "preco": item.preco,
        "local": item.local,
        "imagem": item.imagem,
        "ficha_tecnica": ficha,
        "is_active": bool(item.is_active),
        "created_by_user": {
            "id": created_by.id,
            "name": created_by.name,
            "profile_image": created_by.profile_image,
        }
        if created_by
        else None,
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


@router.get("/categories")
async def list_service_categories():
    return {
        "categories": AGRICULTURAL_SERVICE_CATEGORIES,
        "total": len(AGRICULTURAL_SERVICE_CATEGORIES),
    }


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