from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.ai.business_os import build_orchestration_decision
from app.core.auth_middleware import get_current_user
from app.core.http_cache import set_detail_cache_headers
from app.database.connection import get_db
from app.models.service import Service
from app.models.service_request import ServiceRequest
from app.models.user import User
from app.schemas import ServiceRequestCreate, ServiceRequestResponse, ServiceRequestStatusUpdate
from app.services.ai_telemetry_service import AITelemetryService
from app.services.notification_service import create_notification
from app.services.subscription_policy_service import capabilities_for_user

router = APIRouter(prefix="/services", tags=["Services"])


AGRICULTURAL_SERVICE_CATEGORIES = [
    {"slug": "analise-solo", "label": "Solo"},
    {"slug": "plantio-semeadura", "label": "Plantio"},
    {"slug": "preparo-terreno", "label": "Preparo"},
    {"slug": "irrigacao", "label": "Irrigação"},
    {"slug": "pulverizacao", "label": "Pulverização"},
    {"slug": "controle-pragas", "label": "Pragas"},
    {"slug": "adubacao", "label": "Adubação"},
    {"slug": "colheita", "label": "Colheita"},
    {"slug": "pos-colheita", "label": "Pós-colheita"},
    {"slug": "mecanizacao", "label": "Mecanização"},
    {"slug": "drones", "label": "Drone"},
    {"slug": "georreferenciamento", "label": "Mapa"},
    {"slug": "assistencia-tecnica", "label": "Assistência"},
    {"slug": "consultoria", "label": "Consultoria"},
    {"slug": "podas", "label": "Podas"},
    {"slug": "silagem", "label": "Silagem"},
    {"slug": "pastagem", "label": "Pastagem"},
    {"slug": "cafe", "label": "Café"},
    {"slug": "fruticultura", "label": "Frutas"},
    {"slug": "horticultura", "label": "Horta"},
    {"slug": "avicultura", "label": "Aves"},
    {"slug": "bovinocultura", "label": "Bovinos"},
    {"slug": "suinocultura", "label": "Suínos"},
    {"slug": "agricultura-precision", "label": "Precisão"},
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
        "status": "disponível" if item.is_active else "indisponível",
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
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


def _service_request_payload(item: ServiceRequest) -> dict:
    return {
        "id": str(item.id),
        "service_id": item.service_id,
        "requester_user_id": item.requester_user_id,
        "provider_user_id": item.provider_user_id,
        "status": item.status,
        "priority": item.priority,
        "requested_date": item.requested_date.isoformat() if item.requested_date else None,
        "budget": float(item.budget) if item.budget is not None else None,
        "location": item.location,
        "notes": item.notes,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "service": {
            "id": item.service.id,
            "titulo": item.service.titulo,
            "local": item.service.local,
            "preco": item.service.preco,
        }
        if item.service
        else None,
        "requester": {
            "id": item.requester.id,
            "name": item.requester.name,
            "profile_image": item.requester.profile_image,
        }
        if item.requester
        else None,
        "provider": {
            "id": item.provider.id,
            "name": item.provider.name,
            "profile_image": item.provider.profile_image,
        }
        if item.provider
        else None,
    }


@router.get("")
async def list_services(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(120, ge=1, le=500),
):
    _ensure_seed_services(db)

    base_query = db.query(Service).filter(Service.is_active == True)
    total = base_query.count()

    services = (
        base_query
        .order_by(Service.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    payload = [_service_payload(item) for item in services]
    return {"services": payload, "total": total, "skip": skip, "limit": limit}


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


@router.get("/requests/my")
async def list_my_service_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    query = db.query(ServiceRequest).filter(ServiceRequest.requester_user_id == current_user.id)

    if status:
        query = query.filter(ServiceRequest.status == status)

    total = query.count()
    requests = query.order_by(ServiceRequest.created_at.desc()).offset(skip).limit(limit).all()
    payload = [_service_request_payload(item) for item in requests]

    return {"requests": payload, "total": total, "skip": skip, "limit": limit}


@router.get("/requests/provider-queue")
async def list_provider_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
):
    query = db.query(ServiceRequest).filter(ServiceRequest.provider_user_id == current_user.id)

    if status:
        query = query.filter(ServiceRequest.status == status)

    priority_rank = case(
        (ServiceRequest.priority == "high", 2),
        (ServiceRequest.priority == "normal", 1),
        else_=0,
    )

    total = query.count()
    requests = (
        query
        .order_by(priority_rank.desc(), ServiceRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    payload = []
    for index, item in enumerate(requests):
        req_data = _service_request_payload(item)
        created_at = item.created_at or datetime.utcnow()
        created_naive = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
        diff = datetime.utcnow() - created_naive
        hours_ago = max(0.0, diff.total_seconds() / 3600)

        if hours_ago < 1:
            time_str = f"{int(diff.total_seconds() / 60)} min atrás"
        elif hours_ago < 24:
            time_str = f"{int(hours_ago)} h atrás"
        else:
            days = int(hours_ago / 24)
            time_str = f"{days} dia{'s' if days > 1 else ''} atrás"

        priority_weight = 0.88 if item.priority == "high" else 0.68
        urgency = max(0.0, 1.0 - min(hours_ago / 24.0, 1.0))
        ai_score = round((priority_weight * 0.7) + (urgency * 0.3), 3)

        if hours_ago < 2:
            recommendation = "Responder nas próximas 2h"
        elif hours_ago < 8:
            recommendation = "Alto potencial nas próximas 8h"
        else:
            recommendation = "Priorizar ainda hoje"

        req_data["time_since_creation"] = time_str
        req_data["is_premium"] = item.priority == "high"
        req_data["ai_rank_score"] = ai_score
        req_data["ai_recommendation"] = recommendation
        req_data["rank_position"] = skip + index + 1
        payload.append(req_data)

    return {"requests": payload, "total": total, "skip": skip, "limit": limit}


@router.patch("/requests/{request_id}/status")
async def update_service_request_status(
    request_id: str,
    payload: ServiceRequestStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import uuid

    try:
        req_uuid = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de solicitação inválido")

    service_request = db.query(ServiceRequest).filter(ServiceRequest.id == req_uuid).first()
    if not service_request:
        raise HTTPException(status_code=404, detail="Solicitação de serviço não encontrada")

    new_status = payload.status.lower().strip()
    note_text = (payload.note or "").strip()
    scheduled_date = payload.scheduled_date

    valid_statuses = ["pending", "responded", "scheduled", "accepted", "rejected", "cancelled"]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status inválido. Valores válidos: {', '.join(valid_statuses)}")

    current_status = service_request.status
    transitions = {
        "pending": ["responded", "scheduled", "cancelled"],
        "responded": ["accepted", "rejected", "scheduled", "cancelled"],
        "scheduled": ["accepted", "rejected", "cancelled"],
        "accepted": [],
        "rejected": [],
        "cancelled": [],
    }

    if new_status not in transitions.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"Transição inválida de {current_status} para {new_status}",
        )

    if new_status in ["responded", "scheduled"]:
        if service_request.provider_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Apenas o fornecedor pode responder ou agendar")

    if new_status in ["accepted", "rejected", "cancelled"]:
        if service_request.requester_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Apenas o solicitante pode aceitar, recusar ou cancelar")

    if new_status == "scheduled" and scheduled_date is None:
        raise HTTPException(status_code=400, detail="Informe a data/horário do agendamento")

    service_request.status = new_status

    if scheduled_date is not None:
        service_request.requested_date = scheduled_date

    if note_text:
        stamp = datetime.utcnow().strftime("%d/%m/%Y %H:%M")
        note_entry = f"[{stamp}] {note_text}"
        service_request.notes = f"{service_request.notes}\n{note_entry}".strip() if service_request.notes else note_entry

    actor_name = current_user.name
    event_type = "service_request_updated"

    if new_status == "responded":
        create_notification(
            db,
            user_id=service_request.requester_user_id,
            actor_user_id=current_user.id,
            notification_type="service_request_response",
            title="Fornecedor respondeu",
            message=f"{actor_name} respondeu à sua solicitação de serviço.",
            resource_type="service_request",
            resource_id=str(service_request.id),
        )
        event_type = "service_request_responded"
    elif new_status == "scheduled":
        schedule_label = scheduled_date.strftime("%d/%m/%Y %H:%M") if scheduled_date else "Agendamento confirmado"
        create_notification(
            db,
            user_id=service_request.requester_user_id,
            actor_user_id=current_user.id,
            notification_type="service_request_scheduled",
            title="Solicitação agendada",
            message=f"{actor_name} agendou o serviço para {schedule_label}.",
            resource_type="service_request",
            resource_id=str(service_request.id),
        )
        event_type = "service_request_scheduled"
    elif new_status == "accepted":
        create_notification(
            db,
            user_id=service_request.provider_user_id,
            actor_user_id=current_user.id,
            notification_type="service_request_accepted",
            title="Solicitação aceita",
            message=f"{actor_name} aceitou sua oferta de serviço.",
            resource_type="service_request",
            resource_id=str(service_request.id),
        )
        event_type = "service_request_accepted"
    elif new_status == "rejected":
        create_notification(
            db,
            user_id=service_request.provider_user_id,
            actor_user_id=current_user.id,
            notification_type="service_request_rejected",
            title="Solicitação rejeitada",
            message=f"{actor_name} rejeitou sua oferta de serviço.",
            resource_type="service_request",
            resource_id=str(service_request.id),
        )
        event_type = "service_request_rejected"
    elif new_status == "cancelled":
        recipient_id = (
            service_request.provider_user_id
            if current_user.id == service_request.requester_user_id
            else service_request.requester_user_id
        )
        create_notification(
            db,
            user_id=recipient_id,
            actor_user_id=current_user.id,
            notification_type="service_request_cancelled",
            title="Solicitação cancelada",
            message=f"{actor_name} cancelou a solicitação de serviço.",
            resource_type="service_request",
            resource_id=str(service_request.id),
        )
        event_type = "service_request_cancelled"

    telemetry = AITelemetryService(db)
    decision = build_orchestration_decision(
        event_type=event_type,
        event_domain="atendimento",
        metadata={
            "service_request_id": str(service_request.id),
            "previous_status": current_status,
            "new_status": new_status,
            "actor_user_id": current_user.id,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
        },
        risk_level="low",
        risk_score=0.1,
    )

    telemetry.log_event(
        user_id=current_user.id,
        event_type=event_type,
        entity_type="service_request",
        entity_id=str(service_request.id),
        metadata={
            "previous_status": current_status,
            "new_status": new_status,
            "decision": decision,
        },
        event_domain="atendimento",
        event_source=f"/api/services/requests/{request_id}/status",
        idempotency_key=f"service-request-status:{request_id}:{new_status}:{current_user.id}",
        commit=True,
    )

    db.commit()
    db.refresh(service_request)

    return _service_request_payload(service_request)


@router.get("/{service_id}")
async def get_service(service_id: int, db: Session = Depends(get_db), response: Response = None):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Servico nao encontrado")
    if response is not None:
        set_detail_cache_headers(response, private=False)
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


@router.post("/{service_id}/requests", response_model=ServiceRequestResponse, status_code=201)
async def create_service_request(
    service_id: int,
    payload: ServiceRequestCreate,
    request_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service = db.query(Service).filter(Service.id == service_id, Service.is_active == True).first()
    if not service:
        raise HTTPException(status_code=404, detail="Servico nao encontrado ou indisponivel")

    service_capabilities = capabilities_for_user(db, request_user.id)
    service_monthly_limit = service_capabilities.get("service_request_monthly_limit")
    priority_boost = float(service_capabilities.get("service_request_priority_boost") or 1.0)
    priority = "high" if priority_boost >= 1.35 else "normal"

    if service_monthly_limit is not None:
        now_utc = datetime.now(timezone.utc)
        month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_requests = (
            db.query(func.count(ServiceRequest.id))
            .filter(
                ServiceRequest.requester_user_id == request_user.id,
                ServiceRequest.created_at >= month_start,
            )
            .scalar()
            or 0
        )

        if monthly_requests >= int(service_monthly_limit):
            telemetry = AITelemetryService(db)
            decision = build_orchestration_decision(
                event_type="service_request_denied",
                event_domain="atendimento",
                metadata={
                    "reason": "service_request_monthly_limit",
                    "service_id": service_id,
                    "requester_user_id": request_user.id,
                    "service_request_monthly_limit": service_monthly_limit,
                    "service_request_priority_boost": priority_boost,
                },
                risk_level="medium",
                risk_score=0.5,
            )

            telemetry.log_event(
                user_id=request_user.id,
                event_type="service_request_denied",
                entity_type="service_request",
                entity_id=None,
                metadata={
                    "reason": "service_request_monthly_limit",
                    "service_id": service_id,
                    "service_request_monthly_limit": service_monthly_limit,
                    "service_request_priority_boost": priority_boost,
                    "decision": decision,
                },
                event_domain="atendimento",
                event_source=f"/api/services/{service_id}/requests",
                idempotency_key=f"service-request-denied:{request_user.id}:{service_id}:{month_start.date()}",
                commit=True,
            )

            raise HTTPException(
                status_code=403,
                detail="Seus créditos de solicitação de serviço acabaram neste mês. Faça upgrade para continuar.",
            )

    if service.created_by_user_id and service.created_by_user_id == request_user.id:
        raise HTTPException(status_code=400, detail="Nao e possivel solicitar o proprio servico")

    provider_user_id = service.created_by_user_id

    telemetry = AITelemetryService(db)
    decision = build_orchestration_decision(
        event_type="service_request_created",
        event_domain="atendimento",
        metadata={
            "service_id": service_id,
            "requester_user_id": request_user.id,
            "provider_user_id": provider_user_id,
            "priority_boost": priority_boost,
        },
        risk_level="low" if priority_boost >= 1.35 else "medium",
        risk_score=0.15 if priority_boost >= 1.35 else 0.45,
    )

    request_row = ServiceRequest(
        service_id=service.id,
        requester_user_id=request_user.id,
        provider_user_id=provider_user_id,
        status="pending",
        priority=priority,
        requested_date=payload.requested_date,
        budget=payload.budget,
        location=(payload.location or service.local).strip() if (payload.location or service.local) else None,
        notes=(payload.notes or "").strip() or None,
    )
    db.add(request_row)
    db.flush()

    if provider_user_id is not None:
        create_notification(
            db,
            user_id=provider_user_id,
            actor_user_id=request_user.id,
            notification_type="service_request",
            title="Nova solicitação de serviço",
            message=f"{request_user.name} solicitou o serviço {service.titulo}.",
            resource_type="service_request",
            resource_id=str(request_row.id),
        )

    create_notification(
        db,
        user_id=request_user.id,
        actor_user_id=provider_user_id,
        notification_type="service_request",
        title="Solicitação registrada",
        message=f"Sua solicitação para {service.titulo} foi registrada com prioridade {priority}.",
        resource_type="service_request",
        resource_id=str(request_row.id),
    )

    telemetry.log_event(
        user_id=request_user.id,
        event_type="service_request_created",
        entity_type="service_request",
        entity_id=str(request_row.id),
        metadata={
            "service_id": service_id,
            "provider_user_id": provider_user_id,
            "priority": priority,
            "priority_boost": priority_boost,
            "decision": decision,
        },
        event_domain="atendimento",
        event_source=f"/api/services/{service_id}/requests",
        idempotency_key=f"service-request:{request_user.id}:{service_id}:{request_row.id}",
        commit=True,
    )

    db.commit()
    db.refresh(request_row)
    return _service_request_payload(request_row)


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