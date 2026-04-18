import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_phase3_ops_routes.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.ai_models import AISuggestion, UserBehaviorLog
from app.models.notification import Notification
from app.models.store_models import Order
from app.models.subscription import Subscription
from app.models.user import User
import app.routers.ai_routes as ai_routes


TEST_DB_URL = "sqlite:///./test_ai_phase3_ops_routes.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AIPhase3OpsRoutesTests(unittest.TestCase):
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
            Path("test_ai_phase3_ops_routes.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        self.db.query(UserBehaviorLog).delete()
        self.db.query(AISuggestion).delete()
        self.db.query(Notification).delete()
        self.db.query(Order).delete()
        self.db.query(Subscription).delete()
        self.db.query(User).delete()
        self.db.commit()

        now = datetime.now(timezone.utc)

        self.admin = User(
            name="Admin Fase3",
            email="admin.phase3@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
            created_at=now - timedelta(days=10),
        )
        self.regular = User(
            name="Regular Fase3",
            email="regular.phase3@test.com",
            password="hash",
            role="buyer",
            is_active=True,
            created_at=now - timedelta(days=10),
        )

        self.db.add_all([self.admin, self.regular])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.regular)

    def tearDown(self):
        self.db.close()

    def _add_decision(
        self,
        *,
        action_type: str,
        outcome: str,
        requires_human_review: bool,
        committed: bool,
        rolled_back: bool,
        created_at: datetime,
    ) -> None:
        self.db.add(
            UserBehaviorLog(
                user_id=self.admin.id,
                event_type="ai_decision_recorded",
                entity_type="autonomous_commerce",
                entity_id=f"offer-{action_type}-{int(created_at.timestamp())}",
                created_at=created_at,
                meta_json={
                    "decision": {
                        "action_type": action_type,
                        "decision_outcome": outcome,
                        "risk_level": "low" if not requires_human_review else "high",
                        "requires_human_review": requires_human_review,
                    },
                    "result": {
                        "committed": committed,
                        "rolled_back": rolled_back,
                    },
                },
            )
        )

    def test_decision_cost_monitor_returns_expected_totals(self):
        now = datetime.now(timezone.utc)

        self._add_decision(
            action_type="auto_negotiation",
            outcome="approved_autonomous",
            requires_human_review=False,
            committed=True,
            rolled_back=False,
            created_at=now - timedelta(days=2),
        )
        self._add_decision(
            action_type="auto_negotiation",
            outcome="approved_with_review",
            requires_human_review=True,
            committed=True,
            rolled_back=False,
            created_at=now - timedelta(days=2),
        )
        self._add_decision(
            action_type="auto_negotiation",
            outcome="blocked",
            requires_human_review=True,
            committed=False,
            rolled_back=False,
            created_at=now - timedelta(days=1),
        )
        self._add_decision(
            action_type="flash_auction",
            outcome="approved_autonomous",
            requires_human_review=False,
            committed=True,
            rolled_back=False,
            created_at=now - timedelta(hours=18),
        )
        self._add_decision(
            action_type="flash_auction",
            outcome="approved_autonomous",
            requires_human_review=False,
            committed=True,
            rolled_back=True,
            created_at=now - timedelta(hours=6),
        )
        self.db.commit()

        type(self).current_user = self.admin
        response = self.client.get("/ai/ops/decision-cost-monitor", params={"days": 30})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        totals = payload.get("totals", {})

        self.assertEqual(totals.get("decisions"), 5)
        self.assertAlmostEqual(float(totals.get("estimated_total_cost")), 0.75, places=4)
        self.assertAlmostEqual(float(totals.get("estimated_avg_cost")), 0.15, places=4)

        by_action = {
            item.get("action_type"): item
            for item in payload.get("by_action", [])
        }
        self.assertEqual(by_action.get("auto_negotiation", {}).get("decisions"), 3)
        self.assertEqual(by_action.get("flash_auction", {}).get("decisions"), 2)
        self.assertAlmostEqual(float(by_action.get("auto_negotiation", {}).get("estimated_total_cost", 0.0)), 0.48, places=4)
        self.assertAlmostEqual(float(by_action.get("flash_auction", {}).get("estimated_total_cost", 0.0)), 0.27, places=4)

    def test_autonomy_policy_preview_and_apply(self):
        now = datetime.now(timezone.utc)

        for i in range(8):
            self._add_decision(
                action_type="auto_negotiation",
                outcome="approved_autonomous",
                requires_human_review=False,
                committed=True,
                rolled_back=False,
                created_at=now - timedelta(hours=24 + i),
            )

        for i in range(10):
            self._add_decision(
                action_type="flash_auction",
                outcome="approved_with_review" if i < 8 else "blocked",
                requires_human_review=True,
                committed=i < 8,
                rolled_back=False,
                created_at=now - timedelta(hours=12 + i),
            )

        self.db.commit()

        type(self).current_user = self.admin

        preview = self.client.get("/ai/ops/autonomy-policy", params={"days": 30})
        self.assertEqual(preview.status_code, 200)
        preview_payload = preview.json()

        levels_current = preview_payload.get("levels_current", {})
        levels_proposed = preview_payload.get("levels_proposed", {})

        self.assertEqual(levels_current.get("auto_negotiation"), "L1")
        self.assertEqual(levels_current.get("flash_auction"), "L1")
        self.assertEqual(levels_proposed.get("auto_negotiation"), "L2")
        self.assertEqual(levels_proposed.get("flash_auction"), "L0")

        apply_resp = self.client.get("/ai/ops/autonomy-policy", params={"days": 30, "apply": "true"})
        self.assertEqual(apply_resp.status_code, 200)
        apply_payload = apply_resp.json()
        self.assertTrue(apply_payload.get("apply_performed"))
        self.assertEqual(apply_payload.get("levels_applied", {}).get("auto_negotiation"), "L2")
        self.assertEqual(apply_payload.get("levels_applied", {}).get("flash_auction"), "L0")

        stored = (
            self.db.query(UserBehaviorLog)
            .filter(
                UserBehaviorLog.event_type == "ai_autonomy_policy_applied",
                UserBehaviorLog.entity_type == "ai_autonomy_policy",
                UserBehaviorLog.entity_id == "global",
            )
            .all()
        )
        self.assertEqual(len(stored), 1)

    def test_weekly_learning_report_generates_and_uses_cache(self):
        now = datetime.now(timezone.utc)
        self._add_decision(
            action_type="auto_negotiation",
            outcome="approved_autonomous",
            requires_human_review=False,
            committed=True,
            rolled_back=False,
            created_at=now - timedelta(days=1),
        )
        self.db.commit()

        type(self).current_user = self.admin

        first = self.client.get("/ai/ops/weekly-learning-report", params={"week_offset": 0})
        self.assertEqual(first.status_code, 200)
        first_payload = first.json()
        self.assertFalse(first_payload.get("from_cache"))
        self.assertIn("report", first_payload)

        report = first_payload.get("report", {})
        self.assertIn("executive", report)
        self.assertIn("cost_monitor", report)
        self.assertIn("autonomy_policy_preview", report)

        second = self.client.get("/ai/ops/weekly-learning-report", params={"week_offset": 0})
        self.assertEqual(second.status_code, 200)
        second_payload = second.json()
        self.assertTrue(second_payload.get("from_cache"))
        self.assertEqual(second_payload.get("week_iso"), first_payload.get("week_iso"))

    def test_phase3_endpoints_block_non_admin_user(self):
        type(self).current_user = self.regular

        response = self.client.get("/ai/ops/decision-cost-monitor", params={"days": 30})
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/ai/ops/autonomy-policy", params={"days": 30})
        self.assertEqual(response.status_code, 403)

        response = self.client.get("/ai/ops/weekly-learning-report", params={"week_offset": 0})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
