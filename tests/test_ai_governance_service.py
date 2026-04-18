import unittest

from app.services.ai_governance_service import AIGovernanceService


class AIGovernanceServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = AIGovernanceService()

    def test_precheck_blocks_disabled_auto_negotiation(self):
        result = self.service.precheck_action(
            profile={"auto_negotiation_enabled": False},
            action_type="auto_negotiation",
            mode="commit",
        )

        self.assertFalse(result["allowed"])
        self.assertIn("desabilitada", result["reason"].lower())

    def test_precheck_allows_rollback_even_with_disabled_flags(self):
        result = self.service.precheck_action(
            profile={"auto_negotiation_enabled": False, "auto_flash_auction_enabled": False},
            action_type="flash_auction",
            mode="rollback",
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "rollback_permitido")

    def test_evaluate_requires_human_review_for_high_risk_assistida(self):
        decision = self.service.evaluate_transaction_result(
            profile={"autonomy_mode": "assistida", "decision_style": "conservador"},
            action_type="auto_negotiation",
            mode="commit",
            result={
                "committed": True,
                "event_id": 42,
                "governance_snapshot": {
                    "risk_index": 0.82,
                    "guardrails_ok": True,
                },
            },
        )

        self.assertEqual(decision["risk_level"], "high")
        self.assertTrue(decision["requires_human_review"])
        self.assertEqual(decision["decision_outcome"], "approved_with_review")

    def test_evaluate_low_risk_autonomous_is_approved(self):
        decision = self.service.evaluate_transaction_result(
            profile={"autonomy_mode": "autonoma", "decision_style": "agressivo"},
            action_type="auto_negotiation",
            mode="commit",
            result={
                "committed": True,
                "event_id": 10,
                "governance_snapshot": {
                    "risk_index": 0.12,
                    "guardrails_ok": True,
                },
            },
        )

        self.assertEqual(decision["risk_level"], "low")
        self.assertFalse(decision["requires_human_review"])
        self.assertEqual(decision["decision_outcome"], "approved_autonomous")


if __name__ == "__main__":
    unittest.main()