import os
import unittest
from pathlib import Path

# Force local SQLite for deterministic tests.
os.environ["DATABASE_URL"] = "sqlite:///./test_payment_preferences.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base, SessionLocal, engine
from app.models.user import User
import app.routers.payment_routes as payment_routes


class PaymentPreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(payment_routes.router)
        cls.current_user = None

        def override_get_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return cls.current_user

        cls.app.dependency_overrides[payment_routes.get_db] = override_get_db
        cls.app.dependency_overrides[payment_routes.get_current_user] = override_get_current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.clear()
        try:
            Path("test_payment_preferences.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        self.db.query(User).delete()
        self.db.commit()

        self.user = User(
            name="Comprador Config",
            email="payment-config@test.com",
            password="hash",
            role="buyer",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        type(self).current_user = self.user

    def tearDown(self):
        self.db.close()

    def test_get_default_payment_preferences(self):
        resp = self.client.get("/payment/preferences")
        self.assertEqual(resp.status_code, 200)

        payload = resp.json()
        self.assertIn("billing_address", payload)
        self.assertIn("pix", payload)
        self.assertIn("card", payload)
        self.assertEqual(payload.get("default_method"), "card")
        self.assertFalse(payload.get("is_ready_for_subscription_upgrade"))

    def test_update_payment_preferences_masks_card_data(self):
        payload = {
            "billing_address": {
                "full_name": "Comprador Config",
                "phone": "(11) 98888-7777",
                "address_line1": "Rua das Palmeiras, 300",
                "address_line2": "Sala 8",
                "city": "Sao Paulo",
                "state": "SP",
                "zip_code": "01001-000",
                "country": "BR",
            },
            "pix": {
                "key_type": "email",
                "key": "financeiro@wallfruits.com",
                "holder_name": "Comprador Config",
            },
            "card": {
                "holder_name": "Comprador Config",
                "number": "4242 4242 4242 4242",
                "exp_month": 12,
                "exp_year": 2099,
                "brand": "visa",
            },
            "default_method": "card",
            "use_for_subscriptions": True,
        }

        save_resp = self.client.put("/payment/preferences", json=payload)
        self.assertEqual(save_resp.status_code, 200)

        saved = save_resp.json()
        card = saved.get("card", {})
        pix = saved.get("pix", {})

        self.assertEqual(card.get("last4"), "4242")
        self.assertEqual(card.get("number_masked"), "**** **** **** 4242")
        self.assertEqual(pix.get("key_masked"), "fin***com")
        self.assertTrue(saved.get("is_ready_for_subscription_upgrade"))
        self.assertNotIn("number", card)

        load_resp = self.client.get("/payment/preferences")
        self.assertEqual(load_resp.status_code, 200)
        loaded = load_resp.json()
        self.assertEqual(loaded.get("default_method"), "card")
        self.assertEqual(loaded.get("card", {}).get("last4"), "4242")


if __name__ == "__main__":
    unittest.main()
