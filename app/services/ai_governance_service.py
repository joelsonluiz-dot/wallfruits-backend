from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class AIGovernanceService:
    """Avalia politicas de autonomia e risco para acoes IA."""

    _VALID_ACTIONS = {"flash_auction", "auto_negotiation"}
    _VALID_AUTONOMY_MODES = {"assistida", "semi_autonoma", "autonoma"}
    _VALID_DECISION_STYLES = {"conservador", "equilibrado", "agressivo"}

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @classmethod
    def _normalize_action(cls, action_type: str) -> str:
        action = str(action_type or "").strip().lower()
        return action if action in cls._VALID_ACTIONS else "unknown"

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode or "commit").strip().lower()
        return normalized if normalized in {"commit", "rollback"} else "commit"

    @classmethod
    def _normalize_autonomy_mode(cls, profile: dict[str, Any] | None) -> str:
        value = str((profile or {}).get("autonomy_mode") or "assistida").strip().lower()
        return value if value in cls._VALID_AUTONOMY_MODES else "assistida"

    @classmethod
    def _normalize_decision_style(cls, profile: dict[str, Any] | None) -> str:
        value = str((profile or {}).get("decision_style") or "equilibrado").strip().lower()
        return value if value in cls._VALID_DECISION_STYLES else "equilibrado"

    @staticmethod
    def _risk_level_from_score(risk_score: float) -> str:
        if risk_score >= 0.66:
            return "high"
        if risk_score >= 0.33:
            return "medium"
        return "low"

    def precheck_action(
        self,
        *,
        profile: dict[str, Any] | None,
        action_type: str,
        mode: str,
    ) -> dict[str, Any]:
        action = self._normalize_action(action_type)
        normalized_mode = self._normalize_mode(mode)

        if action == "unknown":
            return {
                "allowed": False,
                "reason": "Acao nao suportada para governanca.",
                "action_type": action,
                "mode": normalized_mode,
            }

        if normalized_mode == "rollback":
            return {
                "allowed": True,
                "reason": "rollback_permitido",
                "action_type": action,
                "mode": normalized_mode,
            }

        profile_payload = profile or {}
        if action == "auto_negotiation" and not bool(profile_payload.get("auto_negotiation_enabled", True)):
            return {
                "allowed": False,
                "reason": "Auto negociacao desabilitada no perfil de agenda.",
                "action_type": action,
                "mode": normalized_mode,
            }

        if action == "flash_auction" and not bool(profile_payload.get("auto_flash_auction_enabled", True)):
            return {
                "allowed": False,
                "reason": "Leilao relampago desabilitado no perfil de agenda.",
                "action_type": action,
                "mode": normalized_mode,
            }

        return {
            "allowed": True,
            "reason": "ok",
            "action_type": action,
            "mode": normalized_mode,
        }

    def evaluate_transaction_result(
        self,
        *,
        profile: dict[str, Any] | None,
        action_type: str,
        mode: str,
        result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = result or {}
        snapshot = payload.get("governance_snapshot") if isinstance(payload.get("governance_snapshot"), dict) else {}

        action = self._normalize_action(action_type)
        normalized_mode = self._normalize_mode(mode)
        autonomy_mode = self._normalize_autonomy_mode(profile)
        decision_style = self._normalize_decision_style(profile)
        committed = bool(payload.get("committed"))
        guardrails_ok = bool(snapshot.get("guardrails_ok", committed))

        risk_score = 0.45
        if action == "auto_negotiation":
            risk_score = max(0.0, min(1.0, self._to_float(snapshot.get("risk_index"), 0.45)))
        elif action == "flash_auction":
            discount = max(0.0, self._to_float(snapshot.get("discount_pct"), 0.0))
            risk_score = max(0.0, min(1.0, 0.25 + (discount / 40.0)))

        risk_level = self._risk_level_from_score(risk_score)

        requires_human_review = False
        reasons: list[str] = []

        if normalized_mode == "rollback":
            reasons.append("rollback_requested")
        else:
            if not committed:
                requires_human_review = True
                reasons.append("transaction_not_committed")
            if not guardrails_ok:
                requires_human_review = True
                reasons.append("guardrail_failed")
            if autonomy_mode == "assistida":
                requires_human_review = True
                reasons.append("autonomy_mode_assistida")
            if risk_level == "high":
                requires_human_review = True
                reasons.append("high_risk")
            if decision_style == "conservador" and risk_level in {"medium", "high"}:
                requires_human_review = True
                reasons.append("conservative_profile_requires_review")

        if normalized_mode == "rollback" and committed:
            decision_outcome = "rolled_back"
        elif not committed:
            decision_outcome = "blocked"
        elif requires_human_review:
            decision_outcome = "approved_with_review"
        else:
            decision_outcome = "approved_autonomous"

        return {
            "decision_id": uuid4().hex,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "action_type": action,
            "mode": normalized_mode,
            "committed": committed,
            "autonomy_mode": autonomy_mode,
            "decision_style": decision_style,
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
            "guardrails_ok": guardrails_ok,
            "requires_human_review": requires_human_review,
            "decision_outcome": decision_outcome,
            "policy_reasons": reasons,
            "event_id": payload.get("event_id"),
            "message": payload.get("message"),
        }