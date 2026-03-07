from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
import logging
import os

from app.core.config import settings

logger = logging.getLogger("database")

# Usar DATABASE_URL do environment se disponível
DATABASE_URL = os.getenv("DATABASE_URL", settings.DATABASE_URL)

# Configurar engine baseado no tipo de banco
if "sqlite" in DATABASE_URL:
    # Configuração para SQLite
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=settings.DB_ECHO
    )
else:
    # Configuração para PostgreSQL
    engine = create_engine(
        DATABASE_URL,
        echo=settings.DB_ECHO,
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "options": "-c timezone=UTC"
        }
    )

# Tratamento de reconexão automática
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configurar pool_recycle para evitar 'gone away' errors"""
    if "sqlite" not in str(dbapi_connection):
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
    except Exception as e:
        logger.error(f"Erro ao acessar banco de dados: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Inicializar o banco de dados criando todas as tabelas"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar banco de dados: {e}")
        raise