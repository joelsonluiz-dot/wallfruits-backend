#!/usr/bin/env python3
"""
Script para resetar o banco de dados
Remove todas as tabelas e as recria do zero
"""
import logging
from sqlalchemy import inspect

from app.database.connection import engine, Base
from app.models import (
    User, Offer, Transaction, Review,
    Favorite, Message, Category
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_database():
    """Reseta o banco de dados removendo e recriando todas as tabelas"""
    try:
        # Inspecionar banco para ver tabelas existentes
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            logger.warning(f"⚠️  Tabelas existentes encontradas: {existing_tables}")
            logger.info("🔨 Deletando todas as tabelas...")
            Base.metadata.drop_all(bind=engine)
            logger.info("✅ Todas as tabelas deletadas")
        
        # Criar tabelas novamente
        logger.info("🔨 Criando tabelas do zero...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Banco de dados resetado com sucesso!")
        
        # Verificar tabelas criadas
        inspector = inspect(engine)
        new_tables = inspector.get_table_names()
        logger.info(f"📊 Tabelas criadas: {new_tables}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao resetar banco de dados: {e}")
        raise


if __name__ == "__main__":
    reset_database()
