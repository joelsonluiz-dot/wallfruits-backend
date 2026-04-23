"""App principal da API WallFruits com startup e observabilidade robustos."""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import logging
import os
import re
import sys
from threading import Lock
import time
import unicodedata
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import auth_routes
from app.cache.redis_client import check_redis_connection, delete_cache, get_cache, set_cache
from app.core.auth_middleware import get_current_user_optional
from app.core.config import settings
from app.core.domain_enums import SubscriptionPlanType, SubscriptionStatus
from app.database.connection import (
    check_database_connection,
    init_db,
    SessionLocal,
    wait_for_database_ready,
    get_db,
)
from sqlalchemy.orm import Session, joinedload
from app.models import Category, Favorite, Message, Offer, Review, Subscription, Transaction, User
from app.routers import (
    ai_routes,
    store_routes,
    service_routes,
    library_routes,
    buyer_client_routes,
    category_routes,
    dashboard_routes,
    favorite_routes,
    gamification_routes,
    growth_routes,
    message_routes,
    negotiation_routes,
    notification_routes,
    offer_routes,
    payment_routes,
    profile_routes,
    report_routes,
    reputation_routes,
    review_routes,
    social_routes,
    community_routes,
    notification_ws_routes,
    transaction_routes,
    upload_routes,
    wallet_routes,
)
from app.services.agenda_proactive_service import emit_predictive_notifications_for_all_users


os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/app.log"),
    ],
)

logger = logging.getLogger("wallfruits_api")
logger.info("Starting WallFruits API v%s", settings.API_VERSION)

_rate_limit_storage: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()
_sensitive_rate_limit_paths = (
    "/api/auth/",
    "/api/messages",
    "/api/community/posts",
    "/api/offers",
)
_non_cacheable_paths = (
    "/api/auth/",
    "/api/messages",
    "/api/notifications",
    "/api/transactions",
    "/api/wallet",
    "/api/checkout",
    "/api/dashboard",
    "/api/admin",
    "/api/upload",
    "/api/store/cart",
    "/api/store/orders",
    "/api/store/quote",
    "/store",
    "/api/messages/conversations",
    "/api/messages/thread/",
    "/api/social/users/search",
)
_cacheable_content_types = (
    "text/html",
    "application/json",
    "application/problem+json",
)
_metrics_lock = Lock()
_request_metrics = {
    "total": 0,
    "status_2xx": 0,
    "status_4xx": 0,
    "status_5xx": 0,
    "rate_limited": 0,
    "duration_ms_total": 0.0,
}


def _client_identifier(request: Request) -> str:
    if settings.RATE_LIMIT_TRUST_PROXY_HEADERS:
        xff = request.headers.get("X-Forwarded-For", "").strip()
        if xff:
            return xff.split(",")[0].strip()

    return (request.client.host if request.client else "unknown").strip() or "unknown"


def _is_sensitive_rate_limit_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in _sensitive_rate_limit_paths)


def _consume_rate_limit(request: Request) -> tuple[bool, int]:
    if not settings.RATE_LIMIT_ENABLED or request.method == "OPTIONS":
        return True, 0

    path = request.url.path
    bucket_max = (
        settings.RATE_LIMIT_SENSITIVE_MAX_REQUESTS
        if _is_sensitive_rate_limit_path(path)
        else settings.RATE_LIMIT_MAX_REQUESTS
    )
    window = float(settings.RATE_LIMIT_WINDOW_SECONDS)
    now = time.monotonic()
    client = _client_identifier(request)
    bucket_name = "sensitive" if _is_sensitive_rate_limit_path(path) else "default"
    bucket_key = f"{client}:{bucket_name}"

    with _rate_limit_lock:
        queue = _rate_limit_storage[bucket_key]
        while queue and (now - queue[0]) > window:
            queue.popleft()

        if len(queue) >= bucket_max:
            retry_after = max(1, int(window - (now - queue[0]))) if queue else int(window)
            return False, retry_after

        queue.append(now)
        return True, 0


def _timed_check(check_fn) -> tuple[bool, str, float]:
    started = time.perf_counter()
    ok, detail = check_fn()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return ok, detail, elapsed_ms


def _request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _error_payload(message: Any, code: str, request: Request) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
        },
        "request_id": _request_id_from(request),
    }


def _is_cacheable_path(path: str) -> bool:
    return not any(path.startswith(prefix) for prefix in _non_cacheable_paths)


def _merge_vary(existing: str | None, values: list[str]) -> str:
    merged: list[str] = []
    for raw in [existing or "", ",".join(values)]:
        for item in str(raw).split(","):
            key = item.strip()
            if key and key.lower() not in {entry.lower() for entry in merged}:
                merged.append(key)
    return ", ".join(merged) if merged else "Accept-Encoding, Authorization, Cookie"


def _build_cache_control_header(request: Request) -> str:
    has_auth = bool(request.headers.get("Authorization"))
    has_cookie = bool(request.headers.get("Cookie"))
    if has_auth or has_cookie:
        return "private, max-age=0, must-revalidate"

    return (
        f"public, max-age={settings.HTTP_PUBLIC_CACHE_MAX_AGE_SECONDS}, "
        f"stale-while-revalidate={settings.HTTP_PUBLIC_CACHE_STALE_WHILE_REVALIDATE_SECONDS}"
    )


def _is_cacheable_response(request: Request, response: JSONResponse | Response) -> bool:
    if request.method != "GET":
        return False
    if response.status_code != 200:
        return False
    if not _is_cacheable_path(request.url.path):
        return False

    content_type = str(response.headers.get("content-type", "")).lower()
    return any(content_type.startswith(prefix) for prefix in _cacheable_content_types)


async def _read_response_body(response: Response) -> bytes:
    body = bytearray()
    async for chunk in response.body_iterator:
        body.extend(chunk)
    return bytes(body)


@asynccontextmanager
async def lifespan(app_obj: FastAPI):
    app_obj.state.startup_ok = False
    app_obj.state.startup_error = None
    app_obj.state.started_at = datetime.now(timezone.utc)

    try:
        wait_for_database_ready()
        init_db()
        app_obj.state.startup_ok = True
        logger.info("Startup concluído com sucesso")
    except Exception as exc:
        app_obj.state.startup_error = str(exc)
        logger.error("Falha no startup: %s", exc, exc_info=True)
        if settings.STRICT_STARTUP:
            raise

    async def _agenda_predictive_worker() -> None:
        interval = max(30, int(settings.AGENDA_PREDICTIVE_WORKER_INTERVAL_SECONDS))
        logger.info("Agenda predictive worker iniciado (intervalo=%ss)", interval)

        while True:
            try:
                db = SessionLocal()
                try:
                    result = emit_predictive_notifications_for_all_users(db)
                    if result.get("predictive_notifications_created", 0) > 0:
                        db.commit()
                        logger.info(
                            "Agenda predictive worker: users=%s notifications=%s",
                            result.get("users_scanned", 0),
                            result.get("predictive_notifications_created", 0),
                        )
                finally:
                    db.close()
            except Exception as exc:
                logger.error("Falha no agenda predictive worker: %s", exc, exc_info=True)

            await asyncio.sleep(interval)

    async def _business_os_marketing_worker() -> None:
        interval = max(60, int(settings.BUSINESS_OS_MARKETING_WORKER_INTERVAL_SECONDS))
        logger.info("Business OS marketing worker iniciado (intervalo=%ss)", interval)

        while True:
            try:
                db = SessionLocal()
                try:
                    admin_actor = (
                        db.query(User)
                        .filter(User.is_active.is_(True), (User.role == "admin") | (User.is_superuser.is_(True)))
                        .order_by(User.is_superuser.desc(), User.id.asc())
                        .first()
                    )

                    if admin_actor is None:
                        logger.info("Business OS marketing worker sem admin ativo para atuar")
                    else:
                        payload = ai_routes._build_business_os_marketing_funnel_payload(
                            db=db,
                            days=int(settings.BUSINESS_OS_MARKETING_WORKER_WINDOW_DAYS),
                            min_segment_signals=int(settings.BUSINESS_OS_MARKETING_WORKER_MIN_SEGMENT_SIGNALS),
                        )
                        signals = list(payload.get("signals") or [])

                        if signals:
                            processed = ai_routes._persist_business_os_marketing_signals(
                                db=db,
                                actor_user_id=int(admin_actor.id),
                                signals=signals,
                                window_start=str(payload.get("window_start") or ""),
                                window_end=str(payload.get("window_end") or ""),
                                request_id=None,
                                event_source="worker:business-os-marketing-funnel",
                            )
                            db.commit()
                            logger.info(
                                "Business OS marketing worker: signals=%s events=%s window=%sd",
                                len(signals),
                                processed,
                                int(payload.get("window_days") or settings.BUSINESS_OS_MARKETING_WORKER_WINDOW_DAYS),
                            )
                finally:
                    db.close()
            except Exception as exc:
                logger.error("Falha no business os marketing worker: %s", exc, exc_info=True)

            await asyncio.sleep(interval)

    worker_task: asyncio.Task | None = None
    business_os_worker_task: asyncio.Task | None = None
    if app_obj.state.startup_ok and settings.AGENDA_PREDICTIVE_WORKER_ENABLED:
        worker_task = asyncio.create_task(_agenda_predictive_worker())
        app_obj.state.agenda_predictive_worker_task = worker_task
    if app_obj.state.startup_ok and settings.BUSINESS_OS_MARKETING_WORKER_ENABLED:
        business_os_worker_task = asyncio.create_task(_business_os_marketing_worker())
        app_obj.state.business_os_marketing_worker_task = business_os_worker_task

    try:
        yield
    finally:
        if worker_task and not worker_task.done():
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                logger.info("Agenda predictive worker encerrado")
        if business_os_worker_task and not business_os_worker_task.done():
            business_os_worker_task.cancel()
            try:
                await business_os_worker_task
            except asyncio.CancelledError:
                logger.info("Business OS marketing worker encerrado")


app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    openapi_url="/api/openapi.json" if not settings.DEBUG else "/openapi.json",
    docs_url="/api/docs" if not settings.DEBUG else "/docs",
    redoc_url="/api/redoc" if not settings.DEBUG else "/redoc",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    request.state.request_started_at = time.perf_counter()

    accepted, retry_after = _consume_rate_limit(request)
    if not accepted:
        with _metrics_lock:
            _request_metrics["total"] += 1
            _request_metrics["status_4xx"] += 1
            _request_metrics["rate_limited"] += 1
        payload = _error_payload(
            "Muitas requisições. Tente novamente em instantes.",
            "rate_limited",
            request,
        )
        response = JSONResponse(status_code=429, content=payload)
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-Request-ID"] = request_id
        logger.warning(
            "rate_limited method=%s path=%s request_id=%s client=%s retry_after=%ss",
            request.method,
            request.url.path,
            request_id,
            _client_identifier(request),
            retry_after,
        )
        return response

    response = await call_next(request)

    if settings.HTTP_ETAG_ENABLED and _is_cacheable_response(request, response) and not response.headers.get("set-cookie"):
        body = await _read_response_body(response)
        etag = hashlib.sha256(body).hexdigest()
        if request.headers.get("if-none-match") == f'"{etag}"':
            not_modified_headers = {
                key: value
                for key, value in dict(response.headers).items()
                if key.lower() not in {"content-length", "content-type", "content-encoding", "transfer-encoding"}
            }
            not_modified_headers["ETag"] = f'"{etag}"'
            not_modified_headers["Cache-Control"] = _build_cache_control_header(request)
            not_modified_headers["Vary"] = _merge_vary(response.headers.get("vary"), ["Accept-Encoding", "Authorization", "Cookie"])
            not_modified_headers["X-Request-ID"] = request_id
            not_modified_headers["X-Process-Time"] = f"{time.perf_counter() - request.state.request_started_at:.4f}"
            return Response(status_code=304, headers=not_modified_headers)

        response_headers = dict(response.headers)
        response_headers["ETag"] = f'"{etag}"'
        response_headers["Cache-Control"] = _build_cache_control_header(request)
        response_headers["Vary"] = _merge_vary(response.headers.get("vary"), ["Accept-Encoding", "Authorization", "Cookie"])
        response_headers["X-Request-ID"] = request_id
        response_headers["X-Process-Time"] = f"{time.perf_counter() - request.state.request_started_at:.4f}"

        response = Response(
            content=body,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.media_type,
        )

    elapsed = time.perf_counter() - request.state.request_started_at
    elapsed_ms = elapsed * 1000

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"

    with _metrics_lock:
        _request_metrics["total"] += 1
        _request_metrics["duration_ms_total"] += elapsed_ms
        if 200 <= response.status_code < 300:
            _request_metrics["status_2xx"] += 1
        elif 400 <= response.status_code < 500:
            _request_metrics["status_4xx"] += 1
        elif response.status_code >= 500:
            _request_metrics["status_5xx"] += 1

    log_fn = logger.info
    if response.status_code >= 500:
        log_fn = logger.error
    elif response.status_code >= 400:
        log_fn = logger.warning

    log_fn(
        "request method=%s path=%s status=%s duration_ms=%.2f request_id=%s client=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        request_id,
        _client_identifier(request),
    )

    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

if settings.HTTP_GZIP_ENABLED:
    app.add_middleware(
        GZipMiddleware,
        minimum_size=settings.HTTP_GZIP_MINIMUM_SIZE,
    )


templates: Jinja2Templates | None = None

if os.path.isdir("templates"):
    templates = Jinja2Templates(directory="templates")
    logger.info("Templates carregados")
else:
    logger.warning("Diretório de templates não encontrado")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    logger.warning("Diretório static não encontrado; /static não será montado")


def _normalize_ads_provider(provider: str) -> str:
    normalized = str(provider or "fallback").strip().lower()
    if normalized not in {"fallback", "adsense", "custom-script"}:
        return "fallback"
    return normalized


def _build_ads_runtime_config() -> dict[str, Any]:
    rollout = max(0.0, min(1.0, float(settings.WF_ADS_EXPERIMENT_ROLLOUT)))
    variants = [
        str(item).strip().lower()
        for item in settings.WF_ADS_EXPERIMENT_VARIANTS
        if str(item).strip()
    ] or ["a", "b"]

    return {
        "enabled": bool(settings.WF_ADS_ENABLED),
        "provider": _normalize_ads_provider(settings.WF_ADS_PROVIDER),
        "adsense_client": settings.WF_ADSENSE_CLIENT.strip(),
        "script_url": settings.WF_ADS_SCRIPT_URL.strip(),
        "slots": {
            "top": settings.WF_ADS_SLOT_TOP.strip(),
            "bottom": settings.WF_ADS_SLOT_BOTTOM.strip(),
        },
        "frequency": {
            "session_cap_per_slot": max(1, int(settings.WF_ADS_SESSION_CAP_PER_SLOT)),
            "daily_cap_per_slot": max(1, int(settings.WF_ADS_DAILY_CAP_PER_SLOT)),
            "fatigue_no_click_threshold": max(1, int(settings.WF_ADS_FATIGUE_NO_CLICK_THRESHOLD)),
            "fatigue_hard_threshold": max(1, int(settings.WF_ADS_FATIGUE_HARD_THRESHOLD)),
        },
        "experiment": {
            "enabled": bool(settings.WF_ADS_EXPERIMENT_ENABLED),
            "rollout": rollout,
            "variants": variants,
        },
    }


def _build_ads_runtime_config_json() -> str:
    payload = _build_ads_runtime_config()
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def _render_template(template_name: str, request: Request, **context: Any):
    if templates is None:
        raise HTTPException(503, "Templates indisponíveis neste ambiente")
    ads_runtime_config = _build_ads_runtime_config()
    ads_runtime_config_json = _build_ads_runtime_config_json()
    # Usa assinatura nomeada para compatibilidade entre versões da Starlette.
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "request": request,
            "wf_ads_runtime_config": ads_runtime_config,
            "wf_ads_runtime_config_json": ads_runtime_config_json,
            **context,
        },
    )


AGENDA_GUEST_ACCESS_TTL_SECONDS = 300
AGENDA_GUEST_ACCESS_WINDOW_EXPIRY_SECONDS = 60 * 60 * 24 * 30
AGENDA_GUEST_CONSUMED_EXPIRY_SECONDS = 60 * 60 * 24 * 30
AGENDA_LOGGED_TRIAL_ACCESS_SECONDS = 60 * 60 * 24 * 2
AGENDA_LOGGED_TRIAL_KEY_EXPIRY_SECONDS = 60 * 60 * 24 * 93
AGENDA_GUEST_COOKIE_NAME = "wf_agenda_guest_id"
AGENDA_GUEST_ACCESS_KEY_PREFIX = "agenda:guest:access"
AGENDA_GUEST_CONSUMED_KEY_PREFIX = "agenda:guest:consumed"
AGENDA_LOGGED_TRIAL_KEY_PREFIX = "agenda:logged:trial"
AGENDA_GUEST_ENTRY_MARKERS = {"nav", "navigation", "quick", "icon", "menu", "mobile"}


def _agenda_guest_access_key(guest_id: str) -> str:
    return f"{AGENDA_GUEST_ACCESS_KEY_PREFIX}:{guest_id}"


def _agenda_guest_consumed_key(guest_id: str) -> str:
    return f"{AGENDA_GUEST_CONSUMED_KEY_PREFIX}:{guest_id}"


def _agenda_logged_trial_key(user_id: int, year_month: str) -> str:
    return f"{AGENDA_LOGGED_TRIAL_KEY_PREFIX}:{user_id}:{year_month}"


def _is_admin_user(user: User) -> bool:
    role = str(getattr(user, "role", "") or "").lower().strip()
    return bool(getattr(user, "is_superuser", False) or role == "admin")


def _has_active_paid_subscription(db: Session, user: User) -> bool:
    paid_plans = {SubscriptionPlanType.PRO.value, SubscriptionPlanType.PREMIUM.value}
    now = datetime.now(timezone.utc)

    rows = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
            Subscription.plan_type.in_(tuple(paid_plans)),
        )
        .all()
    )

    for row in rows:
        if row.end_date is None:
            return True

        end_date = row.end_date
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if end_date >= now:
            return True

    return False


def _is_agenda_entitled(db: Session, user: User) -> bool:
    return _is_admin_user(user) or _has_active_paid_subscription(db, user)


def _parse_cache_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _first_day_next_month(reference: datetime) -> datetime:
    if reference.month == 12:
        return datetime(reference.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(reference.year, reference.month + 1, 1, tzinfo=timezone.utc)


def _resolve_or_create_guest_agenda_expires_at(
    request: Request,
    *,
    allow_create: bool,
) -> tuple[str | None, int | None, bool]:
    now = datetime.now(timezone.utc)
    guest_id = str(request.cookies.get(AGENDA_GUEST_COOKIE_NAME) or "").strip() or None
    created_cookie = False

    if guest_id:
        if get_cache(_agenda_guest_consumed_key(guest_id)):
            return guest_id, None, False

        access_key = _agenda_guest_access_key(guest_id)
        access_started_at = _parse_cache_datetime(get_cache(access_key))
        if access_started_at is not None:
            expires_at_dt = access_started_at + timedelta(seconds=AGENDA_GUEST_ACCESS_TTL_SECONDS)
            if now >= expires_at_dt:
                delete_cache(access_key)
                set_cache(
                    _agenda_guest_consumed_key(guest_id),
                    now.isoformat(),
                    expire=AGENDA_GUEST_CONSUMED_EXPIRY_SECONDS,
                )
                return guest_id, None, False
            return guest_id, int(expires_at_dt.timestamp()), False

    if not allow_create:
        return guest_id, None, created_cookie

    if not guest_id:
        guest_id = uuid4().hex
        created_cookie = True

    if get_cache(_agenda_guest_consumed_key(guest_id)):
        return guest_id, None, created_cookie

    set_cache(
        _agenda_guest_access_key(guest_id),
        now.isoformat(),
        expire=AGENDA_GUEST_ACCESS_WINDOW_EXPIRY_SECONDS,
    )
    expires_at_dt = now + timedelta(seconds=AGENDA_GUEST_ACCESS_TTL_SECONDS)
    return guest_id, int(expires_at_dt.timestamp()), created_cookie


def _resolve_or_create_logged_trial_agenda_expires_at(user: User) -> tuple[int, int | None]:
    now = datetime.now(timezone.utc)
    period_key = now.strftime("%Y%m")
    cache_key = _agenda_logged_trial_key(user.id, period_key)

    first_access_dt = _parse_cache_datetime(get_cache(cache_key))
    if first_access_dt is None:
        first_access_dt = now
        set_cache(
            cache_key,
            first_access_dt.isoformat(),
            expire=AGENDA_LOGGED_TRIAL_KEY_EXPIRY_SECONDS,
        )

    expires_at_dt = first_access_dt + timedelta(seconds=AGENDA_LOGGED_TRIAL_ACCESS_SECONDS)
    if now >= expires_at_dt:
        return int(first_access_dt.timestamp()), None

    return int(first_access_dt.timestamp()), int(expires_at_dt.timestamp())


API_PREFIX = "/api"


def _ensure_store_categories(db: Session) -> None:
    from app.models.store_models import ProductCategory

    existing_count = db.query(ProductCategory).count()
    if existing_count > 0:
        return

    default_categories = [
        {"name": "Adubos e Fertilizantes", "slug": "adubos-fertilizantes", "icon": "🧪", "description": "NPK, foliares, organominerais e corretivos."},
        {"name": "Inseticidas e Defensivos", "slug": "inseticidas-defensivos", "icon": "🛡️", "description": "Controle de pragas, fungos e plantas daninhas."},
        {"name": "Implementos Agricolas", "slug": "implementos-agricolas", "icon": "🚜", "description": "Pulverizadores, plantadeiras, grades e pecas."},
        {"name": "Vestuario e EPI Agricola", "slug": "vestuario-epi-agricola", "icon": "🧤", "description": "Roupas de protecao, botas, luvas e mascaras."},
        {"name": "Ferramentas Agricolas", "slug": "ferramentas-agricolas", "icon": "🛠️", "description": "Ferramentas manuais, kits e utilitarios rurais."},
        {"name": "Irrigacao e Acessorios", "slug": "irrigacao-acessorios", "icon": "💧", "description": "Mangueiras, gotejamento, bombas e conexoes."},
    ]

    for item in default_categories:
        db.add(ProductCategory(**item, is_active=True))
    db.commit()


app.include_router(auth_routes.router, prefix=API_PREFIX)
app.include_router(offer_routes.router, prefix=API_PREFIX)
app.include_router(transaction_routes.router, prefix=API_PREFIX)
app.include_router(review_routes.router, prefix=API_PREFIX)
app.include_router(favorite_routes.router, prefix=API_PREFIX)
app.include_router(message_routes.router, prefix=API_PREFIX)
app.include_router(category_routes.router, prefix=API_PREFIX)
app.include_router(upload_routes.router, prefix=API_PREFIX)
app.include_router(dashboard_routes.router, prefix=API_PREFIX)
app.include_router(profile_routes.router, prefix=API_PREFIX)
app.include_router(wallet_routes.router, prefix=API_PREFIX)
app.include_router(negotiation_routes.router, prefix=API_PREFIX)
app.include_router(reputation_routes.router, prefix=API_PREFIX)
app.include_router(report_routes.router, prefix=API_PREFIX)
app.include_router(gamification_routes.router, prefix=API_PREFIX)
app.include_router(growth_routes.router, prefix=API_PREFIX)
app.include_router(payment_routes.router, prefix=API_PREFIX)
app.include_router(social_routes.router, prefix=API_PREFIX)
app.include_router(community_routes.router, prefix=API_PREFIX)
app.include_router(notification_routes.router, prefix=API_PREFIX)
app.include_router(ai_routes.router, prefix=API_PREFIX)
app.include_router(store_routes.router)  # Loja Agrícola (HTML + API)
app.include_router(store_routes.router, prefix=API_PREFIX)  # Alias /api/store para chamadas JS
app.include_router(service_routes.router, prefix=API_PREFIX)
app.include_router(library_routes.router, prefix=API_PREFIX)
app.include_router(buyer_client_routes.router, prefix=API_PREFIX)
app.include_router(notification_ws_routes.router)

if not settings.DEBUG:
    @app.get("/docs", include_in_schema=False)
    async def docs_alias():
        """Mantem compatibilidade para ambientes que esperam /docs."""
        return RedirectResponse(url="/api/docs", status_code=307)


    @app.get("/redoc", include_in_schema=False)
    async def redoc_alias():
        """Mantem compatibilidade para ambientes que esperam /redoc."""
        return RedirectResponse(url="/api/redoc", status_code=307)


    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_alias():
        """Mantem compatibilidade para ambientes que esperam /openapi.json."""
        return RedirectResponse(url="/api/openapi.json", status_code=307)

@app.get("/")
async def home(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página inicial."""
    return _render_template("index.html", request, current_user=current_user)


@app.get("/community")
async def community_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página da comunidade para publicações rápidas com imagem."""
    return _render_template("community.html", request, current_user=current_user)


@app.get("/library")
async def library_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página da biblioteca com catálogo público e leitura completa."""
    return _render_template("library.html", request, current_user=current_user)


@app.get("/services")
async def services_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de serviços agrícolas com catálogo e detalhe rápido."""
    return _render_template("services.html", request, current_user=current_user)


@app.get("/services/detail/{service_id}")
async def service_detail_page(service_id: int, request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de detalhe completo de um serviço agrícola."""
    return _render_template("service_detail.html", request, current_user=current_user, service_id=service_id)


@app.get("/services/manage")
async def services_manage_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de gestão de serviços para admin/fornecedor/produtor."""
    return _render_template("services_manage.html", request, current_user=current_user)


@app.get("/clients/manage")
async def clients_manage_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de gestão de carteira de clientes para compradores."""
    return _render_template("clients_manage.html", request, current_user=current_user)


@app.get("/reader")
async def reader_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Leitor completo para abrir livros salvos no localStorage como currentBook."""
    return _render_template("reader.html", request, current_user=current_user)


@app.get("/login")
async def login_page(request: Request):
    """Página de login."""
    return _render_template("login.html", request)


@app.get("/register")
async def register_page(request: Request):
    """Página de registro."""
    return _render_template("register.html", request)


@app.get("/forgot-password")
async def forgot_password_page(request: Request):
    """Página para solicitar recuperação de senha por e-mail."""
    return _render_template("forgot_password.html", request)


@app.get("/forgot-password/confirmation")
async def forgot_password_confirmation_page(request: Request):
    """Página de confirmação após solicitar recuperação de senha."""
    return _render_template("forgot_password_confirmation.html", request)


@app.get("/reset-password")
async def reset_password_page(request: Request):
    """Página para redefinir senha usando token enviado por e-mail."""
    return _render_template("reset_password.html", request)


@app.get("/offers")
async def offers_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de ofertas."""
    return _render_template("offers.html", request, current_user=current_user)


@app.get("/offers/new")
async def create_offer_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página oficial de criação de oferta."""
    return _render_template("create_offer.html", request, current_user=current_user)


@app.get("/offers/{offer_id}")
async def offer_detail_page(
    offer_id: str,
    request: Request,
    current_user: User = Depends(get_current_user_optional),
):
    """Página de detalhes de uma oferta específica."""
    return _render_template("offer_detail.html", request, current_user=current_user, offer_id=offer_id)


@app.get("/orders")
async def marketplace_orders_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Pagina de acompanhamento de reservas/pedidos do marketplace de ofertas."""
    return _render_template("orders.html", request, current_user=current_user)


@app.get("/messages")
async def messages_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de mensagens em formato chat."""
    if current_user is None:
        return RedirectResponse(url="/login?next=/messages", status_code=307)
    return _render_template("messages.html", request, current_user=current_user)


@app.get("/notifications")
async def notifications_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de feed de notificações."""
    return _render_template("notifications.html", request, current_user=current_user)


@app.get("/me/profile")
async def my_profile_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de perfil do usuário logado."""
    return _render_template("profile.html", request, current_user=current_user, viewed_user_id=None)


@app.get("/pricing")
async def pricing_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de planos com estratégia de conversão para upgrade de assinatura."""
    return _render_template("pricing.html", request, current_user=current_user)


@app.get("/me/payment-settings")
async def my_payment_settings_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de configuração de informações de pagamento para checkout e upgrades."""
    return _render_template("payment_settings.html", request, current_user=current_user)


@app.get("/users/{user_id}")
async def public_profile_page(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user_optional),
):
    """Página de perfil público de usuário."""
    return _render_template("profile.html", request, current_user=current_user, viewed_user_id=user_id)


@app.get("/admin")
async def admin_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Painel administrativo web da plataforma."""
    return _render_template("admin.html", request, current_user=current_user)


@app.get("/gamification")
async def gamification_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página oficial de gamificação."""
    return _render_template("gamification.html", request, current_user=current_user)


@app.get("/reputation")
async def reputation_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página oficial de reputação e contestação."""
    return _render_template("reputation.html", request, current_user=current_user)


@app.get("/intermediation")
async def intermediation_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página oficial de mediação e contratos."""
    return _render_template("intermediation.html", request, current_user=current_user)


@app.get("/strategy")
async def strategy_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página da central estratégica para gestão de crescimento."""
    return _render_template("strategy.html", request, current_user=current_user)


@app.get("/documentacao")
async def documentation_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Documentação geral do produto com benefícios, usabilidade e visão de planos."""
    return _render_template("documentation.html", request, current_user=current_user)


# === STORE ROUTES ===
@app.get("/store")
async def store_home(request: Request, category: str | None = None, q: str | None = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_optional)):
    """Página da loja agrícola com filtros e categorias."""
    from app.models.store_models import Product, ProductCategory, ProductStatus

    _ensure_store_categories(db)
    
    query = db.query(Product).filter(Product.status == ProductStatus.PUBLISHED)
    
    if category:
        query = query.join(ProductCategory).filter(ProductCategory.slug == category)
        
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
        
    products = query.order_by(Product.is_featured.desc(), Product.created_at.desc()).all()
    categories = db.query(ProductCategory).filter(ProductCategory.is_active == True).all()
    categories_payload = [
        {
            "id": item.id,
            "name": item.name,
            "slug": item.slug,
            "icon": item.icon,
            "description": item.description,
            "is_active": bool(item.is_active),
        }
        for item in categories
    ]
    
    response = _render_template(
        "store/index.html",
        request,
        products=products,
        categories=categories_payload,
        current_user=current_user,
        search_query=q,
        active_category=category,
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/store/product/{slug}")
async def product_detail(slug: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_optional)):
    """Página de detalhes de um produto específico."""
    from app.models.store_models import Product, ProductStatus
    
    product = db.query(Product).filter(Product.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
        
    related = db.query(Product).filter(
        Product.category_id == product.category_id,
        Product.id != product.id,
        Product.status == ProductStatus.PUBLISHED
    ).limit(4).all()
    
    return _render_template("store/product_detail.html", request, product=product, related_products=related, current_user=current_user)

@app.get("/store/manage/dashboard")
async def supplier_dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_optional)):
    """Dashboard da loja para admin/fornecedor gerenciar produtos."""
    from app.models.store_models import Product, ProductCategory

    _ensure_store_categories(db)

    can_manage_store = bool(current_user and current_user.role in ["admin", "supplier", "producer"])
    my_products = db.query(Product).filter(Product.supplier_id == current_user.id).all() if can_manage_store else []
    categories = db.query(ProductCategory).all()

    return _render_template(
        "store/dashboard.html",
        request,
        products=my_products,
        categories=categories,
        current_user=current_user,
        can_manage_store=can_manage_store,
    )

@app.get("/store/cart")
async def view_cart(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página do carrinho de compras."""
    return _render_template("store/cart.html", request, current_user=current_user)


@app.get("/store/checkout")
async def store_checkout_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de checkout da loja."""
    return _render_template("store/checkout.html", request, current_user=current_user)


@app.get("/store/proposals")
async def store_proposals_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de propostas por volume do usuário comprador."""
    return _render_template("store/proposals.html", request, current_user=current_user)


@app.get("/store/orders")
async def store_orders_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de acompanhamento de pedidos e pós-venda."""
    return _render_template("store/orders.html", request, current_user=current_user)


@app.get("/api/store/featured")
async def store_featured_products(limit: int = 8, db: Session = Depends(get_db)):
    """Lista pública de produtos em destaque para vitrines horizontais."""
    from app.models.store_models import Product, ProductStatus

    safe_limit = max(1, min(limit, 20))
    products = (
        db.query(Product)
        .filter(Product.status == ProductStatus.PUBLISHED)
        .order_by(Product.is_featured.desc(), Product.created_at.desc())
        .limit(safe_limit)
        .all()
    )

    payload = []
    for product in products:
        payload.append(
            {
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
                "price": float(product.price or 0),
                "is_featured": bool(product.is_featured),
                "stock_quantity": int(product.stock_quantity or 0),
                "category": product.category.name if product.category else "Categoria",
                "supplier": product.supplier.name if product.supplier else "Fornecedor",
                "image": product.images[0] if isinstance(product.images, list) and product.images else None,
            }
        )

    return {"products": payload, "total": len(payload)}


@app.get("/api/store/products")
async def store_products_api(
    q: str | None = None,
    category: str | None = None,
    crop: str | None = None,
    pest: str | None = None,
    price_range: str | None = None,
    db: Session = Depends(get_db),
):
    """Lista de produtos da loja com filtros para UI dinâmica da vitrine."""
    from app.models.store_models import Product, ProductCategory, ProductStatus

    query = db.query(Product).filter(Product.status == ProductStatus.PUBLISHED)

    if category:
        query = query.join(ProductCategory).filter(ProductCategory.slug == category)

    if q:
        like_q = f"%{q}%"
        query = query.filter(Product.name.ilike(like_q))

    products = query.order_by(Product.is_featured.desc(), Product.created_at.desc()).all()

    def _spec_text(product: Product, key: str) -> str:
        specs = product.specifications if isinstance(product.specifications, dict) else {}
        return str(specs.get(key) or "").strip()

    if crop:
        crop_l = crop.lower()
        products = [
            item for item in products if crop_l in _spec_text(item, "Culturas recomendadas").lower()
        ]

    if pest:
        pest_l = pest.lower()
        products = [
            item
            for item in products
            if pest_l in _spec_text(item, "Uso indicado").lower()
            or pest_l in (str(item.description or "").lower())
        ]

    if price_range:
        bounds = re.match(r"^(\d+)-(\d+)$", str(price_range).strip())
        if bounds:
            min_p = float(bounds.group(1))
            max_p = float(bounds.group(2))
            products = [
                item for item in products if min_p <= float(item.price or 0) <= max_p
            ]

    crops: set[str] = set()
    pests: set[str] = set()
    for item in db.query(Product).filter(Product.status == ProductStatus.PUBLISHED).all():
        crops_value = _spec_text(item, "Culturas recomendadas")
        pests_value = _spec_text(item, "Uso indicado")

        if crops_value:
            for part in crops_value.split(","):
                cleaned = part.strip()
                if cleaned:
                    crops.add(cleaned)

        if pests_value:
            for part in pests_value.split(","):
                cleaned = part.strip()
                if cleaned:
                    pests.add(cleaned)

    payload = []
    for item in products:
        image = item.images[0] if isinstance(item.images, list) and item.images else None
        payload.append(
            {
                "id": item.id,
                "name": item.name,
                "slug": item.slug,
                "price": float(item.price or 0),
                "promotional_price": float(item.promotional_price or 0),
                "stock_quantity": int(item.stock_quantity or 0),
                "is_featured": bool(item.is_featured),
                "category": item.category.name if item.category else "Categoria",
                "image": image,
            }
        )

    return {
        "products": payload,
        "total": len(payload),
        "filters": {
            "crops": sorted(crops),
            "pests": sorted(pests),
        },
    }


@app.get("/ai-agent")
async def ai_agent_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Interface web do assistente IA embutida no botão flutuante."""
    if current_user is None:
        entry_marker = str(request.query_params.get("entry") or "").strip().lower()
        allow_guest_create = entry_marker in AGENDA_GUEST_ENTRY_MARKERS
        guest_id, guest_expires_at, created_guest_cookie = _resolve_or_create_guest_agenda_expires_at(
            request,
            allow_create=allow_guest_create,
        )

        if guest_expires_at is None:
            return RedirectResponse(url="/login?next=/ai-agent%3Fentry%3Dnav", status_code=307)

        response = _render_template(
            "ai_agent.html",
            request,
            current_user=None,
            agenda_is_entitled=False,
            agenda_temporary_access=True,
            agenda_access_expires_at=guest_expires_at,
            agenda_guest_access=True,
            agenda_logged_trial_access=False,
            agenda_trial_first_access_at=None,
        )
        if created_guest_cookie and guest_id:
            response.set_cookie(
                key=AGENDA_GUEST_COOKIE_NAME,
                value=guest_id,
                max_age=AGENDA_GUEST_ACCESS_WINDOW_EXPIRY_SECONDS,
                httponly=True,
                samesite="lax",
                secure=not settings.DEBUG,
            )
        return response

    if _is_agenda_entitled(db, current_user):
        return _render_template(
            "ai_agent.html",
            request,
            current_user=current_user,
            agenda_is_entitled=True,
            agenda_temporary_access=False,
            agenda_access_expires_at=None,
            agenda_guest_access=False,
            agenda_logged_trial_access=False,
            agenda_trial_first_access_at=None,
        )

    first_access_at, expires_at = _resolve_or_create_logged_trial_agenda_expires_at(current_user)
    if expires_at is None:
        now = datetime.now(timezone.utc)
        first_access_label = datetime.fromtimestamp(first_access_at, tz=timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        next_cycle_label = _first_day_next_month(now).strftime("%d/%m/%Y")
        return _render_template(
            "ai_agent_access_denied.html",
            request,
            current_user=current_user,
            access_denied_reason="monthly_window_expired",
            agenda_trial_first_access_label=first_access_label,
            agenda_trial_next_cycle_label=next_cycle_label,
        )

    return _render_template(
        "ai_agent.html",
        request,
        current_user=current_user,
        agenda_is_entitled=False,
        agenda_temporary_access=True,
        agenda_access_expires_at=expires_at,
        agenda_guest_access=False,
        agenda_logged_trial_access=True,
        agenda_trial_first_access_at=first_access_at,
    )


@app.get("/ai_agent")
async def ai_agent_page_legacy_alias():
    """Alias legado para preservar links antigos da agenda inteligente."""
    return RedirectResponse(url="/ai-agent", status_code=307)


_AGENT_QUERY_STOPWORDS = {
    "de",
    "da",
    "do",
    "das",
    "dos",
    "para",
    "por",
    "com",
    "sem",
    "que",
    "qual",
    "quais",
    "uma",
    "um",
    "as",
    "os",
    "na",
    "no",
    "nas",
    "nos",
    "pra",
    "pro",
    "mais",
    "menos",
    "sobre",
    "entre",
    "hoje",
    "amanha",
    "amanha",
}

_AGENT_DOMAIN_LABELS = {
    "offer": "ofertas",
    "service": "servicos",
    "product": "loja",
}

_AGENT_RESULT_SOURCE_LABELS = {
    "offer": "Oferta",
    "service": "Servico",
    "product": "Loja",
}


def _normalize_agent_text(value: str) -> str:
    base = unicodedata.normalize("NFKD", str(value or ""))
    base = "".join(ch for ch in base if not unicodedata.combining(ch))
    base = re.sub(r"\s+", " ", base)
    return base.strip().lower()


def _agent_tokens(normalized_question: str) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"[a-z0-9]{3,}", normalized_question):
        if token in _AGENT_QUERY_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def _agent_parse_number(value: Any) -> float:
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return 0.0

    text = re.sub(r"[^0-9,.-]", "", text)
    if not text:
        return 0.0

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return 0.0


def _extract_agent_limit(normalized_question: str, default_value: int = 5) -> int:
    match = re.search(r"\b(?:top|melhores|melhor|mostrar|liste|listar|quero)\s*(\d{1,2})\b", normalized_question)
    if not match:
        return max(3, min(default_value, 10))

    try:
        return max(3, min(int(match.group(1)), 10))
    except ValueError:
        return max(3, min(default_value, 10))


def _extract_agent_price_bounds(normalized_question: str) -> tuple[float | None, float | None]:
    min_price: float | None = None
    max_price: float | None = None

    between_match = re.search(
        r"\b(?:entre|de)\s*r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:e|a|ate|até|-)\s*r?\$?\s*(\d+(?:[.,]\d+)?)",
        normalized_question,
    )
    if between_match:
        left = _agent_parse_number(between_match.group(1))
        right = _agent_parse_number(between_match.group(2))
        min_price = min(left, right)
        max_price = max(left, right)

    max_match = re.search(r"\b(?:ate|até|no maximo|no maximo de|maximo|maximo de)\s*r?\$?\s*(\d+(?:[.,]\d+)?)", normalized_question)
    if max_match:
        max_price = _agent_parse_number(max_match.group(1))

    min_match = re.search(r"\b(?:a partir de|acima de|minimo|minimo de|min)\s*r?\$?\s*(\d+(?:[.,]\d+)?)", normalized_question)
    if min_match:
        min_price = _agent_parse_number(min_match.group(1))

    if min_price is not None and max_price is not None and min_price > max_price:
        min_price, max_price = max_price, min_price

    return min_price, max_price


def _extract_agent_domains(normalized_question: str) -> set[str]:
    domains: set[str] = set()

    if any(term in normalized_question for term in ("oferta", "ofertas", "negociacao", "negociar")):
        domains.add("offer")

    if any(term in normalized_question for term in ("servico", "servicos", "prestador", "prestacao")):
        domains.add("service")

    if any(term in normalized_question for term in ("loja", "store", "produto", "produtos", "insumo", "adubo")):
        domains.add("product")

    if not domains:
        return {"offer", "service", "product"}

    return domains


def _extract_agent_category_hint(normalized_question: str) -> str | None:
    match = re.search(r"\bcategoria\s+([a-z0-9\s/_-]{3,40})", normalized_question)
    if not match:
        return None

    raw = match.group(1).strip()
    raw = re.split(r"\b(com|entre|ate|até|acima|minimo|minimo de|qualidade|preco|agendar|reservar)\b", raw)[0].strip()
    if len(raw) < 3:
        return None
    return raw


def _extract_agent_quality_preference(normalized_question: str) -> str | None:
    prefers_high = any(
        term in normalized_question
        for term in (
            "qualidade alta",
            "premium",
            "primeira",
            "classe a",
            "tipo a",
            "organico",
            "certificado",
        )
    )
    prefers_value = any(
        term in normalized_question
        for term in (
            "mais barato",
            "barato",
            "economico",
            "baixo custo",
            "segunda",
            "classe b",
            "classe c",
        )
    )

    if prefers_high:
        return "high"
    if prefers_value:
        return "value"
    return None


def _extract_agent_sort_preference(normalized_question: str) -> str:
    if any(term in normalized_question for term in ("mais barato", "barato", "economico", "menor preco", "preco baixo")):
        return "price_low"

    if any(term in normalized_question for term in ("melhor qualidade", "premium", "classe a", "mais qualidade")):
        return "quality_high"

    return "balanced"


def _is_agent_schedule_intent(normalized_question: str) -> bool:
    return any(
        term in normalized_question
        for term in (
            "agendar",
            "agende",
            "marcar",
            "marque",
            "reserva",
            "reservar",
            "criar evento",
            "agendamento",
        )
    )


def _is_agent_decision_query(normalized_question: str) -> bool:
    domain_hit = any(
        term in normalized_question
        for term in (
            "oferta",
            "ofertas",
            "servico",
            "servicos",
            "loja",
            "produto",
            "produtos",
            "store",
        )
    )
    decision_hit = any(
        term in normalized_question
        for term in (
            "buscar",
            "busca",
            "encontrar",
            "recomendar",
            "comparar",
            "decidir",
            "priorizar",
            "melhor",
            "categoria",
            "preco",
            "preço",
            "qualidade",
        )
    )

    return _is_agent_schedule_intent(normalized_question) or (domain_hit and decision_hit)


def _extract_agent_schedule_datetime(question: str) -> datetime | None:
    normalized_question = _normalize_agent_text(question)
    now = datetime.now(timezone.utc)

    relative = re.search(r"\b(hoje|amanha)\b(?:\s*(?:as|a))?\s*(\d{1,2})(?:[:h](\d{2}))?", normalized_question)
    if relative:
        day_word = relative.group(1)
        hour = int(relative.group(2))
        minute = int(relative.group(3) or 0)

        target_date = now.date()
        if day_word == "amanha":
            target_date = (now + timedelta(days=1)).date()

        hour = max(0, min(23, hour))
        minute = max(0, min(59, minute))

        return datetime(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
            hour=hour,
            minute=minute,
            tzinfo=timezone.utc,
        )

    absolute = re.search(
        r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?(?:\D+(\d{1,2})(?:[:h](\d{2}))?)?",
        normalized_question,
    )
    if absolute:
        day = int(absolute.group(1))
        month = int(absolute.group(2))
        year_raw = absolute.group(3)
        hour = int(absolute.group(4) or 9)
        minute = int(absolute.group(5) or 0)

        year = now.year
        if year_raw:
            year_num = int(year_raw)
            year = year_num + 2000 if year_num < 100 else year_num

        try:
            return datetime(
                year=year,
                month=month,
                day=day,
                hour=max(0, min(23, hour)),
                minute=max(0, min(59, minute)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None

    return None


def _agent_quality_score(*values: Any) -> float:
    text = _normalize_agent_text(" ".join(str(value or "") for value in values))
    score = 0.56

    if any(term in text for term in ("premium", "primeira", "classe a", "tipo a", "selecionad", "extra")):
        score += 0.24
    if any(term in text for term in ("organico", "certific", "rastreabilidade")):
        score += 0.14
    if any(term in text for term in ("classe b", "segunda", "padrao", "standard")):
        score -= 0.06
    if any(term in text for term in ("classe c", "descarte")):
        score -= 0.20

    return max(0.15, min(0.98, score))


def _agent_quality_label(score: float) -> str:
    if score >= 0.78:
        return "Alta"
    if score >= 0.52:
        return "Media"
    return "Economica"


def _agent_currency(value: float) -> str:
    return f"R$ {float(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _build_agent_commerce_recommendations(db: Session, question: str, limit: int = 5) -> dict[str, Any]:
    from app.models.service import Service
    from app.models.store_models import Product, ProductStatus

    normalized_question = _normalize_agent_text(question)
    requested_limit = _extract_agent_limit(normalized_question, default_value=limit)
    domains = _extract_agent_domains(normalized_question)
    category_hint = _extract_agent_category_hint(normalized_question)
    quality_pref = _extract_agent_quality_preference(normalized_question)
    sort_pref = _extract_agent_sort_preference(normalized_question)
    min_price, max_price = _extract_agent_price_bounds(normalized_question)
    tokens = _agent_tokens(normalized_question)

    candidates: list[dict[str, Any]] = []
    scanned_total = 0

    def category_matches(search_blob: str) -> bool:
        if not category_hint:
            return True

        if category_hint in search_blob:
            return True

        hint_tokens = [token for token in category_hint.split() if len(token) >= 3]
        return any(token in search_blob for token in hint_tokens)

    def token_hits_count(search_blob: str) -> int:
        if not tokens:
            return 0
        return sum(1 for token in tokens if token in search_blob)

    if "offer" in domains:
        offer_rows = (
            db.query(Offer)
            .filter(Offer.status == "active")
            .order_by(Offer.is_featured.desc(), Offer.updated_at.desc(), Offer.created_at.desc())
            .limit(120)
            .all()
        )
        scanned_total += len(offer_rows)

        for offer in offer_rows:
            unit_price = _agent_parse_number(offer.price_per_kg)
            if unit_price <= 0:
                total_price = _agent_parse_number(offer.price)
                quantity = _agent_parse_number(offer.quantity)
                if total_price > 0 and quantity > 0:
                    unit_price = total_price / max(quantity, 1.0)
                else:
                    unit_price = total_price

            quality_raw = str(offer.quality_class or offer.quality_grade or "").strip()
            quality_score = _agent_quality_score(
                quality_raw,
                "organico" if bool(getattr(offer, "organic", False)) else "",
                str(offer.certification or ""),
            )
            quality_label = quality_raw or _agent_quality_label(quality_score)
            unit_label = str(offer.unit or "kg").strip() or "kg"

            search_blob = _normalize_agent_text(
                " ".join(
                    [
                        str(offer.product_name or ""),
                        str(offer.description or ""),
                        str(offer.category or ""),
                        str(offer.variety or ""),
                        str(offer.location or ""),
                        quality_label,
                    ]
                )
            )

            if not category_matches(search_blob):
                continue

            price_known = unit_price > 0
            if min_price is not None and (not price_known or unit_price < min_price):
                continue
            if max_price is not None and (not price_known or unit_price > max_price):
                continue

            token_hits = token_hits_count(search_blob)
            score = 26.0 + (token_hits * 9.0)
            if tokens and token_hits == 0:
                score -= 5.0
            if category_hint:
                score += 10.0
            if quality_pref == "high":
                score += quality_score * 18.0
            elif quality_pref == "value":
                score += (1.0 - quality_score) * 8.0
            elif "qualidade" in normalized_question:
                score += quality_score * 8.0
            if bool(getattr(offer, "is_featured", False)):
                score += 4.0
            if "oferta" in normalized_question:
                score += 5.0

            reasons: list[str] = []
            if token_hits:
                reasons.append(f"aderencia textual ({token_hits} termo(s))")
            if category_hint:
                reasons.append("categoria compatvel")
            if min_price is not None or max_price is not None:
                reasons.append("faixa de preco aplicada")
            if quality_pref:
                reasons.append("preferencia de qualidade aplicada")

            candidates.append(
                {
                    "source": "offer",
                    "id": str(offer.id),
                    "title": str(offer.product_name or "Oferta"),
                    "category": str(offer.category or "Geral"),
                    "price": float(unit_price) if price_known else 0.0,
                    "price_known": price_known,
                    "price_label": f"{_agent_currency(unit_price)}/{unit_label}" if price_known else "Preco sob consulta",
                    "quality_score": quality_score,
                    "quality_label": quality_label,
                    "url": f"/offers/{offer.id}",
                    "score": score,
                    "reasons": reasons,
                    "location": str(offer.location or "").strip() or None,
                }
            )

    if "service" in domains:
        service_rows = (
            db.query(Service)
            .filter(Service.is_active.is_(True))
            .order_by(Service.updated_at.desc(), Service.created_at.desc())
            .limit(100)
            .all()
        )
        scanned_total += len(service_rows)

        for service in service_rows:
            ficha = service.ficha_tecnica if isinstance(service.ficha_tecnica, dict) else {}
            category = str(
                ficha.get("categoria")
                or ficha.get("Categoria")
                or ficha.get("segmento")
                or "Servicos"
            )

            price_value = _agent_parse_number(service.preco)
            price_known = price_value > 0

            search_blob = _normalize_agent_text(
                " ".join(
                    [
                        str(service.titulo or ""),
                        str(service.descricao or ""),
                        str(category),
                        str(service.local or ""),
                        json.dumps(ficha, ensure_ascii=True),
                    ]
                )
            )

            if not category_matches(search_blob):
                continue

            if min_price is not None and (not price_known or price_value < min_price):
                continue
            if max_price is not None and (not price_known or price_value > max_price):
                continue

            quality_score = _agent_quality_score(str(service.descricao or ""), json.dumps(ficha, ensure_ascii=True))
            quality_label = _agent_quality_label(quality_score)

            token_hits = token_hits_count(search_blob)
            score = 24.0 + (token_hits * 8.0)
            if tokens and token_hits == 0:
                score -= 6.0
            if category_hint:
                score += 10.0
            if quality_pref == "high":
                score += quality_score * 16.0
            elif quality_pref == "value":
                score += (1.0 - quality_score) * 7.0
            if "servico" in normalized_question:
                score += 5.0

            reasons = []
            if token_hits:
                reasons.append(f"aderencia textual ({token_hits} termo(s))")
            if category_hint:
                reasons.append("categoria compatvel")
            if min_price is not None or max_price is not None:
                reasons.append("faixa de preco aplicada")

            candidates.append(
                {
                    "source": "service",
                    "id": str(service.id),
                    "title": str(service.titulo or "Servico"),
                    "category": category,
                    "price": float(price_value) if price_known else 0.0,
                    "price_known": price_known,
                    "price_label": _agent_currency(price_value) if price_known else "Preco sob consulta",
                    "quality_score": quality_score,
                    "quality_label": quality_label,
                    "url": f"/services/detail/{service.id}",
                    "score": score,
                    "reasons": reasons,
                    "location": str(service.local or "").strip() or None,
                }
            )

    if "product" in domains:
        product_rows = (
            db.query(Product)
            .options(joinedload(Product.category))
            .filter(Product.status == ProductStatus.PUBLISHED)
            .order_by(Product.is_featured.desc(), Product.created_at.desc())
            .limit(120)
            .all()
        )
        scanned_total += len(product_rows)

        for product in product_rows:
            category_name = str(product.category.name if product.category else "Loja")
            specifications = product.specifications if isinstance(product.specifications, dict) else {}
            promotion_price = _agent_parse_number(product.promotional_price)
            base_price = _agent_parse_number(product.price)
            effective_price = promotion_price if promotion_price > 0 else base_price
            price_known = effective_price > 0

            search_blob = _normalize_agent_text(
                " ".join(
                    [
                        str(product.name or ""),
                        str(product.description or ""),
                        category_name,
                        json.dumps(specifications, ensure_ascii=True),
                    ]
                )
            )

            if not category_matches(search_blob):
                continue

            if min_price is not None and (not price_known or effective_price < min_price):
                continue
            if max_price is not None and (not price_known or effective_price > max_price):
                continue

            quality_score = _agent_quality_score(
                str(product.description or ""),
                json.dumps(specifications, ensure_ascii=True),
            )
            quality_label = _agent_quality_label(quality_score)

            token_hits = token_hits_count(search_blob)
            score = 24.0 + (token_hits * 8.5)
            if tokens and token_hits == 0:
                score -= 6.0
            if category_hint:
                score += 10.0
            if quality_pref == "high":
                score += quality_score * 16.0
            elif quality_pref == "value":
                score += (1.0 - quality_score) * 7.0
            if bool(getattr(product, "is_featured", False)):
                score += 4.0
            if "loja" in normalized_question or "produto" in normalized_question:
                score += 5.0

            reasons = []
            if token_hits:
                reasons.append(f"aderencia textual ({token_hits} termo(s))")
            if category_hint:
                reasons.append("categoria compatvel")
            if min_price is not None or max_price is not None:
                reasons.append("faixa de preco aplicada")

            candidates.append(
                {
                    "source": "product",
                    "id": str(product.id),
                    "title": str(product.name or "Produto"),
                    "category": category_name,
                    "price": float(effective_price) if price_known else 0.0,
                    "price_known": price_known,
                    "price_label": _agent_currency(effective_price) if price_known else "Preco sob consulta",
                    "quality_score": quality_score,
                    "quality_label": quality_label,
                    "url": f"/store/product/{product.slug}" if product.slug else "/store",
                    "score": score,
                    "reasons": reasons,
                    "location": None,
                }
            )

    known_prices = [row["price"] for row in candidates if row["price_known"] and row["price"] > 0]
    min_known_price = min(known_prices) if known_prices else 0.0
    max_known_price = max(known_prices) if known_prices else 0.0
    price_span = max(max_known_price - min_known_price, 1.0)

    for item in candidates:
        if sort_pref == "price_low":
            if item["price_known"] and item["price"] > 0:
                normalized_price = (item["price"] - min_known_price) / price_span
                item["score"] += (1.0 - normalized_price) * 22.0
            else:
                item["score"] -= 8.0
        elif sort_pref == "quality_high":
            item["score"] += float(item["quality_score"]) * 18.0
        else:
            if item["price_known"] and max_known_price > 0:
                normalized_price = (item["price"] - min_known_price) / price_span
                item["score"] += (1.0 - normalized_price) * 6.0
            item["score"] += float(item["quality_score"]) * 5.0

    if sort_pref == "price_low":
        candidates.sort(
            key=lambda row: (
                -float(row["score"]),
                float(row["price"]) if row["price_known"] else float("inf"),
            )
        )
    else:
        candidates.sort(key=lambda row: float(row["score"]), reverse=True)

    recommendations: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates[:requested_limit], start=1):
        reason_text = "; ".join(item["reasons"][:3]) if item["reasons"] else "aderencia geral ao pedido"
        recommendations.append(
            {
                "rank": idx,
                "source": item["source"],
                "source_label": _AGENT_RESULT_SOURCE_LABELS.get(item["source"], "Item"),
                "id": item["id"],
                "title": item["title"],
                "category": item["category"],
                "price": round(float(item["price"]), 2) if item["price_known"] else None,
                "price_label": item["price_label"],
                "quality_label": item["quality_label"],
                "score": round(float(item["score"]), 1),
                "reason": reason_text,
                "url": item["url"],
                "location": item["location"],
            }
        )

    return {
        "recommendations": recommendations,
        "domains": sorted(list(domains)),
        "filters": {
            "domains": sorted(list(domains)),
            "category": category_hint,
            "min_price": round(min_price, 2) if min_price is not None else None,
            "max_price": round(max_price, 2) if max_price is not None else None,
            "quality_preference": quality_pref,
            "sort": sort_pref,
            "limit": requested_limit,
        },
        "total_scanned": scanned_total,
    }


@app.post("/api/ai-agent/ask")
async def ai_agent_ask(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    """Responde perguntas sobre os módulos da plataforma WallFruits."""
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Pergunta não informada")

    text_q = _normalize_agent_text(question)

    def has(*terms: str) -> bool:
        return any(_normalize_agent_text(term) in text_q for term in terms)

    agenda_profile: dict[str, Any] = {}
    total_orders: int | None = None
    pending_quotes: int | None = None
    unread_notifications: int | None = None
    recommendations_payload: list[dict[str, Any]] = []
    decision_filters: dict[str, Any] = {}
    scheduled_event_payload: dict[str, Any] | None = None

    def build_full_platform_guide() -> str:
        intro = (
            "Guia completo da WallFruits:\n"
            "1) Acesso e conta\n"
            "- Entrar: /login\n"
            "- Criar conta: /register\n"
            "- Recuperar senha: /forgot-password\n"
            "- Perfil do usuário: /profile\n"
            "\n"
            "2) Comercial de ofertas\n"
            "- Ver ofertas: /offers\n"
            "- Criar oferta: /offers/new\n"
            "- Negociar com comprador/vendedor: /messages e detalhes da oferta\n"
            "- Resolver conflito: /intermediation\n"
            "\n"
            "3) Loja Agro (e-commerce)\n"
            "- Catálogo e compra: /store\n"
            "- Carrinho e checkout: /store/checkout\n"
            "- Gestão para fornecedor/admin: /store/manage/dashboard\n"
            "\n"
            "4) Comunicação e alertas\n"
            "- Conversas: /messages\n"
            "- Notificações: /notifications\n"
            "\n"
            "5) Agenda Inteligente\n"
            "- Acessar: /ai-agent\n"
            "- Define prioridade, risco e próximos passos com base no seu perfil\n"
            "- Modos: assistida, semiautomática e autônoma\n"
            "\n"
            "6) Administração (somente admin)\n"
            "- Painel: /admin\n"
            "- Gestão de usuários, permissões e verificações\n"
            "\n"
            "7) Atalhos úteis\n"
            "- Home: /\n"
            "- Estratégia: /strategy\n"
            "- Comunidade/Biblioteca quando habilitadas no menu principal\n"
            "\n"
            "8) Erros comuns e solução rápida\n"
            "- Credencial inválida: revisar ambiente + redefinir senha\n"
            "- Sem acesso à Agenda: validar janela temporária/plano\n"
            "- Sem resposta em negociação: conferir notificações e mensagens\n"
        )

        if current_user:
            mode = str(agenda_profile.get("autonomy_mode") or "assistida")
            goal = str(agenda_profile.get("main_goal") or "produtividade")
            intro += (
                "\n"
                "Seu contexto atual:\n"
                f"- Modo da Agenda: {mode}\n"
                f"- Objetivo principal: {goal}\n"
                f"- Pedidos na loja: {int(total_orders or 0)}\n"
                f"- Propostas pendentes: {int(pending_quotes or 0)}\n"
                f"- Notificações não lidas: {int(unread_notifications or 0)}\n"
            )

        intro += (
            "\n"
            "Se quiser, eu também te passo um passo a passo por tarefa, por exemplo: \n"
            "- 'como criar uma oferta e fechar negócio'\n"
            "- 'como publicar produto na loja'\n"
            "- 'como usar a agenda no modo autônomo com segurança'"
        )
        return intro

    answer = (
        "Posso ajudar com tudo da WallFruits: login, ofertas, loja agro, mensagens, notificações, "
        "negociações, pagamentos, reputação, perfil e painel admin. Diga exatamente o que você precisa fazer."
    )

    if current_user:
        from app.models.ai_models import UserBehaviorLog
        from app.models.notification import Notification
        from app.models.store_models import Order, QuoteRequest, QuoteRequestStatus

        profile_row = (
            db.query(UserBehaviorLog)
            .filter(
                UserBehaviorLog.user_id == current_user.id,
                UserBehaviorLog.event_type == "agenda_profile_updated",
            )
            .order_by(UserBehaviorLog.created_at.desc())
            .first()
        )
        agenda_profile = profile_row.meta_json if profile_row and isinstance(profile_row.meta_json, dict) else {}

        total_orders = (
            db.query(Order)
            .filter(Order.customer_id == current_user.id, Order.payment_method != "cart_open")
            .count()
        )
        pending_quotes = (
            db.query(QuoteRequest)
            .filter(
                QuoteRequest.requester_id == current_user.id,
                QuoteRequest.status == QuoteRequestStatus.PENDING,
            )
            .count()
        )
        unread_notifications = (
            db.query(Notification)
            .filter(Notification.user_id == current_user.id, Notification.is_read.is_(False))
            .count()
        )

        if has("resumo", "meu perfil", "meus dados", "minha agenda", "status"):
            mode = agenda_profile.get("autonomy_mode", "assistida")
            answer = (
                f"Resumo do seu contexto, {current_user.name}: modo da agenda = {mode}; "
                f"pedidos na loja = {total_orders}; propostas pendentes = {pending_quotes}; "
                f"notificações não lidas = {unread_notifications}. "
                "Posso decidir próximas ações com base nisso e no seu objetivo configurado na Agenda Inteligente."
            )
        elif has("agenda", "autônoma", "autonoma", "decisão", "decisao"):
            mode = agenda_profile.get("autonomy_mode", "assistida")
            goal = agenda_profile.get("main_goal", "produtividade")
            answer = (
                f"Sua Agenda Inteligente está em modo {mode} com foco em {goal}. "
                "Ela cruza histórico de compras, propostas, notificações e atividades para priorizar ações. "
                "Abra /ai-agent para revisar ou atualizar suas preferências de autonomia e recomendações."
            )

    blocked_for_decision_mode = has(
        "todas instruções",
        "todas as instruções",
        "instruções da plataforma",
        "manual",
        "guia completo",
        "ajuda completa",
        "passo a passo",
        "suporte inteligente",
        "como usar a plataforma",
        "onboarding",
    )

    decision_query = _is_agent_decision_query(text_q) and not blocked_for_decision_mode
    if decision_query:
        decision_bundle = _build_agent_commerce_recommendations(db=db, question=question, limit=5)
        recommendations_payload = list(decision_bundle.get("recommendations") or [])
        decision_filters = dict(decision_bundle.get("filters") or {})

        domains = list(decision_bundle.get("domains") or [])
        domain_labels = [_AGENT_DOMAIN_LABELS.get(domain, domain) for domain in domains]
        scanned_total = int(decision_bundle.get("total_scanned") or 0)

        if recommendations_payload:
            top = recommendations_payload[0]
            scope_label = ", ".join(domain_labels) if domain_labels else "ofertas, servicos e loja"
            answer = (
                f"Analisei {scanned_total} itens em {scope_label} e selecionei {len(recommendations_payload)} opcoes aderentes ao seu pedido. "
                f"A melhor opcao agora e {top.get('title', 'item sugerido')} ({top.get('source_label', 'Item')}) por {top.get('price_label', 'preco sob consulta')}, "
                f"categoria {top.get('category', 'geral')} e qualidade {top.get('quality_label', 'media')}."
            )
            if top.get("reason"):
                answer += f" Motivo principal: {top.get('reason')}."
            answer += " Posso refinar imediatamente por outra categoria, faixa de preco ou nivel de qualidade."
        else:
            answer = (
                "Nao encontrei resultados que atendam ao filtro atual. "
                "Tente ampliar a categoria, ajustar faixa de preco ou reduzir a restricao de qualidade."
            )

        if _is_agent_schedule_intent(text_q):
            if current_user is None:
                answer += " Para agendar reserva automatica, faca login e repita com dia e hora."
            else:
                schedule_at = _extract_agent_schedule_datetime(question)
                if schedule_at is None:
                    answer += " Para agendar automaticamente, informe dia e horario (ex.: 'amanha 14h' ou '25/04 09:30')."
                else:
                    from app.models.agenda_event import AgendaEvent

                    top_item = recommendations_payload[0] if recommendations_payload else None
                    event_title_suffix = str((top_item or {}).get("title") or "acao estrategica")
                    event_title = f"Reserva IA: {event_title_suffix}"[:170]
                    event_description = (
                        f"Reserva criada pelo Agente Pessoal a partir da pergunta: {question}. "
                        f"Filtro aplicado: {json.dumps(decision_filters, ensure_ascii=True)}"
                    )
                    starts_at = schedule_at
                    ends_at = schedule_at + timedelta(minutes=45)

                    event = AgendaEvent(
                        user_id=current_user.id,
                        title=event_title,
                        description=event_description,
                        event_type="reservation",
                        starts_at=starts_at,
                        ends_at=ends_at,
                        location=str((top_item or {}).get("location") or "").strip() or None,
                        status="scheduled",
                        is_all_day=False,
                        meta_json={
                            "source": "ai_agent_chat",
                            "question": question,
                            "recommendation": top_item,
                            "filters": decision_filters,
                        },
                    )
                    db.add(event)
                    db.commit()
                    db.refresh(event)

                    scheduled_event_payload = {
                        "id": int(event.id),
                        "title": event.title,
                        "starts_at": event.starts_at.isoformat(),
                        "ends_at": event.ends_at.isoformat(),
                        "event_type": event.event_type,
                    }
                    answer += (
                        " Reserva criada com sucesso na Agenda IA para "
                        f"{schedule_at.astimezone(timezone.utc).strftime('%d/%m %H:%M UTC')}."
                    )

        return {
            "answer": answer,
            "recommendations": recommendations_payload,
            "filters": decision_filters,
            "scheduled_event": scheduled_event_payload,
        }

    if has(
        "todas instruções",
        "todas as instruções",
        "instruções da plataforma",
        "manual",
        "guia completo",
        "ajuda completa",
        "passo a passo",
        "suporte inteligente",
        "como usar a plataforma",
        "onboarding",
    ):
        answer = build_full_platform_guide()
    elif has("login", "entrar", "senha", "credencial", "acesso"):
        answer = (
            "Para acessar: vá em Login, informe e-mail e senha. Se aparecer credencial inválida, confirme se está no ambiente correto "
            "(produção/local) e tente redefinir a senha. Se for admin, o painel fica em /admin após autenticar."
        )
    elif has("admin", "usuário", "usuario", "conta", "permiss", "role", "bloquear", "desativar"):
        answer = (
            "Como admin você pode gerenciar contas no painel /admin, seção Gestão de Contas de Usuários: "
            "alterar role (buyer/producer/supplier/admin), ativar/desativar conta e marcar verificado/superuser."
        )
    elif has("loja", "ecommerce", "adubo", "insetic", "defensivo", "implemento", "epi", "ferrament"):
        answer = (
            "A Loja Agro está em /store com categorias técnicas: adubos, defensivos, implementos, vestuário/EPI, ferramentas e irrigação. "
            "Fornecedores e admins publicam produtos em /store/manage/dashboard com ficha técnica completa."
        )
    elif has("oferta", "negocia", "negociação", "proposta", "contrato", "mediação"):
        answer = (
            "Fluxo comercial: criar oferta em /offers/new, negociar via mensagens e rotas de negociação, e usar mediação em /intermediation "
            "quando necessário."
        )
    elif has("pagamento", "transa", "wallet", "carteira", "checkout"):
        answer = (
            "Pagamentos e transações são gerenciados pelos módulos de transaction/payment/wallet. "
            "No ecommerce, o checkout está disponível em /store/checkout para evolução do fluxo de compra."
        )
    elif has("mensagem", "chat", "notifica", "alerta"):
        answer = (
            "Comunicação da plataforma: /messages para conversas, /notifications para alertas e feed de eventos. "
            "A leitura e atualização de notificações ocorre pelas APIs de notificações."
        )
    elif has("dados", "quantos", "total", "estat", "resumo"):
        total_users = db.query(User).count()
        total_offers = db.query(Offer).count()
        total_transactions = db.query(Transaction).count()
        answer = (
            "Resumo atual da plataforma: "
            f"{total_users} usuários, {total_offers} ofertas e {total_transactions} transações registradas."
        )
    elif has("rota", "url", "onde", "acessar"):
        answer = (
            "Rotas principais: / (home), /offers, /messages, /notifications, /store, /store/manage/dashboard, /admin, /profile, /strategy."
        )
    elif re.search(r"(ola|oi|bom dia|boa tarde|boa noite)", text_q):
        answer = (
            "Olá! Posso te orientar em qualquer etapa da WallFruits: acesso, gestão de contas, loja agro, ofertas, transações e administração."
        )

    return {
        "answer": answer,
        "recommendations": recommendations_payload,
        "filters": decision_filters,
        "scheduled_event": scheduled_event_payload,
    }


@app.post("/api/agenda/access/revoke")
async def revoke_agenda_temporary_access(
    current_user: User | None = Depends(get_current_user_optional),
):
    """Endpoint legado mantido por compatibilidade de clientes antigos."""
    if current_user is None:
        return {"revoked": False, "reason": "guest_or_no_session"}
    return {"revoked": False, "reason": "policy_managed"}


@app.get("/mobile-preview")
async def mobile_preview_page(request: Request, url: str | None = None):
    """Simulador visual de dispositivos móveis para validar responsividade por URL."""
    preview_url = (url or "https://wallfruits-backend.onrender.com/").strip()
    return _render_template("mobile_preview.html", request, preview_url=preview_url)


@app.get("/health")
def health():
    """Health check profundo da aplicação."""
    db_ok, db_detail, db_latency_ms = _timed_check(check_database_connection)
    redis_ok, redis_detail, redis_latency_ms = _timed_check(check_redis_connection)
    startup_ok = bool(getattr(app.state, "startup_ok", False))
    startup_error = getattr(app.state, "startup_error", None)

    critical_ok = startup_ok and db_ok
    if settings.REDIS_ENABLED:
        overall_ok = critical_ok and redis_ok
    else:
        overall_ok = critical_ok

    status_label = "ok" if overall_ok else "degraded"
    status_code = 200 if overall_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_label,
            "version": settings.API_VERSION,
            "environment": settings.APP_ENV,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                "database": {
                    "ok": db_ok,
                    "detail": db_detail,
                    "latency_ms": round(db_latency_ms, 2),
                },
                "redis": {
                    "ok": redis_ok,
                    "detail": redis_detail,
                    "enabled": settings.REDIS_ENABLED,
                    "latency_ms": round(redis_latency_ms, 2),
                },
                "startup": {"ok": startup_ok, "detail": startup_error or "ok"},
            },
        },
    )


@app.get("/api/health")
def api_health_alias():
    """Alias para manter compatibilidade com clientes legados."""
    return health()


@app.get("/api/metrics")
def runtime_metrics():
    """Métricas internas simples para diagnóstico rápido em produção."""
    with _metrics_lock:
        snapshot = dict(_request_metrics)

    total = int(snapshot["total"])
    avg_ms = (snapshot["duration_ms_total"] / total) if total else 0.0
    started_at = getattr(app.state, "started_at", None)
    uptime_seconds = 0.0
    if isinstance(started_at, datetime):
        uptime_seconds = max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds())

    return {
        "status": "ok",
        "uptime_seconds": round(uptime_seconds, 2),
        "requests": {
            "total": total,
            "2xx": int(snapshot["status_2xx"]),
            "4xx": int(snapshot["status_4xx"]),
            "5xx": int(snapshot["status_5xx"]),
            "rate_limited": int(snapshot["rate_limited"]),
            "avg_duration_ms": round(avg_ms, 2),
        },
    }


@app.get("/health/live")
def health_live():
    """Liveness probe: processo em execução."""
    return {
        "status": "alive",
        "version": settings.API_VERSION,
    }


@app.get("/health/ready")
def health_ready():
    """Readiness probe: pronto para receber tráfego."""
    db_ok, db_detail, db_latency_ms = _timed_check(check_database_connection)
    redis_ok, redis_detail, redis_latency_ms = _timed_check(check_redis_connection)
    startup_ok = bool(getattr(app.state, "startup_ok", False))
    ready = startup_ok and db_ok and (redis_ok or not settings.REDIS_ENABLED)

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": {
                "startup": startup_ok,
                "database": {
                    "ok": db_ok,
                    "detail": db_detail,
                    "latency_ms": round(db_latency_ms, 2),
                },
                "redis": {
                    "ok": redis_ok,
                    "detail": redis_detail,
                    "enabled": settings.REDIS_ENABLED,
                    "latency_ms": round(redis_latency_ms, 2),
                },
            },
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(exc.detail, "http_error", request),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_payload(exc.errors(), "validation_error", request),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler para exceções genéricas."""
    logger.error("Erro nao tratado [request_id=%s]: %s", _request_id_from(request), exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content=_error_payload("Erro interno do servidor", "internal_error", request),
    )
