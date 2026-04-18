import os
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Force local SQLite for deterministic and fast automated tests.
os.environ["DATABASE_URL"] = "sqlite:///./test_ai_agenda_smoke.db"

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.connection import Base, SessionLocal, engine
from app.models.agenda_event import AgendaEvent
from app.models.ai_models import UserBehaviorLog
from app.models.notification import Notification
from app.models.user import User
import app.routers.ai_routes as ai_routes


class AIAgendaSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = FastAPI()
        cls.app.include_router(ai_routes.router)
        cls.current_user = None

        cls._originals = {
            "build_market_snapshot": ai_routes.MarketIntelligenceAI.build_market_snapshot,
            "market_automations": ai_routes.MarketIntelligenceAI.materialize_guardrail_automations,
            "build_autonomous_plan": ai_routes.AutonomousCommerceAI.build_autonomous_plan,
            "autonomous_automations": ai_routes.AutonomousCommerceAI.materialize_guardrail_automations,
            "suggest_best_slots": ai_routes.SmartSchedulingAI.suggest_best_slots,
            "get_cache": ai_routes.get_cache,
            "set_cache": ai_routes.set_cache,
            "emit_predictive": ai_routes.emit_predictive_notifications_for_user,
            "create_rule_notifications": ai_routes.maybe_create_rule_notifications,
        }

        def fake_build_market_snapshot(self, *, user_id, profile):
            return {
                "recommended_actions": [
                    {
                        "type": "market_watch",
                        "source": "notifications",
                        "base_impact": 70,
                        "urgency": 1.0,
                        "title": "Monitorar mercado",
                        "description": "Acompanhar oscilação diária de preços.",
                        "cta": "/strategy",
                    }
                ]
            }

        def fake_market_automations(self, *, user_id, profile, market_snapshot):
            return {"events_created": 0, "automations": []}

        def fake_build_autonomous_plan(self, *, user_id, profile, market_snapshot):
            return {
                "recommended_actions": [
                    {
                        "type": "auto_negotiation",
                        "source": "offers",
                        "base_impact": 72,
                        "urgency": 1.05,
                        "title": "Negociação autônoma sugerida",
                        "description": "Sugestão preparada para execução transacional.",
                        "cta": "/offers",
                    }
                ],
                "recommended_deals": [
                    {
                        "offer_id": "smoke-offer-1",
                        "buyer_user_id": 999999,
                        "buyer_name": "Comprador Smoke",
                        "buyer_location": "SP",
                        "proposed_unit_price": 123.45,
                        "expected_margin_pct": 0.12,
                        "guardrails_ok": True,
                        "max_response_hours": 8,
                        "response_deadline_at": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat(),
                        "product_name": "Tomate Smoke",
                    }
                ],
                "flash_auction_candidates": [],
            }

        def fake_autonomous_automations(self, *, user_id, profile, autonomous_plan):
            return {"events_created": 0, "automations": []}

        async def fake_suggest_best_slots(
            self,
            *,
            user_id,
            location_lat,
            location_lon,
            availability,
            persist_suggestions=False,
        ):
            return [{"hour": 9, "score": 0.91, "reason": "janela estável"}]

        ai_routes.MarketIntelligenceAI.build_market_snapshot = fake_build_market_snapshot
        ai_routes.MarketIntelligenceAI.materialize_guardrail_automations = fake_market_automations
        ai_routes.AutonomousCommerceAI.build_autonomous_plan = fake_build_autonomous_plan
        ai_routes.AutonomousCommerceAI.materialize_guardrail_automations = fake_autonomous_automations
        ai_routes.SmartSchedulingAI.suggest_best_slots = fake_suggest_best_slots
        ai_routes.get_cache = lambda _key: None
        ai_routes.set_cache = lambda _key, _value, expire=60: None
        ai_routes.emit_predictive_notifications_for_user = lambda db, user_id, now=None: 0
        ai_routes.maybe_create_rule_notifications = lambda db, user_id, event: 0

        def override_get_db():
            db = SessionLocal()
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

        ai_routes.MarketIntelligenceAI.build_market_snapshot = cls._originals["build_market_snapshot"]
        ai_routes.MarketIntelligenceAI.materialize_guardrail_automations = cls._originals["market_automations"]
        ai_routes.AutonomousCommerceAI.build_autonomous_plan = cls._originals["build_autonomous_plan"]
        ai_routes.AutonomousCommerceAI.materialize_guardrail_automations = cls._originals["autonomous_automations"]
        ai_routes.SmartSchedulingAI.suggest_best_slots = cls._originals["suggest_best_slots"]
        ai_routes.get_cache = cls._originals["get_cache"]
        ai_routes.set_cache = cls._originals["set_cache"]
        ai_routes.emit_predictive_notifications_for_user = cls._originals["emit_predictive"]
        ai_routes.maybe_create_rule_notifications = cls._originals["create_rule_notifications"]

        try:
            Path("test_ai_agenda_smoke.db").unlink(missing_ok=True)
        except Exception:
            pass

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        self.db.query(Notification).delete()
        self.db.query(AgendaEvent).delete()
        self.db.query(UserBehaviorLog).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.user = User(
            name="Agenda Smoke",
            email="agenda-smoke@test.com",
            password="hash",
            role="producer",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        type(self).current_user = self.user

    def tearDown(self):
        self.db.close()

    def test_agenda_endpoints_flow_smoke(self):
        profile_payload = {
            "autonomy_mode": "autonoma",
            "main_goal": "margem",
            "decision_style": "equilibrado",
            "preferred_contact_period": "manha",
            "guardrail_max_discount_pct": 7,
            "guardrail_min_net_margin_pct": 9,
            "guardrail_max_response_hours": 10,
            "guardrail_risk_tolerance": "medio",
            "flash_auction_window_minutes": 90,
            "flash_spoilage_risk_threshold": 62,
            "auto_execute_limit_per_day": 2,
        }

        save_profile = self.client.post("/ai/agenda/profile", json=profile_payload)
        self.assertEqual(save_profile.status_code, 200)

        get_profile = self.client.get("/ai/agenda/profile")
        self.assertEqual(get_profile.status_code, 200)
        returned_profile = get_profile.json().get("profile", {})
        self.assertEqual(returned_profile.get("autonomy_mode"), "autonoma")
        self.assertEqual(returned_profile.get("main_goal"), "margem")

        starts_at = datetime.now(timezone.utc) + timedelta(hours=2)
        ends_at = starts_at + timedelta(hours=1)

        create_event = self.client.post(
            "/ai/agenda/events",
            json={
                "title": "Reunião de validação IA",
                "description": "Smoke test agenda",
                "event_type": "meeting",
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "location": "Remoto",
                "is_all_day": False,
                "meta_json": {"source": "smoke_test"},
            },
        )
        self.assertEqual(create_event.status_code, 200)
        event_id = int(create_event.json()["event"]["id"])

        calendar = self.client.get(f"/ai/agenda/events?view=week&anchor_date={date.today().isoformat()}")
        self.assertEqual(calendar.status_code, 200)
        self.assertIn("days", calendar.json())

        moved = self.client.patch(
            f"/ai/agenda/events/{event_id}/move",
            json={"target_date": (date.today() + timedelta(days=1)).isoformat()},
        )
        self.assertEqual(moved.status_code, 200)

        market = self.client.get("/ai/agenda/market-intelligence")
        self.assertEqual(market.status_code, 200)
        self.assertIn("recommended_actions", market.json())

        autonomous = self.client.get("/ai/agenda/autonomous-commerce")
        self.assertEqual(autonomous.status_code, 200)
        self.assertIn("recommended_deals", autonomous.json())

        execute_commit = self.client.post(
            "/ai/agenda/autonomous-commerce/execute",
            json={
                "action_type": "auto_negotiation",
                "offer_id": "smoke-offer-1",
                "buyer_user_id": 999999,
                "mode": "commit",
            },
        )
        self.assertEqual(execute_commit.status_code, 200)
        self.assertTrue(execute_commit.json().get("committed"))

        execute_rollback = self.client.post(
            "/ai/agenda/autonomous-commerce/execute",
            json={
                "action_type": "auto_negotiation",
                "offer_id": "smoke-offer-1",
                "buyer_user_id": 999999,
                "mode": "rollback",
            },
        )
        self.assertEqual(execute_rollback.status_code, 200)
        self.assertTrue(execute_rollback.json().get("rolled_back"))

        plan = self.client.get("/ai/agenda/plan")
        self.assertEqual(plan.status_code, 200)
        payload = plan.json()
        self.assertIn("actions", payload)
        self.assertIn("autonomous_commerce", payload)

        cancel = self.client.delete(f"/ai/agenda/events/{event_id}")
        self.assertEqual(cancel.status_code, 200)
        self.assertTrue(cancel.json().get("ok"))


if __name__ == "__main__":
    unittest.main()
