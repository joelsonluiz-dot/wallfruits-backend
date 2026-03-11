"""App principal da API WallFruits com startup e observabilidade robustos."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
import sys
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
from app.cache.redis_client import check_redis_connection
from app.core.auth_middleware import get_current_user_optional
from app.core.config import settings
from app.database.connection import (
    check_database_connection,
    init_db,
    wait_for_database_ready,
)
from app.models import Category, Favorite, Message, Offer, Review, Transaction, User
from app.routers import (
    category_routes,
    dashboard_routes,
    favorite_routes,
    gamification_routes,
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
    transaction_routes,
    upload_routes,
    wallet_routes,
)


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

    yield


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

    started_at = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started_at

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{elapsed:.4f}"
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
    return templates.TemplateResponse(template_name, {"request": request, **context})


API_PREFIX = "/api"

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
app.include_router(payment_routes.router, prefix=API_PREFIX)
app.include_router(social_routes.router, prefix=API_PREFIX)
app.include_router(notification_routes.router, prefix=API_PREFIX)

@app.get("/")
async def home(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página inicial."""
    return _render_template("index.html", request, current_user=current_user)


@app.get("/login")
async def login_page(request: Request):
    """Página de login."""
    return _render_template("login.html", request)


@app.get("/register")
async def register_page(request: Request):
    """Página de registro."""
    return _render_template("register.html", request)


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


@app.get("/qa")
async def qa_page(request: Request):
    """Redireciona a antiga rota de QA para o fluxo oficial de criação de oferta."""
    return RedirectResponse(url="/offers/new", status_code=302)


@app.get("/health")
def health():
    """Health check profundo da aplicação."""
    db_ok, db_detail = check_database_connection()
    redis_ok, redis_detail = check_redis_connection()
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
                "database": {"ok": db_ok, "detail": db_detail},
                "redis": {
                    "ok": redis_ok,
                    "detail": redis_detail,
                    "enabled": settings.REDIS_ENABLED,
                },
                "startup": {"ok": startup_ok, "detail": startup_error or "ok"},
            },
        },
    )


@app.get("/api/health")
def api_health_alias():
    """Alias para manter compatibilidade com clientes legados."""
    return health()


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
    db_ok, db_detail = check_database_connection()
    startup_ok = bool(getattr(app.state, "startup_ok", False))
    ready = startup_ok and db_ok

    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": {
                "startup": startup_ok,
                "database": {
                    "ok": db_ok,
                    "detail": db_detail,
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
