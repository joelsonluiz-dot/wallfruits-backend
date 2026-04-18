import csv
import io
import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_ai_governance_summary_routes.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.ai_models import AISuggestion, UserBehaviorLog
from app.models.user import User
from app.services.ai_decision_review_service import AIDecisionReviewService
import app.routers.ai_routes as ai_routes


TEST_DB_URL = "sqlite:///./test_ai_governance_summary_routes.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AIGovernanceSummaryRoutesTests(unittest.TestCase):
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
            Path("test_ai_governance_summary_routes.db").unlink(missing_ok=True)
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
            name="Admin Summary",
            email="admin.summary@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
        )
        self.regular = User(
            name="Regular Summary",
            email="regular.summary@test.com",
            password="hash",
            role="buyer",
            is_active=True,
        )
        self.actor = User(
            name="Actor Summary",
            email="actor.summary@test.com",
            password="hash",
            role="producer",
            is_active=True,
        )
        self.db.add_all([self.admin, self.regular, self.actor])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.regular)
        self.db.refresh(self.actor)

    def tearDown(self):
        self.db.close()

    def _seed_governance_data(self):
        decision_rows = [
            UserBehaviorLog(
                user_id=self.actor.id,
                event_type="ai_decision_recorded",
                entity_type="autonomous_commerce",
                entity_id="offer-1",
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
                user_id=self.actor.id,
                event_type="ai_decision_recorded",
                entity_type="autonomous_commerce",
                entity_id="offer-2",
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

        queue_rows = [
            AISuggestion(
                user_id=self.actor.id,
                module=AIDecisionReviewService.MODULE,
                suggestion_type=AIDecisionReviewService.SUGGESTION_TYPE,
                title="Fila pendente",
                content="Item pendente",
                priority="high",
                status=AIDecisionReviewService.STATUS_PENDING,
                confidence=0.45,
                meta_json={"review_key": "k1"},
            ),
            AISuggestion(
                user_id=self.actor.id,
                module=AIDecisionReviewService.MODULE,
                suggestion_type=AIDecisionReviewService.SUGGESTION_TYPE,
                title="Fila aprovada",
                content="Item aprovado",
                priority="medium",
                status=AIDecisionReviewService.STATUS_APPROVED,
                confidence=0.52,
                meta_json={"review_key": "k2"},
            ),
        ]

        self.db.add_all(decision_rows + queue_rows)
        self.db.commit()

    def test_governance_summary_returns_aggregated_metrics_for_admin(self):
        self._seed_governance_data()
        type(self).current_user = self.admin

        response = self.client.get(
            "/ai/ops/governance-summary",
            params={"days": 30, "include_recent": "true"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()

        totals = payload.get("totals", {})
        self.assertEqual(totals.get("decisions"), 2)
        self.assertEqual(totals.get("requires_human_review"), 1)
        self.assertEqual(float(totals.get("review_rate")), 50.0)
        self.assertEqual(totals.get("approved_autonomous"), 1)
        self.assertEqual(float(totals.get("autonomous_rate")), 50.0)

        by_action = payload.get("by_action", {})
        self.assertEqual(by_action.get("auto_negotiation"), 1)
        self.assertEqual(by_action.get("flash_auction"), 1)

        queue = payload.get("review_queue", {})
        self.assertEqual(queue.get("total"), 2)
        self.assertEqual(queue.get("pending"), 1)
        self.assertEqual(queue.get("approved"), 1)
        self.assertEqual(queue.get("rejected"), 0)

        recent = payload.get("recent", [])
        self.assertEqual(len(recent), 2)

    def test_governance_summary_blocks_non_admin_user(self):
        self._seed_governance_data()
        type(self).current_user = self.regular

        response = self.client.get("/ai/ops/governance-summary")
        self.assertEqual(response.status_code, 403)

    def test_governance_summary_csv_export_returns_expected_payload_for_admin(self):
        self._seed_governance_data()
        type(self).current_user = self.admin

        response = self.client.get(
            "/ai/ops/governance-summary.csv",
            params={"days": 30, "include_recent": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers.get("content-type", ""))
        self.assertIn("attachment; filename=", response.headers.get("content-disposition", ""))

        csv_text = response.text.lstrip("\ufeff")
        self.assertIn("section,key,value,event_id,user_id,created_at,action_type,decision_outcome,risk_level,requires_human_review", csv_text)
        self.assertIn("totals,decisions,2", csv_text)
        self.assertIn("review_queue,pending,1", csv_text)
        self.assertIn("review_queue,approved,1", csv_text)
        self.assertIn("recent,,,", csv_text)

    def test_governance_summary_csv_export_blocks_non_admin_user(self):
        self._seed_governance_data()
        type(self).current_user = self.regular

        response = self.client.get("/ai/ops/governance-summary.csv")
        self.assertEqual(response.status_code, 403)

    def test_governance_summary_csv_weekly_export_returns_grouped_rows(self):
        now = datetime.now(timezone.utc)
        recent_dt = now - timedelta(days=1)
        older_dt = now - timedelta(days=9)

        decision_rows = [
            UserBehaviorLog(
                user_id=self.actor.id,
                event_type="ai_decision_recorded",
                entity_type="autonomous_commerce",
                entity_id="offer-weekly-1",
                created_at=recent_dt,
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
                user_id=self.actor.id,
                event_type="ai_decision_recorded",
                entity_type="autonomous_commerce",
                entity_id="offer-weekly-2",
                created_at=older_dt,
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

        queue_rows = [
            AISuggestion(
                user_id=self.actor.id,
                module=AIDecisionReviewService.MODULE,
                suggestion_type=AIDecisionReviewService.SUGGESTION_TYPE,
                title="Fila semanal aprovada",
                content="Item aprovado",
                priority="medium",
                status=AIDecisionReviewService.STATUS_APPROVED,
                confidence=0.66,
                created_at=recent_dt,
                meta_json={"review_key": "wk-1"},
            ),
            AISuggestion(
                user_id=self.actor.id,
                module=AIDecisionReviewService.MODULE,
                suggestion_type=AIDecisionReviewService.SUGGESTION_TYPE,
                title="Fila semanal pendente",
                content="Item pendente",
                priority="high",
                status=AIDecisionReviewService.STATUS_PENDING,
                confidence=0.41,
                created_at=older_dt,
                meta_json={"review_key": "wk-2"},
            ),
        ]

        self.db.add_all(decision_rows + queue_rows)
        self.db.commit()

        type(self).current_user = self.admin
        response = self.client.get(
            "/ai/ops/governance-summary.csv",
            params={"days": 30, "granularity": "week"},
        )

        self.assertEqual(response.status_code, 200)
        csv_text = response.text.lstrip("\ufeff")
        self.assertIn("week_start,week_iso,decisions", csv_text)

        rows = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertGreaterEqual(len(rows), 2)

        recent_iso = recent_dt.isocalendar()
        older_iso = older_dt.isocalendar()
        recent_start = date.fromisocalendar(int(recent_iso.year), int(recent_iso.week), 1).isoformat()
        older_start = date.fromisocalendar(int(older_iso.year), int(older_iso.week), 1).isoformat()

        by_week = {row["week_start"]: row for row in rows}
        self.assertIn(recent_start, by_week)
        self.assertIn(older_start, by_week)

        recent_row = by_week[recent_start]
        self.assertEqual(recent_row["decisions"], "1")
        self.assertEqual(recent_row["approved_autonomous"], "1")
        self.assertEqual(recent_row["queue_approved"], "1")

        older_row = by_week[older_start]
        self.assertEqual(older_row["decisions"], "1")
        self.assertEqual(older_row["requires_human_review"], "1")
        self.assertEqual(older_row["queue_pending"], "1")


if __name__ == "__main__":
    unittest.main()
