import os
import unittest
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force local SQLite for deterministic and fast automated tests.
os.environ["DATABASE_URL"] = "sqlite:///./test_store_cart_checkout.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.user import User
from app.models.store_models import (
    Product,
    ProductCategory,
    ProductStatus,
    Order,
    OrderItem,
    QuoteRequest,
)
import app.routers.store_routes as store_routes


TEST_DB_URL = "sqlite:///./test_store_cart_checkout.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class StoreCartCheckoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(store_routes.router)
        cls.current_user = None

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return cls.current_user

        cls.app.dependency_overrides[store_routes.get_db] = override_get_db
        cls.app.dependency_overrides[store_routes.get_current_user] = override_get_current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.clear()
        test_engine.dispose()
        try:
            Path("test_store_cart_checkout.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        # Cleanup order matters due to FKs.
        self.db.query(OrderItem).delete()
        self.db.query(QuoteRequest).delete()
        self.db.query(Order).delete()
        self.db.query(Product).delete()
        self.db.query(ProductCategory).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.supplier = User(
            name="Fornecedor Teste",
            email="supplier@test.com",
            password="hash",
            role="supplier",
            is_active=True,
        )
        self.buyer = User(
            name="Comprador Teste",
            email="buyer@test.com",
            password="hash",
            role="buyer",
            is_active=True,
        )
        self.db.add_all([self.supplier, self.buyer])
        self.db.flush()

        category = ProductCategory(name="Insumos", slug="insumos", is_active=True)
        self.db.add(category)
        self.db.flush()

        self.product = Product(
            name="Produto Teste",
            slug="produto-teste",
            description="Produto para testes",
            price=120.0,
            stock_quantity=12,
            status=ProductStatus.PUBLISHED,
            supplier_id=self.supplier.id,
            category_id=category.id,
            images=[],
            specifications={"Unidade": "caixa"},
        )
        self.db.add(self.product)
        self.db.commit()

        type(self).current_user = self.buyer

    def tearDown(self):
        self.db.close()

    def test_cart_add_and_checkout_success(self):
        add_resp = self.client.post("/store/cart/add", json={"product_id": self.product.id, "quantity": 2})
        self.assertEqual(add_resp.status_code, 200)
        cart = add_resp.json()
        self.assertEqual(len(cart.get("items", [])), 1)
        self.assertEqual(cart["items"][0]["quantity"], 2)

        checkout_resp = self.client.post(
            "/store/checkout/complete",
            json={
                "payment_method": "pix",
                "shipping_address": {
                    "name": "Comprador Teste",
                    "phone": "(11) 98888-7777",
                    "city": "Sao Paulo",
                    "state": "SP",
                    "address": "Rua Teste, 123",
                    "zip": "01001-000",
                },
            },
        )
        self.assertEqual(checkout_resp.status_code, 200)
        payload = checkout_resp.json()
        self.assertEqual(payload["status"], "paid")
        self.assertGreater(payload["total_amount"], 0)

        # After checkout, a new open cart should be empty.
        cart_after = self.client.get("/store/cart/items")
        self.assertEqual(cart_after.status_code, 200)
        self.assertEqual(len(cart_after.json().get("items", [])), 0)

    def test_checkout_rejects_invalid_shipping_payload(self):
        self.client.post("/store/cart/add", json={"product_id": self.product.id, "quantity": 1})

        invalid_resp = self.client.post(
            "/store/checkout/complete",
            json={
                "payment_method": "pix",
                "shipping_address": {
                    "name": "Comprador Teste",
                    "phone": "999",
                    "city": "Sao Paulo",
                    "state": "S",
                    "address": "Rua Teste, 123",
                    "zip": "123",
                },
            },
        )
        self.assertEqual(invalid_resp.status_code, 422)

    def test_cart_rejects_quantity_above_stock(self):
        create_resp = self.client.post("/store/cart/add", json={"product_id": self.product.id, "quantity": 1})
        self.assertEqual(create_resp.status_code, 200)
        item_id = create_resp.json()["items"][0]["id"]

        update_resp = self.client.patch(f"/store/cart/item/{item_id}", json={"quantity": 999})
        self.assertEqual(update_resp.status_code, 400)
        self.assertIn("estoque", update_resp.json().get("detail", "").lower())

    def test_checkout_session_creates_online_payment(self):
        add_resp = self.client.post("/store/cart/add", json={"product_id": self.product.id, "quantity": 2})
        self.assertEqual(add_resp.status_code, 200)

        with patch("app.routers.store_routes.is_stripe_configured", return_value=True), patch(
            "app.routers.store_routes.create_store_order_checkout_session",
            return_value={
                "checkout_url": "https://checkout.stripe.test/session/cs_test_123",
                "session_id": "cs_test_123",
            },
        ):
            resp = self.client.post(
                "/store/checkout/session",
                json={
                    "payment_method": "cartao",
                    "shipping_address": {
                        "name": "Comprador Teste",
                        "phone": "(11) 98888-7777",
                        "city": "Sao Paulo",
                        "state": "SP",
                        "address": "Rua Teste, 123",
                        "zip": "01001-000",
                    },
                },
            )

        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["mode"], "checkout")
        self.assertEqual(payload["session_id"], "cs_test_123")
        self.assertIn("checkout_url", payload)

        # Cart is converted to a pending online checkout order, so a new open cart is created on next fetch.
        cart_after = self.client.get("/store/cart/items")
        self.assertEqual(cart_after.status_code, 200)
        self.assertEqual(len(cart_after.json().get("items", [])), 0)


if __name__ == "__main__":
    unittest.main()
