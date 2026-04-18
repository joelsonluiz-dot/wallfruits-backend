import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_business_os_marketing_funnel_routes.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.ai_models import UserBehaviorLog
from app.models.user import User
import app.routers.ai_routes as ai_routes


TEST_DB_URL = "sqlite:///./test_ai_business_os_marketing_funnel_routes.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AIBusinessOSMarketingFunnelRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(ai_routes.router)
        cls.current_user = None

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        def override_get_current_user():
            return cls.current_user

        cls.app.dependency_overrides[ai_routes.get_db] = override_get_db
        cls.app.dependency_overrides[ai_routes.get_current_user] = override_get_current_user
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.app.dependency_overrides.clear()
        test_engine.dispose()
        try:
            Path("test_ai_business_os_marketing_funnel_routes.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        self.db.query(UserBehaviorLog).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.admin = User(
            name="Admin Marketing Loop",
            email="admin.marketing.loop@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
        )
        self.regular = User(
            name="Regular Marketing Loop",
            email="regular.marketing.loop@test.com",
            password="hash",
            role="buyer",
            is_active=True,
        )

        self.db.add_all([self.admin, self.regular])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.regular)

    def tearDown(self):
        self.db.close()

    def _seed_marketing_funnel_events(self):
        now = datetime.now(timezone.utc)
        rows = []

        # Segmento com conversao baixa e friccao alta.
        for i in range(4):
            rows.append(
                UserBehaviorLog(
                    user_id=self.admin.id,
                    event_type="payment_checkout_requested",
                    entity_type="subscription_plan",
                    entity_id="pro",
                    created_at=now - timedelta(hours=48 + i),
                    meta_json={
                        "source": "ads",
                        "plan": "pro",
                        "billing_cycle": "monthly",
                        "page": "pricing",
                    },
                )
            )
        for i in range(2):
            rows.append(
                UserBehaviorLog(
                    user_id=self.admin.id,
                    event_type="payment_checkout_failed",
                    entity_type="subscription_plan",
                    entity_id="pro",
                    created_at=now - timedelta(hours=36 + i),
                    meta_json={
                        "source": "ads",
                        "plan": "pro",
                        "billing_cycle": "monthly",
                        "page": "pricing",
                        "reason": "gateway_timeout",
                    },
                )
            )

        # Segmento com alta intencao de compra.
        for i in range(5):
            rows.append(
                UserBehaviorLog(
                    user_id=self.admin.id,
                    event_type="payment_checkout_requested",
                    entity_type="subscription_plan",
                    entity_id="basic",
                    created_at=now - timedelta(hours=24 + i),
                    meta_json={
                        "source": "crm",
                        "plan": "basic",
                        "billing_cycle": "monthly",
                        "page": "email",
                    },
                )
            )
        for i in range(4):
            rows.append(
                UserBehaviorLog(
                    user_id=self.admin.id,
                    event_type="payment_checkout_created",
                    entity_type="subscription_plan",
                    entity_id="basic",
                    created_at=now - timedelta(hours=12 + i),
                    meta_json={
                        "source": "crm",
                        "plan": "basic",
                        "billing_cycle": "monthly",
                        "page": "email",
                        "session_id": f"sess-{i}",
                    },
                )
            )

        self.db.add_all(rows)
        self.db.commit()

    def test_marketing_funnel_returns_segment_signals_and_orchestration(self):
        self._seed_marketing_funnel_events()
        type(self).current_user = self.admin

        response = self.client.get(
            "/ai/ops/business-os/marketing-funnel",
            params={"days": 30, "min_segment_signals": 3},
        )
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("funnel_totals", payload)
        self.assertIn("segments", payload)
        self.assertIn("signals", payload)
        self.assertIn("experiments", payload)

        self.assertGreaterEqual(int(payload.get("funnel_totals", {}).get("entries", 0)), 9)
        self.assertGreaterEqual(len(payload.get("segments", [])), 2)

        signal_types = {item.get("signal_type") for item in payload.get("signals", [])}
        self.assertIn("conversion_drop", signal_types)
        self.assertIn("high_intent_segment", signal_types)

        for item in payload.get("signals", []):
            decision = item.get("decision", {})
            self.assertEqual(decision.get("selected_agent"), "agente_growth_marketing")

    def test_marketing_funnel_persist_logs_signals_and_orchestration(self):
        self._seed_marketing_funnel_events()
        type(self).current_user = self.admin

        response = self.client.get(
            "/ai/ops/business-os/marketing-funnel",
            params={"days": 30, "min_segment_signals": 3, "persist": "true"},
        )
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertTrue(payload.get("persist_performed"))
        self.assertGreater(int(payload.get("persisted_events", 0)), 0)

        signal_rows = (
            self.db.query(UserBehaviorLog)
            .filter(UserBehaviorLog.event_type == "growth_signal_detected")
            .all()
        )
        orchestration_rows = (
            self.db.query(UserBehaviorLog)
            .filter(UserBehaviorLog.event_type == "ai_business_os_orchestrated")
            .all()
        )
        self.assertGreater(len(signal_rows), 0)
        self.assertGreater(len(orchestration_rows), 0)

    def test_marketing_funnel_blocks_non_admin(self):
        self._seed_marketing_funnel_events()
        type(self).current_user = self.regular

        response = self.client.get("/ai/ops/business-os/marketing-funnel")
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
