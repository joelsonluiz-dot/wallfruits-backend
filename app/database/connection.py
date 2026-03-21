import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings

logger = logging.getLogger("database")

DATABASE_URL = (os.getenv("DATABASE_URL") or settings.DATABASE_URL or "").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurada. Defina no ambiente ou no arquivo .env")

IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_SUPABASE = (not IS_SQLITE) and (
    "supabase.co" in DATABASE_URL
    or "supabase.com" in DATABASE_URL
    or ".supabase." in DATABASE_URL
)

# Configurar engine baseado no tipo de banco
if IS_SQLITE:
    # Configuração para SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DB_ECHO
    )
else:
    # Configuração para PostgreSQL
    postgres_connect_args = {
        "connect_timeout": 10,
        "options": "-c timezone=UTC"
    }

    if IS_SUPABASE:
        postgres_connect_args["sslmode"] = "require"

    engine = create_engine(
        DATABASE_URL,
        echo=settings.DB_ECHO,
        pool_size=5 if IS_SUPABASE else 20,
        max_overflow=10 if IS_SUPABASE else 40,
        pool_pre_ping=True,
        connect_args=postgres_connect_args,
    )

# Tratamento de reconexão automática
@event.listens_for(engine, "connect")
def set_connection_defaults(dbapi_connection, connection_record):
    """Configurar pool_recycle para evitar 'gone away' errors"""
    del connection_record  # assinatura exigida pelo SQLAlchemy

    if not IS_SQLITE:
        cursor = dbapi_connection.cursor()
        cursor.execute("SET client_encoding='utf8'")
        cursor.close()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

Base = declarative_base()


def get_db():
    """Dependency para obter sessão do banco de dados"""
    db = SessionLocal()
    try:
        yield db
    except Exception as exc:
        db.rollback()

        # Excecoes HTTP de regra de negocio nao sao falhas de acesso ao banco.
        if getattr(exc, "status_code", None) is not None:
            raise

        logger.error(f"Erro ao acessar banco de dados: {exc}", exc_info=True)
        raise
    finally:
        db.close()


def _table_exists(conn, table_name: str) -> bool:
    if IS_SQLITE:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table_name},
        ).scalar()
        return result is not None

    result = conn.execute(
        text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar()
    return result is not None


def _ensure_users_schema_compatibility() -> None:
    """Garante colunas necessárias para autenticação na tabela users."""
    if IS_SQLITE:
        sqlite_statements = {
            "role": "ALTER TABLE users ADD COLUMN role VARCHAR(50) DEFAULT 'buyer'",
            "supabase_user_id": "ALTER TABLE users ADD COLUMN supabase_user_id VARCHAR(64)",
            "phone": "ALTER TABLE users ADD COLUMN phone VARCHAR(20)",
            "location": "ALTER TABLE users ADD COLUMN location VARCHAR(150)",
            "bio": "ALTER TABLE users ADD COLUMN bio TEXT",
            "profile_image": "ALTER TABLE users ADD COLUMN profile_image VARCHAR(500)",
            "is_active": "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1",
            "is_superuser": "ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT 0",
            "is_verified": "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0",
            "rating": "ALTER TABLE users ADD COLUMN rating INTEGER DEFAULT 0",
            "total_reviews": "ALTER TABLE users ADD COLUMN total_reviews INTEGER DEFAULT 0",
            "created_at": "ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "ALTER TABLE users ADD COLUMN updated_at DATETIME",
            "last_login": "ALTER TABLE users ADD COLUMN last_login DATETIME",
        }

        with engine.begin() as conn:
            if not _table_exists(conn, "users"):
                return

            existing_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(users)"))
            }

            for column_name, statement in sqlite_statements.items():
                if column_name not in existing_columns:
                    conn.execute(text(statement))

            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_supabase_user_id "
                    "ON users (supabase_user_id)"
                )
            )

        return

    user_statements = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'buyer'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS supabase_user_id VARCHAR(64)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS location VARCHAR(150)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image VARCHAR(500)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS rating INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS total_reviews INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_supabase_user_id ON users (supabase_user_id)",
    ]

    with engine.begin() as conn:
        if not _table_exists(conn, "users"):
            return

        for statement in user_statements:
            conn.execute(text(statement))


def ensure_auth_schema_compatibility() -> None:
    """Compatibilidade mínima necessária para fluxo de login/registro."""
    _ensure_users_schema_compatibility()


def check_database_connection() -> tuple[bool, str]:
    """Executa ping no banco para uso em health check e startup."""
    timeout_seconds = max(settings.HEALTHCHECK_TIMEOUT_SECONDS, 0.1)
    if IS_SUPABASE:
        # Supabase pode ter latência maior no cold start; evita falso negativo no boot.
        timeout_seconds = max(timeout_seconds, 8.0)

    def _ping_db() -> None:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_ping_db)
            future.result(timeout=timeout_seconds)
        return True, "ok"
    except FuturesTimeoutError:
        detail = f"timeout ao verificar banco ({timeout_seconds}s)"
        logger.error(detail)
        return False, detail
    except Exception as exc:
        logger.error("Falha no ping do banco: %s", exc)
        return False, str(exc)


def wait_for_database_ready() -> None:
    """Aguarda disponibilidade do banco respeitando retries configurados."""
    attempts = max(settings.STARTUP_DB_RETRIES, 1)
    delay = max(settings.STARTUP_DB_RETRY_DELAY_SECONDS, 0.0)

    last_error = "desconhecido"
    for attempt in range(1, attempts + 1):
        ok, detail = check_database_connection()
        if ok:
            if attempt > 1:
                logger.info("Banco ficou disponível após %s tentativa(s)", attempt)
            return

        last_error = detail
        logger.warning(
            "Banco indisponível na tentativa %s/%s: %s",
            attempt,
            attempts,
            detail,
        )
        if attempt < attempts and delay > 0:
            time.sleep(delay)

    raise RuntimeError(f"Banco indisponível após {attempts} tentativas: {last_error}")


def _ensure_offers_schema_compatibility() -> None:
    if IS_SQLITE:
        sqlite_statements = {
            "owner_profile_id": "ALTER TABLE offers ADD COLUMN owner_profile_id VARCHAR(40)",
            "public_price": "ALTER TABLE offers ADD COLUMN public_price NUMERIC(10,2)",
            "private_price": "ALTER TABLE offers ADD COLUMN private_price NUMERIC(10,2)",
            "visibility": "ALTER TABLE offers ADD COLUMN visibility VARCHAR(30) DEFAULT 'public'",
            "is_featured": "ALTER TABLE offers ADD COLUMN is_featured BOOLEAN DEFAULT 0",
            "variety": "ALTER TABLE offers ADD COLUMN variety VARCHAR(100)",
            "quality_class": "ALTER TABLE offers ADD COLUMN quality_class VARCHAR(50)",
            "certification": "ALTER TABLE offers ADD COLUMN certification VARCHAR(100)",
            "box_weight_kg": "ALTER TABLE offers ADD COLUMN box_weight_kg NUMERIC(10,2)",
            "price_per_kg": "ALTER TABLE offers ADD COLUMN price_per_kg NUMERIC(10,2)",
            "price_min_kg": "ALTER TABLE offers ADD COLUMN price_min_kg NUMERIC(10,2)",
            "price_avg_kg": "ALTER TABLE offers ADD COLUMN price_avg_kg NUMERIC(10,2)",
            "price_max_kg": "ALTER TABLE offers ADD COLUMN price_max_kg NUMERIC(10,2)",
            "available_quantity": "ALTER TABLE offers ADD COLUMN available_quantity NUMERIC(10,2)",
            "origin": "ALTER TABLE offers ADD COLUMN origin VARCHAR(100)",
            "target_market": "ALTER TABLE offers ADD COLUMN target_market VARCHAR(100)",
            "maturation": "ALTER TABLE offers ADD COLUMN maturation VARCHAR(50)",
            "shelf_life": "ALTER TABLE offers ADD COLUMN shelf_life VARCHAR(50)",
            "harvest_date_actual": "ALTER TABLE offers ADD COLUMN harvest_date_actual DATE",
            "reservation_start": "ALTER TABLE offers ADD COLUMN reservation_start DATE",
            "reservation_end": "ALTER TABLE offers ADD COLUMN reservation_end DATE",
            "property_name": "ALTER TABLE offers ADD COLUMN property_name VARCHAR(200)",
            "property_address": "ALTER TABLE offers ADD COLUMN property_address VARCHAR(300)",
            "ad_duration_days": "ALTER TABLE offers ADD COLUMN ad_duration_days INTEGER DEFAULT 30",
            "min_boxes_to_negotiate": "ALTER TABLE offers ADD COLUMN min_boxes_to_negotiate INTEGER DEFAULT 1",
            "platform_fee": "ALTER TABLE offers ADD COLUMN platform_fee NUMERIC(10,4) DEFAULT 0.03",
        }

        with engine.begin() as conn:
            if not _table_exists(conn, "offers"):
                return

            existing_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(offers)"))
            }

            for column_name, statement in sqlite_statements.items():
                if column_name not in existing_columns:
                    conn.execute(text(statement))

        return

    offer_statements = [
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS owner_profile_id UUID",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS public_price NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS private_price NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS visibility VARCHAR(30) DEFAULT 'public'",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS variety VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS quality_class VARCHAR(50)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS certification VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS box_weight_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_per_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_min_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_avg_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS price_max_kg NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS available_quantity NUMERIC(10,2)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS origin VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS target_market VARCHAR(100)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS maturation VARCHAR(50)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS shelf_life VARCHAR(50)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS harvest_date_actual DATE",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS reservation_start DATE",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS reservation_end DATE",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS property_name VARCHAR(200)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS property_address VARCHAR(300)",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS ad_duration_days INTEGER DEFAULT 30",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS min_boxes_to_negotiate INTEGER DEFAULT 1",
        "ALTER TABLE offers ADD COLUMN IF NOT EXISTS platform_fee NUMERIC(10,4) DEFAULT 0.03",
    ]

    with engine.begin() as conn:
        if not _table_exists(conn, "offers"):
            return

        for statement in offer_statements:
            conn.execute(text(statement))


def _backfill_offer_owner_profiles() -> None:
    from app.models.offer import Offer
    from app.models.user import User
    from app.services.profile_service import ProfileService

    db = SessionLocal()
    try:
        offers_missing_owner = db.query(Offer).filter(Offer.owner_profile_id.is_(None)).all()
        if not offers_missing_owner:
            return

        profile_service = ProfileService(db)
        resolved_count = 0
        unresolved_count = 0

        for offer in offers_missing_owner:
            owner_user = offer.owner
            if owner_user is None and offer.user_id is not None:
                owner_user = db.query(User).filter(User.id == offer.user_id).first()

            if owner_user is None:
                unresolved_count += 1
                continue

            owner_profile = profile_service.get_or_create_profile(owner_user)
            offer.owner_profile_id = owner_profile.id
            resolved_count += 1

        if resolved_count:
            db.commit()
            logger.info("Backfill owner_profile_id concluído: %s ofertas atualizadas", resolved_count)
        else:
            db.rollback()

        if unresolved_count:
            logger.warning(
                "Backfill owner_profile_id não conseguiu resolver %s ofertas sem dono válido",
                unresolved_count,
            )
    except Exception as exc:
        db.rollback()
        logger.error("Falha no backfill de owner_profile_id: %s", exc, exc_info=True)
    finally:
        db.close()


def _enforce_offer_owner_profile_required() -> None:
    if IS_SQLITE:
        return

    with engine.begin() as conn:
        if not _table_exists(conn, "offers"):
            return

        null_count = conn.execute(
            text("SELECT COUNT(*) FROM offers WHERE owner_profile_id IS NULL")
        ).scalar() or 0

        if null_count > 0:
            logger.warning(
                "owner_profile_id ainda possui %s registros nulos; NOT NULL não aplicado",
                null_count,
            )
            return

        conn.execute(text("ALTER TABLE offers ALTER COLUMN owner_profile_id SET NOT NULL"))


def _ensure_profiles_schema_compatibility() -> None:
    if IS_SQLITE:
        sqlite_statements = {
            "document_type": "ALTER TABLE profiles ADD COLUMN document_type VARCHAR(30)",
            "document_front_url": "ALTER TABLE profiles ADD COLUMN document_front_url VARCHAR(500)",
            "document_back_url": "ALTER TABLE profiles ADD COLUMN document_back_url VARCHAR(500)",
            "document_selfie_url": "ALTER TABLE profiles ADD COLUMN document_selfie_url VARCHAR(500)",
            "proof_of_address_url": "ALTER TABLE profiles ADD COLUMN proof_of_address_url VARCHAR(500)",
            "submitted_at": "ALTER TABLE profiles ADD COLUMN submitted_at DATETIME",
            "validated_at": "ALTER TABLE profiles ADD COLUMN validated_at DATETIME",
            "validated_by_user_id": "ALTER TABLE profiles ADD COLUMN validated_by_user_id INTEGER",
            "validation_notes": "ALTER TABLE profiles ADD COLUMN validation_notes VARCHAR(1000)",
        }

        with engine.begin() as conn:
            if not _table_exists(conn, "profiles"):
                return

            existing_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(profiles)"))
            }

            for column_name, statement in sqlite_statements.items():
                if column_name not in existing_columns:
                    conn.execute(text(statement))

        return

    profile_statements = [
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS document_type VARCHAR(30)",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS document_front_url VARCHAR(500)",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS document_back_url VARCHAR(500)",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS document_selfie_url VARCHAR(500)",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS proof_of_address_url VARCHAR(500)",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS validated_by_user_id INTEGER",
        "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS validation_notes VARCHAR(1000)",
    ]

    with engine.begin() as conn:
        if not _table_exists(conn, "profiles"):
            return

        for statement in profile_statements:
            conn.execute(text(statement))


def _ensure_intermediation_schema_compatibility() -> None:
    if IS_SQLITE:
        sqlite_statements = {
            "reviewed_by_user_id": "ALTER TABLE intermediation_requests ADD COLUMN reviewed_by_user_id INTEGER",
            "reviewed_at": "ALTER TABLE intermediation_requests ADD COLUMN reviewed_at DATETIME",
            "review_notes": "ALTER TABLE intermediation_requests ADD COLUMN review_notes VARCHAR(1000)",
        }

        with engine.begin() as conn:
            if not _table_exists(conn, "intermediation_requests"):
                return

            existing_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(intermediation_requests)"))
            }

            for column_name, statement in sqlite_statements.items():
                if column_name not in existing_columns:
                    conn.execute(text(statement))

        return

    intermediation_statements = [
        "ALTER TABLE intermediation_requests ADD COLUMN IF NOT EXISTS reviewed_by_user_id INTEGER",
        "ALTER TABLE intermediation_requests ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ",
        "ALTER TABLE intermediation_requests ADD COLUMN IF NOT EXISTS review_notes VARCHAR(1000)",
    ]

    with engine.begin() as conn:
        if not _table_exists(conn, "intermediation_requests"):
            return

        for statement in intermediation_statements:
            conn.execute(text(statement))


def _ensure_reports_schema_compatibility() -> None:
    if IS_SQLITE:
        sqlite_statements = {
            "reviewed_by_user_id": "ALTER TABLE reports ADD COLUMN reviewed_by_user_id INTEGER",
            "reviewed_at": "ALTER TABLE reports ADD COLUMN reviewed_at DATETIME",
            "resolution_notes": "ALTER TABLE reports ADD COLUMN resolution_notes VARCHAR(1000)",
        }

        with engine.begin() as conn:
            if not _table_exists(conn, "reports"):
                return

            existing_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(reports)"))
            }

            for column_name, statement in sqlite_statements.items():
                if column_name not in existing_columns:
                    conn.execute(text(statement))

        return

    report_statements = [
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS reviewed_by_user_id INTEGER",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ",
        "ALTER TABLE reports ADD COLUMN IF NOT EXISTS resolution_notes VARCHAR(1000)",
    ]

    with engine.begin() as conn:
        if not _table_exists(conn, "reports"):
            return

        for statement in report_statements:
            conn.execute(text(statement))


def _ensure_services_schema_compatibility() -> None:
    if IS_SQLITE:
        sqlite_statements = {
            "ficha_tecnica": "ALTER TABLE services ADD COLUMN ficha_tecnica JSON",
        }

        with engine.begin() as conn:
            if not _table_exists(conn, "services"):
                return

            existing_columns = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(services)"))
            }

            for column_name, statement in sqlite_statements.items():
                if column_name not in existing_columns:
                    conn.execute(text(statement))

        return

    service_statements = [
        "ALTER TABLE services ADD COLUMN IF NOT EXISTS ficha_tecnica JSONB DEFAULT '{}'::jsonb",
    ]

    with engine.begin() as conn:
        if not _table_exists(conn, "services"):
            return

        for statement in service_statements:
            conn.execute(text(statement))


def _ensure_postgres_schema_compatibility() -> None:
    """Aplica ajustes de compatibilidade para bancos já existentes."""
    _ensure_users_schema_compatibility()
    _ensure_profiles_schema_compatibility()
    _ensure_offers_schema_compatibility()
    _backfill_offer_owner_profiles()
    _enforce_offer_owner_profile_required()
    _ensure_intermediation_schema_compatibility()
    _ensure_reports_schema_compatibility()
    _ensure_services_schema_compatibility()


def init_db():
    """Inicializar o banco de dados criando todas as tabelas"""
    try:
        Base.metadata.create_all(bind=engine)
        _ensure_postgres_schema_compatibility()
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
        raise