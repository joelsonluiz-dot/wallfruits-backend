import os
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_review_queue_routes.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.ai_models import AISuggestion, UserBehaviorLog
from app.models.user import User
from app.services.ai_decision_review_service import AIDecisionReviewService
import app.routers.ai_routes as ai_routes


TEST_DB_URL = "sqlite:///./test_ai_review_queue_routes.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AIReviewQueueRoutesTests(unittest.TestCase):
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
            Path("test_ai_review_queue_routes.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        self.db.query(UserBehaviorLog).delete()
        self.db.query(AISuggestion).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.admin = User(
            name="Admin Queue",
            email="admin.queue@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
        )
        self.regular_user = User(
            name="Regular Queue",
            email="regular.queue@test.com",
            password="hash",
            role="buyer",
            is_active=True,
        )
        self.actor = User(
            name="Actor Queue",
            email="actor.queue@test.com",
            password="hash",
            role="producer",
            is_active=True,
        )
        self.db.add_all([self.admin, self.regular_user, self.actor])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.regular_user)
        self.db.refresh(self.actor)

        self.review_service = AIDecisionReviewService(self.db)

    def tearDown(self):
        self.db.close()

    def _enqueue_pending_review(self, *, event_id: int = 123) -> AISuggestion:
        row, _ = self.review_service.enqueue_review(
            user_id=self.actor.id,
            action_type="auto_negotiation",
            entity_id="offer-queue-1",
            decision={
                "event_id": event_id,
                "risk_level": "high",
                "risk_score": 0.78,
                "policy_reasons": ["high_risk"],
            },
            context={"mode": "commit"},
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def test_get_review_queue_returns_pending_items_for_admin(self):
        pending = self._enqueue_pending_review(event_id=200)

        type(self).current_user = self.admin
        response = self.client.get("/ai/ops/review-queue", params={"status_filter": "pending_review", "limit": 10})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status_filter"], "pending_review")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["id"], pending.id)
        self.assertEqual(payload["items"][0]["status"], AIDecisionReviewService.STATUS_PENDING)

    def test_get_review_queue_blocks_non_admin_user(self):
        self._enqueue_pending_review(event_id=201)

        type(self).current_user = self.regular_user
        response = self.client.get("/ai/ops/review-queue")

        self.assertEqual(response.status_code, 403)

    def test_resolve_review_queue_item_updates_status_and_logs_event(self):
        pending = self._enqueue_pending_review(event_id=202)

        type(self).current_user = self.admin
        response = self.client.post(
            f"/ai/ops/review-queue/{pending.id}/resolve",
            json={"decision": "approve", "notes": "Aprovado apos revisao"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload["item"]["status"], AIDecisionReviewService.STATUS_APPROVED)
        self.assertEqual(payload["item"]["review"]["decision"], "approve")

        self.db.expire_all()
        updated = self.db.query(AISuggestion).filter(AISuggestion.id == pending.id).first()
        self.assertIsNotNone(updated)
        self.assertEqual(updated.status, AIDecisionReviewService.STATUS_APPROVED)

        review_events = (
            self.db.query(UserBehaviorLog)
            .filter(
                UserBehaviorLog.event_type == "ai_review_queue_resolved",
                UserBehaviorLog.entity_type == "ai_review_queue",
                UserBehaviorLog.entity_id == str(pending.id),
            )
            .all()
        )
        self.assertEqual(len(review_events), 1)


if __name__ == "__main__":
    unittest.main()
