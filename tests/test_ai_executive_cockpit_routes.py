import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_executive_cockpit_routes.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.ai_models import AISuggestion, UserBehaviorLog
from app.models.notification import Notification
from app.models.store_models import Order, OrderStatus
from app.models.subscription import Subscription
from app.models.user import User
from app.services.ai_decision_review_service import AIDecisionReviewService
import app.routers.ai_routes as ai_routes


TEST_DB_URL = "sqlite:///./test_ai_executive_cockpit_routes.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AIExecutiveCockpitRoutesTests(unittest.TestCase):
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
            Path("test_ai_executive_cockpit_routes.db").unlink(missing_ok=True)
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
            name="Admin Cockpit",
            email="admin.cockpit@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
            created_at=now - timedelta(days=5),
        )
        self.regular = User(
            name="Regular Cockpit",
            email="regular.cockpit@test.com",
            password="hash",
            role="buyer",
            is_active=True,
            created_at=now - timedelta(days=50),
        )
        self.customer_a = User(
            name="Cliente A",
            email="customer.a@test.com",
            password="hash",
            role="buyer",
            is_active=True,
            created_at=now - timedelta(days=3),
        )
        self.customer_b = User(
            name="Cliente B",
            email="customer.b@test.com",
            password="hash",
            role="buyer",
            is_active=True,
            created_at=now - timedelta(days=2),
        )
        self.customer_c = User(
            name="Cliente C",
            email="customer.c@test.com",
            password="hash",
            role="buyer",
            is_active=True,
            created_at=now - timedelta(days=1),
        )

        self.db.add_all([self.admin, self.regular, self.customer_a, self.customer_b, self.customer_c])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.regular)
        self.db.refresh(self.customer_a)
        self.db.refresh(self.customer_b)
        self.db.refresh(self.customer_c)

    def tearDown(self):
        self.db.close()

    def _seed_cockpit_data(self):
        now = datetime.now(timezone.utc)

        orders = [
            Order(
                customer_id=self.customer_a.id,
                total_amount=100.0,
                status=OrderStatus.PAID,
                payment_method="card",
                created_at=now - timedelta(days=2),
            ),
            Order(
                customer_id=self.customer_a.id,
                total_amount=120.0,
                status=OrderStatus.DELIVERED,
                payment_method="card",
                created_at=now - timedelta(days=1),
            ),
            Order(
                customer_id=self.customer_b.id,
                total_amount=80.0,
                status=OrderStatus.CANCELLED,
                payment_method="pix",
                created_at=now - timedelta(days=1),
            ),
            Order(
                customer_id=self.customer_c.id,
                total_amount=60.0,
                status=OrderStatus.PENDING,
                payment_method="boleto",
                created_at=now - timedelta(hours=18),
            ),
        ]

        subscriptions = [
            Subscription(
                user_id=self.customer_a.id,
                status="active",
                plan_type="pro",
                created_at=now - timedelta(days=7),
            ),
            Subscription(
                user_id=self.customer_b.id,
                status="active",
                plan_type="basic",
                created_at=now - timedelta(days=40),
            ),
        ]

        logs = [
            UserBehaviorLog(
                user_id=self.customer_a.id,
                event_type="payment_checkout_requested",
                created_at=now - timedelta(days=2),
                meta_json={"source": "test"},
            ),
            UserBehaviorLog(
                user_id=self.customer_a.id,
                event_type="store_checkout_session_requested",
                created_at=now - timedelta(days=2),
                meta_json={"source": "test"},
            ),
            UserBehaviorLog(
                user_id=self.customer_b.id,
                event_type="payment_subscription_cta_event",
                created_at=now - timedelta(days=1),
                meta_json={"source": "test"},
            ),
            UserBehaviorLog(
                user_id=self.customer_a.id,
                event_type="ai_decision_recorded",
                entity_type="autonomous_commerce",
                entity_id="offer-100",
                created_at=now - timedelta(days=1),
                meta_json={
                    "decision": {
                        "action_type": "auto_negotiation",
                        "decision_outcome": "approved_autonomous",
                        "risk_level": "low",
                        "requires_human_review": False,
                    }
                },
            ),
            UserBehaviorLog(
                user_id=self.customer_b.id,
                event_type="ai_decision_recorded",
                entity_type="autonomous_commerce",
                entity_id="offer-200",
                created_at=now - timedelta(hours=8),
                meta_json={
                    "decision": {
                        "action_type": "flash_auction",
                        "decision_outcome": "approved_with_review",
                        "risk_level": "high",
                        "requires_human_review": True,
                    }
                },
            ),
        ]

        pending_review = AISuggestion(
            user_id=self.customer_b.id,
            module=AIDecisionReviewService.MODULE,
            suggestion_type=AIDecisionReviewService.SUGGESTION_TYPE,
            title="Revisao pendente",
            content="Teste",
            priority="high",
            status=AIDecisionReviewService.STATUS_PENDING,
            confidence=0.42,
            created_at=now - timedelta(hours=5),
            meta_json={"review_key": "cockpit-1"},
        )

        alert = Notification(
            user_id=self.admin.id,
            actor_user_id=None,
            notification_type="admin_alert",
            title="Alerta operacional",
            message="Fila alta",
            resource_type="growth",
            resource_id="ops",
            is_read=False,
            created_at=now - timedelta(hours=3),
        )

        self.db.add_all(orders + subscriptions + logs + [pending_review, alert])
        self.db.commit()

    def test_executive_cockpit_returns_loops_targets_and_segments_for_admin(self):
        self._seed_cockpit_data()
        type(self).current_user = self.admin

        response = self.client.get("/ai/ops/executive-cockpit", params={"days": 30})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload.get("window_days"), 30)

        loops = payload.get("loops", {})
        conversion = loops.get("conversion", {})
        retention = loops.get("retention_expansion", {})
        efficiency = loops.get("efficiency_risk", {})

        self.assertEqual(conversion.get("orders_total"), 4)
        self.assertEqual(conversion.get("paid_or_delivered_orders"), 2)
        self.assertEqual(float(conversion.get("order_conversion_rate")), 50.0)
        self.assertEqual(float(conversion.get("gross_revenue")), 220.0)

        self.assertEqual(retention.get("active_subscriptions"), 2)
        self.assertEqual(retention.get("new_active_subscriptions"), 1)

        self.assertEqual(efficiency.get("ai_decisions_total"), 2)
        self.assertEqual(float(efficiency.get("ai_review_rate")), 50.0)
        self.assertEqual(float(efficiency.get("ai_autonomous_rate")), 50.0)
        self.assertEqual(efficiency.get("review_queue_pending"), 1)
        self.assertEqual(efficiency.get("admin_alerts_open"), 1)
        self.assertGreater(float(efficiency.get("estimated_ai_cost_total", 0.0)), 0.0)
        self.assertGreater(float(efficiency.get("estimated_cost_per_decision", 0.0)), 0.0)

        targets = payload.get("targets", {})
        self.assertIn("order_conversion_rate", targets)
        self.assertIn("ai_autonomous_rate", targets)

        self.assertIn("cost_monitor", payload)
        self.assertIn("autonomy_policy_preview", payload)
        self.assertEqual(payload.get("cost_monitor", {}).get("totals", {}).get("decisions"), 2)

        goal_gaps = payload.get("goal_gaps", [])
        self.assertTrue(any(item.get("metric") == "order_conversion_rate" for item in goal_gaps))

        segments = payload.get("profitability_by_segment", [])
        self.assertGreaterEqual(len(segments), 3)
        card_segment = next((item for item in segments if item.get("segment") == "card"), None)
        self.assertIsNotNone(card_segment)
        self.assertEqual(float(card_segment.get("gross_revenue")), 220.0)
        self.assertEqual(float(card_segment.get("order_conversion_rate")), 100.0)

        alerts = payload.get("alerts", [])
        self.assertTrue(any("Conversão de pedidos" in item for item in alerts))

        actions = payload.get("recommended_actions", [])
        self.assertTrue(any("checkout" in item.lower() for item in actions))

    def test_executive_cockpit_blocks_non_admin_user(self):
        self._seed_cockpit_data()
        type(self).current_user = self.regular

        response = self.client.get("/ai/ops/executive-cockpit", params={"days": 30})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
