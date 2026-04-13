import os
import unittest
from pathlib import Path

# Force local SQLite for deterministic and fast automated tests.
os.environ["DATABASE_URL"] = "sqlite:///./test_library_catalog_routes.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base, SessionLocal, engine
from app.models.library_item import LibraryItem
from app.models.user import User
import app.routers.library_routes as library_routes


class LibraryCatalogRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(library_routes.router)
        cls.current_user = None

        def override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return cls.current_user

        cls.app.dependency_overrides[library_routes.get_db] = override_get_db
        cls.app.dependency_overrides[library_routes.get_current_user] = override_get_current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.clear()
        try:
            Path("test_library_catalog_routes.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        self.db.query(LibraryItem).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.admin = User(
            name="Admin Biblioteca",
            email="admin-biblioteca@test.com",
            password="hash",
            role="admin",
            is_active=True,
            is_superuser=False,
        )
        self.buyer = User(
            name="Leitor",
            email="leitor@test.com",
            password="hash",
            role="buyer",
            is_active=True,
            is_superuser=False,
        )

        self.db.add_all([self.admin, self.buyer])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.buyer)

        type(self).current_user = self.buyer

    def tearDown(self):
        self.db.close()

    def test_public_catalog_returns_only_admin_publications(self):
        admin_item = LibraryItem(
            user_id=self.admin.id,
            book_id="guia-campo",
            title="Guia de Campo",
            author="Equipe Admin",
            category="Producao",
            read_time="8 min",
            cover="",
            text="Conteudo oficial para leitura publica e util para todos os usuarios.",
            is_favorite=False,
            is_offline=False,
        )
        buyer_item = LibraryItem(
            user_id=self.buyer.id,
            book_id="rascunho-privado",
            title="Rascunho Privado",
            author="Usuario Comum",
            category="Teste",
            read_time="2 min",
            cover="",
            text="Esse conteudo nao deve aparecer no catalogo publico.",
            is_favorite=False,
            is_offline=False,
        )
        self.db.add_all([admin_item, buyer_item])
        self.db.commit()

        response = self.client.get("/library/catalog")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], "guia-campo")
        self.assertEqual(payload["items"][0]["title"], "Guia de Campo")

    def test_non_admin_cannot_publish_to_catalog(self):
        type(self).current_user = self.buyer

        response = self.client.post(
            "/library/catalog",
            json={
                "title": "Leitura nao autorizada",
                "author": "Usuario",
                "category": "Teste",
                "read_time": "4 min",
                "cover": "",
                "text": "Conteudo que nao pode ser publicado por usuario comum.",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_publish_update_and_delete_catalog_item(self):
        type(self).current_user = self.admin

        create_response = self.client.post(
            "/library/catalog",
            json={
                "id": "monitoramento-semanal",
                "title": "Monitoramento Semanal",
                "author": "Time Editorial",
                "category": "Gestao",
                "read_time": "6 min",
                "cover": "",
                "text": "Conteudo completo com orientacoes de monitoramento semanal para campo.",
            },
        )
        self.assertEqual(create_response.status_code, 200)

        update_response = self.client.put(
            "/library/catalog/monitoramento-semanal",
            json={
                "title": "Monitoramento Semanal Atualizado",
                "author": "Time Editorial",
                "category": "Gestao",
                "read_time": "7 min",
                "cover": "",
                "text": "Versao atualizada com melhores praticas para leitura e execucao no campo.",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.json()["title"], "Monitoramento Semanal Atualizado")

        public_response = self.client.get("/library/catalog")
        self.assertEqual(public_response.status_code, 200)
        self.assertEqual(public_response.json()["total"], 1)

        delete_response = self.client.delete("/library/catalog/monitoramento-semanal")
        self.assertEqual(delete_response.status_code, 200)
        self.assertTrue(delete_response.json()["deleted"])

        final_response = self.client.get("/library/catalog")
        self.assertEqual(final_response.status_code, 200)
        self.assertEqual(final_response.json()["total"], 0)


if __name__ == "__main__":
    unittest.main()
