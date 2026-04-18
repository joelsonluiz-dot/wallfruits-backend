import os
import unittest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_decision_review_service.db"

from app.database.connection import Base
from app.models.ai_models import AISuggestion
from app.models.user import User
from app.services.ai_decision_review_service import AIDecisionReviewService


TEST_DB_URL = "sqlite:///./test_ai_decision_review_service.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AIDecisionReviewServiceTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        test_engine.dispose()
        try:
            Path("test_ai_decision_review_service.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=test_engine)
        self.db = TestingSessionLocal()

        self.db.query(AISuggestion).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.actor = User(
            name="Actor IA",
            email="actor.review@test.com",
            password="hash",
            role="producer",
            is_active=True,
        )
        self.reviewer = User(
            name="Admin Review",
            email="admin.review@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
        )
        self.db.add_all([self.actor, self.reviewer])
        self.db.commit()
        self.db.refresh(self.actor)
        self.db.refresh(self.reviewer)

        self.service = AIDecisionReviewService(self.db)

    def tearDown(self):
        self.db.close()

    def test_enqueue_review_is_idempotent_by_review_key(self):
        decision = {
            "event_id": 77,
            "risk_level": "high",
            "risk_score": 0.81,
            "policy_reasons": ["high_risk", "autonomy_mode_assistida"],
        }

        row_1, created_1 = self.service.enqueue_review(
            user_id=self.actor.id,
            action_type="auto_negotiation",
            entity_id="offer-abc",
            decision=decision,
            context={"mode": "commit"},
        )
        row_2, created_2 = self.service.enqueue_review(
            user_id=self.actor.id,
            action_type="auto_negotiation",
            entity_id="offer-abc",
            decision=decision,
            context={"mode": "commit"},
        )

        self.assertTrue(created_1)
        self.assertFalse(created_2)
        self.assertEqual(row_1.id, row_2.id)
        self.assertEqual(row_1.status, AIDecisionReviewService.STATUS_PENDING)

    def test_resolve_review_updates_status_and_audit_metadata(self):
        decision = {
            "event_id": 91,
            "risk_level": "medium",
            "risk_score": 0.48,
            "policy_reasons": ["autonomy_mode_assistida"],
        }
        row, _ = self.service.enqueue_review(
            user_id=self.actor.id,
            action_type="flash_auction",
            entity_id="offer-xyz",
            decision=decision,
            context={"mode": "commit"},
        )

        resolved = self.service.resolve_review(
            review_id=row.id,
            decision="approve",
            reviewer=self.reviewer,
            notes="Aprovado para operacao monitorada",
        )

        self.assertEqual(resolved.status, AIDecisionReviewService.STATUS_APPROVED)
        payload = self.service.to_payload(resolved)
        self.assertEqual(payload["review"].get("decision"), "approve")
        self.assertEqual(payload["review"].get("reviewed_by_user_id"), self.reviewer.id)


if __name__ == "__main__":
    unittest.main()