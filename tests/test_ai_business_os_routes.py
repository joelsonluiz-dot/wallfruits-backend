import os
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_business_os_routes.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.ai_models import UserBehaviorLog
from app.models.user import User
import app.routers.ai_routes as ai_routes


TEST_DB_URL = "sqlite:///./test_ai_business_os_routes.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AIBusinessOSRoutesTests(unittest.TestCase):
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
            Path("test_ai_business_os_routes.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        self.db.query(UserBehaviorLog).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.admin = User(
            name="Admin Business OS",
            email="admin.businessos@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
        )
        self.regular = User(
            name="Regular Business OS",
            email="regular.businessos@test.com",
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

    def test_business_os_blueprint_returns_taxonomy_and_runtime_snapshot(self):
        type(self).current_user = self.admin

        response = self.client.get("/ai/ops/business-os/blueprint", params={"days": 30})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertIn("business_os", payload)
        self.assertIn("runtime_snapshot", payload)

        business_os = payload.get("business_os", {})
        self.assertGreater(int(business_os.get("summary", {}).get("events_total", 0)), 0)

        cycle = business_os.get("architecture_cycle", [])
        self.assertIn("captar_sinais", cycle)
        self.assertIn("decidir_com_ia", cycle)

        runtime = payload.get("runtime_snapshot", {})
        self.assertIn("governance_totals", runtime)
        self.assertIn("loops", runtime)

    def test_business_os_orchestrate_event_validates_contract_and_logs_event(self):
        type(self).current_user = self.admin

        response = self.client.post(
            "/ai/ops/business-os/orchestrate-event",
            json={
                "event_type": "payment_checkout_failed",
                "event_domain": "gestao_financeira",
                "metadata": {
                    "plan": "pro"
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload.get("accepted"))

        missing = payload.get("missing_required_fields", [])
        self.assertIn("billing_cycle", missing)
        self.assertIn("reason", missing)

        decision = payload.get("decision", {})
        self.assertEqual(decision.get("selected_agent"), "agente_gestao_financeira_operacional")
        self.assertEqual(decision.get("autonomy_policy", {}).get("policy"), "human_approval")

        logs = (
            self.db.query(UserBehaviorLog)
            .filter(UserBehaviorLog.event_type == "ai_business_os_orchestrated")
            .all()
        )
        self.assertEqual(len(logs), 1)

    def test_business_os_endpoints_block_non_admin(self):
        type(self).current_user = self.regular

        response = self.client.get("/ai/ops/business-os/blueprint")
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/ai/ops/business-os/orchestrate-event",
            json={"event_type": "message_sent", "metadata": {}},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
