"""App principal da API WallFruits com startup e observabilidade robustos."""

import asyncio
from contextlib import asynccontextmanager
from collections import defaultdict, deque
from datetime import datetime, timezone
import logging
import os
import re
import sys
from threading import Lock
import time
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import auth_routes
from app.cache.redis_client import check_redis_connection, delete_cache, get_cache, set_cache
from app.core.auth_middleware import get_current_user_optional, get_current_user
from app.core.config import settings
from app.core.domain_enums import SubscriptionPlanType, SubscriptionStatus
from app.database.connection import (
    check_database_connection,
    init_db,
    SessionLocal,
    wait_for_database_ready,
    get_db,
)
from sqlalchemy.orm import Session
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

    worker_task: asyncio.Task | None = None
    if app_obj.state.startup_ok and settings.AGENDA_PREDICTIVE_WORKER_ENABLED:
        worker_task = asyncio.create_task(_agenda_predictive_worker())
        app_obj.state.agenda_predictive_worker_task = worker_task

    try:
        yield
    finally:
        if worker_task and not worker_task.done():
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                logger.info("Agenda predictive worker encerrado")


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


def _render_template(template_name: str, request: Request, **context: Any):
    if templates is None:
        raise HTTPException(503, "Templates indisponíveis neste ambiente")
    # Usa assinatura nomeada para compatibilidade entre versões da Starlette.
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={"request": request, **context},
    )


AGENDA_TEMP_ACCESS_TTL_SECONDS = 300
AGENDA_TEMP_ACCESS_KEY_PREFIX = "agenda:temp:access"
AGENDA_TEMP_REVOKED_KEY_PREFIX = "agenda:temp:revoked"


def _agenda_temp_access_key(user_id: int) -> str:
    return f"{AGENDA_TEMP_ACCESS_KEY_PREFIX}:{user_id}"


def _agenda_temp_revoked_key(user_id: int) -> str:
    return f"{AGENDA_TEMP_REVOKED_KEY_PREFIX}:{user_id}"


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


def _user_last_login_dt(user: User) -> datetime | None:
    last_login = getattr(user, "last_login", None)
    if not last_login:
        return None
    if last_login.tzinfo is None:
        return last_login.replace(tzinfo=timezone.utc)
    return last_login


def _revoke_temporary_agenda_access(user: User):
    delete_cache(_agenda_temp_access_key(user.id))
    set_cache(
        _agenda_temp_revoked_key(user.id),
        datetime.now(timezone.utc).isoformat(),
        expire=60 * 60 * 24 * 14,
    )


def _is_temporary_access_revoked_for_login(user: User) -> bool:
    revoked_dt = _parse_cache_datetime(get_cache(_agenda_temp_revoked_key(user.id)))
    if revoked_dt is None:
        return False

    last_login = _user_last_login_dt(user)
    if last_login and revoked_dt < last_login:
        delete_cache(_agenda_temp_revoked_key(user.id))
        return False

    return True


def _resolve_or_create_temp_agenda_expires_at(user: User) -> int | None:
    now = datetime.now(timezone.utc)
    last_login = _user_last_login_dt(user)
    temp_key = _agenda_temp_access_key(user.id)
    start_dt = _parse_cache_datetime(get_cache(temp_key))

    if start_dt and last_login and start_dt < last_login:
        start_dt = None
        delete_cache(temp_key)

    if start_dt is None:
        start_dt = now
        set_cache(temp_key, start_dt.isoformat(), expire=60 * 60 * 24)

    expires_at = int(start_dt.timestamp()) + AGENDA_TEMP_ACCESS_TTL_SECONDS
    if now.timestamp() >= expires_at:
        _revoke_temporary_agenda_access(user)
        return None

    return expires_at


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
    """Página da biblioteca de leitura baseada em dados locais do navegador."""
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
    return _render_template("messages.html", request, current_user=current_user)


@app.get("/notifications")
async def notifications_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de feed de notificações."""
    return _render_template("notifications.html", request, current_user=current_user)


@app.get("/me/profile")
async def my_profile_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de perfil do usuário logado."""
    return _render_template("profile.html", request, current_user=current_user, viewed_user_id=None)


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
    
    return _render_template("store/index.html", request, products=products, categories=categories, current_user=current_user, search_query=q, active_category=category)

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
        next_path = request.url.path
        return RedirectResponse(url=f"/login?next={next_path}", status_code=307)

    if _is_agenda_entitled(db, current_user):
        return _render_template(
            "ai_agent.html",
            request,
            current_user=current_user,
            agenda_is_entitled=True,
            agenda_temporary_access=False,
            agenda_access_expires_at=None,
        )

    if _is_temporary_access_revoked_for_login(current_user):
        return _render_template(
            "ai_agent_access_denied.html",
            request,
            current_user=current_user,
        )

    expires_at = _resolve_or_create_temp_agenda_expires_at(current_user)
    if expires_at is None:
        return _render_template(
            "ai_agent_access_denied.html",
            request,
            current_user=current_user,
        )

    return _render_template(
        "ai_agent.html",
        request,
        current_user=current_user,
        agenda_is_entitled=False,
        agenda_temporary_access=True,
        agenda_access_expires_at=expires_at,
    )


@app.get("/ai_agent")
async def ai_agent_page_legacy_alias():
    """Alias legado para preservar links antigos da agenda inteligente."""
    return RedirectResponse(url="/ai-agent", status_code=307)


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

    text_q = question.lower()

    def has(*terms: str) -> bool:
        return any(term in text_q for term in terms)

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

    if has("login", "entrar", "senha", "credencial", "acesso"):
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
    elif re.search(r"(olá|oi|bom dia|boa tarde|boa noite)", text_q):
        answer = (
            "Olá! Posso te orientar em qualquer etapa da WallFruits: acesso, gestão de contas, loja agro, ofertas, transações e administração."
        )

    return {"answer": answer}


@app.post("/api/agenda/access/revoke")
async def revoke_agenda_temporary_access(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Revoga acesso temporário da agenda para não assinantes/admin."""
    if _is_agenda_entitled(db, current_user):
        return {"revoked": False, "reason": "entitled"}

    _revoke_temporary_agenda_access(current_user)
    return {"revoked": True}


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
