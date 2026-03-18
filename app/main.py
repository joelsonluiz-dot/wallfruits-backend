"""App principal da API WallFruits com startup e observabilidade robustos."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
import re
import sys
import time
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import auth_routes
from app.cache.redis_client import check_redis_connection
from app.core.auth_middleware import get_current_user_optional, get_current_user
from app.core.config import settings
from app.database.connection import (
    check_database_connection,
    init_db,
    wait_for_database_ready,
    get_db,
)
from sqlalchemy.orm import Session
from app.models import Category, Favorite, Message, Offer, Review, Transaction, User
from app.routers import (
    store_routes,
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
app.include_router(store_routes.router)  # Loja Agrícola (HTML + API)
app.include_router(store_routes.router, prefix=API_PREFIX)  # Alias /api/store para chamadas JS

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


@app.get("/ai-agent")
async def ai_agent_page(request: Request):
    """Interface web do assistente IA embutida no botão flutuante."""
    return _render_template("ai_agent.html", request)


@app.post("/api/ai-agent/ask")
async def ai_agent_ask(payload: dict[str, Any], db: Session = Depends(get_db)):
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


@app.get("/mobile-preview")
async def mobile_preview_page(request: Request, url: str | None = None):
    """Simulador visual de dispositivos móveis para validar responsividade por URL."""
    preview_url = (url or "https://wallfruits-backend.onrender.com/").strip()
    return _render_template("mobile_preview.html", request, preview_url=preview_url)


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
