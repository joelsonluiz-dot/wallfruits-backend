import os
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_admin_ai_governance_e2e.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base
from app.models.ai_models import AISuggestion, UserBehaviorLog
from app.models.user import User
from app.services.ai_decision_review_service import AIDecisionReviewService
import app.routers.ai_routes as ai_routes


TEST_DB_URL = "sqlite:///./test_admin_ai_governance_e2e.db"
test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


class AdminAIGovernanceFlowE2ETests(unittest.TestCase):
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
            Path("test_admin_ai_governance_e2e.db").unlink(missing_ok=True)
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
            name="Admin E2E",
            email="admin.e2e@test.com",
            password="hash",
            role="admin",
            is_superuser=True,
            is_active=True,
        )
        self.actor = User(
            name="Actor E2E",
            email="actor.e2e@test.com",
            password="hash",
            role="producer",
            is_active=True,
        )
        self.db.add_all([self.admin, self.actor])
        self.db.commit()
        self.db.refresh(self.admin)
        self.db.refresh(self.actor)

        self.review_service = AIDecisionReviewService(self.db)

    def tearDown(self):
        self.db.close()

    def _enqueue_pending_review(self, *, event_id: int, entity_id: str) -> AISuggestion:
        row, _ = self.review_service.enqueue_review(
            user_id=self.actor.id,
            action_type="auto_negotiation",
            entity_id=entity_id,
            decision={
                "event_id": event_id,
                "risk_level": "high",
                "risk_score": 0.84,
                "policy_reasons": ["high_risk", "autonomy_mode_assistida"],
            },
            context={"mode": "commit"},
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def test_admin_l1_queue_interface_flow_approve_and_reject_end_to_end(self):
        admin_template = Path("templates/admin.html").read_text(encoding="utf-8")
        self.assertIn('id="refreshAiGovernanceBtn"', admin_template)
        self.assertIn('id="aiGovWindowDays"', admin_template)
        self.assertIn('id="exportAiGovernanceCsvBtn"', admin_template)
        self.assertIn('id="exportAiGovernanceCsvWeeklyBtn"', admin_template)
        self.assertIn('id="refreshAiExecutiveBtn"', admin_template)
        self.assertIn('id="refreshAiBoMarketingBtn"', admin_template)
        self.assertIn('id="persistAiBoMarketingBtn"', admin_template)
        self.assertIn('id="aiBoMinSignals"', admin_template)
        self.assertIn('id="applyAiAutonomyBtn"', admin_template)
        self.assertIn('id="generateAiWeeklyReportBtn"', admin_template)
        self.assertIn('id="aiExecKpisGrid"', admin_template)
        self.assertIn('id="aiExecSegmentsRows"', admin_template)
        self.assertIn('id="aiBoMarketingKpisGrid"', admin_template)
        self.assertIn('id="aiBoMarketingSignalsRows"', admin_template)
        self.assertIn("resolveAiReviewItem", admin_template)
        self.assertIn("/ai/ops/review-queue/${reviewId}/resolve", admin_template)
        self.assertIn("/ai/ops/governance-summary?days=${encodeURIComponent(days)}&include_recent=true", admin_template)
        self.assertIn("/ai/ops/governance-summary.csv", admin_template)
        self.assertIn("/ai/ops/executive-cockpit?days=${encodeURIComponent(days)}", admin_template)
        self.assertIn("/ai/ops/business-os/marketing-funnel?days=", admin_template)
        self.assertIn("min_segment_signals=${encodeURIComponent(minSignals)}", admin_template)
        self.assertIn("/ai/ops/autonomy-policy?days=${encodeURIComponent(days)}&apply=true", admin_template)
        self.assertIn("/ai/ops/weekly-learning-report?week_offset=0&regenerate=true", admin_template)
        self.assertIn("granularity=${encodeURIComponent(granularity)}", admin_template)

        row_a = self._enqueue_pending_review(event_id=3101, entity_id="offer-e2e-1")
        row_b = self._enqueue_pending_review(event_id=3102, entity_id="offer-e2e-2")

        type(self).current_user = self.admin

        queue_pending = self.client.get(
            "/ai/ops/review-queue",
            params={"status_filter": "pending_review", "limit": 20},
        )
        self.assertEqual(queue_pending.status_code, 200)
        payload_pending = queue_pending.json()
        self.assertEqual(payload_pending.get("total"), 2)
        pending_ids = {item.get("id") for item in payload_pending.get("items", [])}
        self.assertEqual(pending_ids, {row_a.id, row_b.id})

        approve_resp = self.client.post(
            f"/ai/ops/review-queue/{row_a.id}/resolve",
            json={"decision": "approve", "notes": "Aprovado no fluxo E2E"},
        )
        self.assertEqual(approve_resp.status_code, 200)
        self.assertEqual(approve_resp.json().get("item", {}).get("status"), AIDecisionReviewService.STATUS_APPROVED)

        reject_resp = self.client.post(
            f"/ai/ops/review-queue/{row_b.id}/resolve",
            json={"decision": "reject", "notes": "Rejeitado no fluxo E2E"},
        )
        self.assertEqual(reject_resp.status_code, 200)
        self.assertEqual(reject_resp.json().get("item", {}).get("status"), AIDecisionReviewService.STATUS_REJECTED)

        queue_all = self.client.get(
            "/ai/ops/review-queue",
            params={"status_filter": "all", "limit": 20},
        )
        self.assertEqual(queue_all.status_code, 200)
        payload_all = queue_all.json()
        self.assertEqual(payload_all.get("total"), 2)

        status_counts = {"pending_review": 0, "approved": 0, "rejected": 0}
        for item in payload_all.get("items", []):
            status = item.get("status")
            if status in status_counts:
                status_counts[status] += 1

        self.assertEqual(status_counts["pending_review"], 0)
        self.assertEqual(status_counts["approved"], 1)
        self.assertEqual(status_counts["rejected"], 1)

        summary_resp = self.client.get("/ai/ops/governance-summary", params={"days": 30})
        self.assertEqual(summary_resp.status_code, 200)
        summary_payload = summary_resp.json()
        review_queue = summary_payload.get("review_queue", {})
        self.assertEqual(review_queue.get("total"), 2)
        self.assertEqual(review_queue.get("pending"), 0)
        self.assertEqual(review_queue.get("approved"), 1)
        self.assertEqual(review_queue.get("rejected"), 1)

        cockpit_resp = self.client.get("/ai/ops/executive-cockpit", params={"days": 30})
        self.assertEqual(cockpit_resp.status_code, 200)
        cockpit_payload = cockpit_resp.json()
        efficiency = cockpit_payload.get("loops", {}).get("efficiency_risk", {})
        self.assertEqual(efficiency.get("review_queue_pending"), 0)

        business_os_marketing_resp = self.client.get(
            "/ai/ops/business-os/marketing-funnel",
            params={"days": 30, "min_segment_signals": 3, "persist": "true"},
        )
        self.assertEqual(business_os_marketing_resp.status_code, 200)
        business_os_marketing_payload = business_os_marketing_resp.json()
        self.assertIn("signals", business_os_marketing_payload)
        self.assertIn("experiments", business_os_marketing_payload)
        self.assertIn("persist_performed", business_os_marketing_payload)
        if business_os_marketing_payload.get("signals"):
            self.assertTrue(business_os_marketing_payload.get("persist_performed"))
        else:
            self.assertFalse(business_os_marketing_payload.get("persist_performed"))

        autonomy_resp = self.client.get("/ai/ops/autonomy-policy", params={"days": 30, "apply": "true"})
        self.assertEqual(autonomy_resp.status_code, 200)
        self.assertTrue(autonomy_resp.json().get("apply_performed"))

        weekly_report_resp = self.client.get(
            "/ai/ops/weekly-learning-report",
            params={"week_offset": 0, "regenerate": "true"},
        )
        self.assertEqual(weekly_report_resp.status_code, 200)
        self.assertIn("report", weekly_report_resp.json())

        csv_resp = self.client.get("/ai/ops/governance-summary.csv", params={"days": 30})
        self.assertEqual(csv_resp.status_code, 200)
        csv_text = csv_resp.text.lstrip("\ufeff")
        self.assertIn("review_queue,pending,0", csv_text)
        self.assertIn("review_queue,approved,1", csv_text)
        self.assertIn("review_queue,rejected,1", csv_text)

        weekly_csv_resp = self.client.get(
            "/ai/ops/governance-summary.csv",
            params={"days": 30, "granularity": "week"},
        )
        self.assertEqual(weekly_csv_resp.status_code, 200)
        weekly_csv_text = weekly_csv_resp.text.lstrip("\ufeff")
        self.assertIn("week_start,week_iso,decisions", weekly_csv_text)


if __name__ == "__main__":
    unittest.main()
