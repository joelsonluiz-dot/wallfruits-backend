import os
import unittest
from unittest.mock import patch
from pathlib import Path

# Force local SQLite so this module does not leak postgres settings into other tests.
os.environ["DATABASE_URL"] = "sqlite:///./test_payment_plans.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.payment_routes as payment_routes
from app.models.user import User


class PaymentPlansTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(payment_routes.router)

        cls.current_user = User(
            id=1,
            name="User Plano",
            email="plans@test.com",
            password="hash",
            role="buyer",
            is_active=True,
        )

        def override_get_db():
            yield None

        def override_get_current_user():
            return cls.current_user

        cls.app.dependency_overrides[payment_routes.get_db] = override_get_db
        cls.app.dependency_overrides[payment_routes.get_current_user] = override_get_current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.clear()
        try:
            Path("test_payment_plans.db").unlink(missing_ok=True)
        except Exception:
            pass

    def test_list_plans_includes_basic_pro_premium(self):
        response = self.client.get("/payment/plans")
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        plans = payload.get("plans", [])
        ids = {item.get("id") for item in plans}

        self.assertEqual(ids, {"basic", "pro", "premium"})

        pro_plan = next((item for item in plans if item.get("id") == "pro"), None)
        self.assertIsNotNone(pro_plan)
        self.assertTrue(bool(pro_plan.get("recommended")))
        self.assertIn("yearly_checkout_enabled", pro_plan)
        self.assertEqual(pro_plan.get("cta", {}).get("checkout_plan_id"), "pro")

    def test_checkout_accepts_pro_plan(self):
        with patch("app.routers.payment_routes.create_checkout_session", return_value={
            "checkout_url": "https://checkout.stripe.test/session/cs_test_pro",
            "session_id": "cs_test_pro",
        }) as checkout_mock:
            response = self.client.post(
                "/payment/checkout/pro",
                json={
                    "success_url": "https://app.test/sucesso",
                    "cancel_url": "https://app.test/cancelado",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("checkout_url", body)

        checkout_mock.assert_called_once()
        kwargs = checkout_mock.call_args.kwargs
        self.assertEqual(kwargs.get("plan"), "pro")
        self.assertEqual(kwargs.get("billing_cycle"), "monthly")


if __name__ == "__main__":
    unittest.main()
