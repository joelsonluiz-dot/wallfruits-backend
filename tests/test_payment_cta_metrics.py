import os
import unittest
from pathlib import Path

# Force local SQLite so this module does not leak postgres settings into other tests.
os.environ["DATABASE_URL"] = "sqlite:///./test_payment_cta_metrics.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.payment_routes as payment_routes
import app.cache.redis_client as redis_client
from app.models.user import User


class PaymentCtaMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        payment_routes.settings.REDIS_ENABLED = False
        redis_client.settings.REDIS_ENABLED = False

        cls.app = FastAPI()
        cls.app.include_router(payment_routes.router)

        cls.admin_user = User(
            id=1,
            name="Admin",
            email="admin@test.com",
            password="hash",
            role="admin",
            is_active=True,
            is_superuser=False,
        )
        cls.current_user = cls.admin_user
        cls.optional_user = None

        def override_get_db():
            yield None

        def override_get_current_user():
            return cls.current_user

        def override_get_current_user_optional():
            return cls.optional_user

        cls.app.dependency_overrides[payment_routes.get_db] = override_get_db
        cls.app.dependency_overrides[payment_routes.get_current_user] = override_get_current_user
        cls.app.dependency_overrides[payment_routes.get_current_user_optional] = override_get_current_user_optional
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.clear()
        try:
            Path("test_payment_cta_metrics.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        type(self).current_user = type(self).admin_user
        type(self).optional_user = None
        payment_routes._reset_subscription_cta_metrics_for_tests()

    def test_track_event_and_read_summary(self):
        event_resp = self.client.post(
            "/payment/subscription-cta/event",
            json={
                "event": "pricing_cta_click",
                "variant": "b",
                "plan_id": "pro",
                "billing_cycle": "monthly",
                "source": "pricing-page",
                "page": "/pricing",
            },
        )
        self.assertEqual(event_resp.status_code, 202)
        event_payload = event_resp.json()
        self.assertTrue(event_payload.get("accepted"))
        self.assertEqual(event_payload.get("variant"), "b")

        summary_resp = self.client.get("/payment/subscription-cta/summary?include_recent=true&recent_limit=5")
        self.assertEqual(summary_resp.status_code, 200)
        summary = summary_resp.json()

        self.assertGreaterEqual(summary.get("total_events", 0), 1)
        self.assertGreaterEqual(summary.get("by_variant", {}).get("b", {}).get("clicks", 0), 1)
        self.assertGreaterEqual(summary.get("by_plan", {}).get("pro", {}).get("clicks", 0), 1)

        recent = summary.get("recent", [])
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].get("event"), "pricing_cta_click")
        self.assertEqual(recent[0].get("auth"), "guest")

    def test_summary_requires_admin(self):
        type(self).current_user = User(
            id=2,
            name="Buyer",
            email="buyer@test.com",
            password="hash",
            role="buyer",
            is_active=True,
            is_superuser=False,
        )

        resp = self.client.get("/payment/subscription-cta/summary")
        self.assertEqual(resp.status_code, 403)

    def test_invalid_variant_returns_422(self):
        resp = self.client.post(
            "/payment/subscription-cta/event",
            json={
                "event": "pricing_cta_click",
                "variant": "x",
            },
        )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
