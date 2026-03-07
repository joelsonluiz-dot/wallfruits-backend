# app/main.py

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
import sys

# Configurações
from app.core.config import settings

# database
from app.database.connection import init_db, get_db

# models (import necessário para criar tabelas)
from app.models import (
    User, Offer, Transaction, Review,
    Favorite, Message, Category
)

# routes
from app.routers import (
    offer_routes, transaction_routes, review_routes,
    favorite_routes, message_routes, category_routes,
    upload_routes, dashboard_routes
)
from app.auth import auth_routes

# auth
from app.core.auth_middleware import get_current_user_optional


# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING GLOBAL
# ═══════════════════════════════════════════════════════════════════════════════
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/app.log")
    ]
)

logger = logging.getLogger("wallfruits_api")
logger.info(f"Starting WallFruits API v{settings.API_VERSION}")


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════
app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    openapi_url="/api/openapi.json" if not settings.DEBUG else "/openapi.json",
    docs_url="/api/docs" if not settings.DEBUG else "/docs",
    redoc_url="/api/redoc" if not settings.DEBUG else "/redoc"
)


# ═══════════════════════════════════════════════════════════════════════════════
# MIDDLEWARES
# ═══════════════════════════════════════════════════════════════════════════════

# CORS - Controlar origens permitidas
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted Host - Prevenir Host Header Attacks
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATES E ARQUIVOS ESTÁTICOS
# ═══════════════════════════════════════════════════════════════════════════════
try:
    templates = Jinja2Templates(directory="templates")
    app.mount("/static", StaticFiles(directory="static"), name="static")
    logger.info("Templates e arquivos estaticos carregados")
except Exception as e:
    logger.warning(f"Aviso ao carregar templates: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZAR BANCO DE DADOS
# ═══════════════════════════════════════════════════════════════════════════════
@app.on_event("startup")
def startup_event():
    """Inicializar banco de dados ao iniciar a aplicação"""
    try:
        init_db()
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# ROTAS DA API
# ═══════════════════════════════════════════════════════════════════════════════
API_PREFIX = "/api"

# Incluir rotas com prefixo
app.include_router(auth_routes.router, prefix=API_PREFIX)
app.include_router(offer_routes.router, prefix=API_PREFIX)
app.include_router(transaction_routes.router, prefix=API_PREFIX)
app.include_router(review_routes.router, prefix=API_PREFIX)
app.include_router(favorite_routes.router, prefix=API_PREFIX)
app.include_router(message_routes.router, prefix=API_PREFIX)
app.include_router(category_routes.router, prefix=API_PREFIX)
app.include_router(upload_routes.router, prefix=API_PREFIX)
app.include_router(dashboard_routes.router, prefix=API_PREFIX)

logger.info("Todas as rotas carregadas com sucesso")


# ═══════════════════════════════════════════════════════════════════════════════
# ROTAS HTML (Frontend)
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/")
async def home(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página inicial"""
    return templates.TemplateResponse("index.html", {"request": request, "current_user": current_user})


@app.get("/login")
async def login_page(request: Request):
    """Página de login"""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register")
async def register_page(request: Request):
    """Página de registro"""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/offers")
async def offers_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    """Página de ofertas"""
    return templates.TemplateResponse("offers.html", {"request": request, "current_user": current_user})


@app.get("/qa")
async def qa_page(request: Request):
    """Página para testes manuais reais via navegador"""
    return templates.TemplateResponse("qa_tester.html", {"request": request})


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/health")
def health():
    """Verificar saúde da API"""
    return {
        "status": "ok",
        "version": settings.API_VERSION,
        "environment": "debug" if settings.DEBUG else "production"
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LIDAR COM EXCEÇÕES GLOBAIS
# ═══════════════════════════════════════════════════════════════════════════════
from fastapi.responses import JSONResponse


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handler para exceções genéricas"""
    logger.error(f"Erro nao tratado: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor"}
    )
