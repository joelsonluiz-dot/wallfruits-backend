from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_ARCHITECTURE_CYCLE = [
    "captar_sinais",
    "decidir_com_ia",
    "executar_por_agentes",
    "aprender_em_tempo_real",
]

# Taxonomia mínima para padronizar eventos críticos do Business OS.
_EVENT_TAXONOMY: dict[str, dict[str, Any]] = {
    "message_sent": {
        "domain": "atendimento",
        "loop": "conversao",
        "agent": "agente_atendimento",
        "required_metadata": ["receiver_id", "message_type"],
        "default_risk": "low",
    },
    "message_send_denied": {
        "domain": "atendimento",
        "loop": "risco_eficiencia",
        "agent": "agente_atendimento",
        "required_metadata": ["reason", "message_type"],
        "default_risk": "medium",
    },
    "payment_checkout_requested": {
        "domain": "marketing",
        "loop": "conversao",
        "agent": "agente_growth_marketing",
        "required_metadata": ["plan", "billing_cycle"],
        "default_risk": "low",
    },
    "payment_checkout_created": {
        "domain": "marketing",
        "loop": "conversao",
        "agent": "agente_growth_marketing",
        "required_metadata": ["plan", "billing_cycle"],
        "default_risk": "low",
    },
    "payment_checkout_failed": {
        "domain": "gestao_financeira",
        "loop": "risco_eficiencia",
        "agent": "agente_gestao_financeira_operacional",
        "required_metadata": ["plan", "billing_cycle", "reason"],
        "default_risk": "medium",
    },
    "store_checkout_session_requested": {
        "domain": "marketing",
        "loop": "conversao",
        "agent": "agente_growth_marketing",
        "required_metadata": ["payment_method"],
        "default_risk": "low",
    },
    "store_checkout_completed": {
        "domain": "gestao_financeira",
        "loop": "retencao_expansao",
        "agent": "agente_gestao_financeira_operacional",
        "required_metadata": ["payment_method", "status", "total_amount"],
        "default_risk": "low",
    },
    "ai_decision_recorded": {
        "domain": "gestao_operacional",
        "loop": "risco_eficiencia",
        "agent": "orquestrador_central",
        "required_metadata": ["decision"],
        "default_risk": "medium",
    },
    "ai_review_queue_resolved": {
        "domain": "gestao_operacional",
        "loop": "risco_eficiencia",
        "agent": "agente_risco_compliance",
        "required_metadata": ["decision", "resolved_status"],
        "default_risk": "high",
    },
    "growth_signal_detected": {
        "domain": "marketing",
        "loop": "aquisicao",
        "agent": "agente_growth_marketing",
        "required_metadata": ["signal_type", "segment"],
        "default_risk": "low",
    },
    "product_friction_detected": {
        "domain": "produto",
        "loop": "eficiencia_produto",
        "agent": "agente_produto_descoberta",
        "required_metadata": ["journey", "impact_area"],
        "default_risk": "medium",
    },
    "support_crisis_alert": {
        "domain": "atendimento",
        "loop": "risco_eficiencia",
        "agent": "agente_atendimento",
        "required_metadata": ["severity", "summary"],
        "default_risk": "high",
    },
}

_DOMAIN_DEFAULT_AGENT = {
    "atendimento": "agente_atendimento",
    "marketing": "agente_growth_marketing",
    "produto": "agente_produto_descoberta",
    "gestao_financeira": "agente_gestao_financeira_operacional",
    "gestao_operacional": "orquestrador_central",
}

_AUTONOMY_BY_RISK = {
    "low": {
        "policy": "auto_execute",
        "human_gate": False,
        "description": "Baixo risco: IA executa automaticamente com auditoria.",
    },
    "medium": {
        "policy": "human_approval",
        "human_gate": True,
        "description": "Médio risco: IA propõe e humano aprova.",
    },
    "high": {
        "policy": "human_decision",
        "human_gate": True,
        "description": "Alto risco: humano decide com recomendação da IA.",
    },
}


def _normalize_text(value: str | None, default: str = "") -> str:
    return str(value or "").strip().lower() or default


def classify_risk(*, risk_level: str | None = None, risk_score: float | None = None, default: str = "medium") -> str:
    normalized = _normalize_text(risk_level)
    if normalized in {"low", "medium", "high"}:
        return normalized

    if risk_score is None:
        return default

    try:
        score = float(risk_score)
    except (TypeError, ValueError):
        return default

    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "medium"
    return "low"


def validate_event_contract(event_type: str, metadata: dict[str, Any] | None) -> dict[str, Any]:
    normalized_event_type = _normalize_text(event_type)
    contract = _EVENT_TAXONOMY.get(normalized_event_type)
    payload = metadata if isinstance(metadata, dict) else {}

    if not contract:
        return {
            "known_event": False,
            "required_fields": [],
            "missing_fields": [],
        }

    required_fields = [str(field) for field in contract.get("required_metadata", [])]
    missing_fields = [field for field in required_fields if payload.get(field) in (None, "")]

    return {
        "known_event": True,
        "required_fields": required_fields,
        "missing_fields": missing_fields,
    }


def select_agent_for_event(*, event_type: str, event_domain: str | None = None) -> str:
    normalized_event_type = _normalize_text(event_type)
    contract = _EVENT_TAXONOMY.get(normalized_event_type)
    if contract:
        return str(contract.get("agent") or "orquestrador_central")

    domain = _normalize_text(event_domain)
    if domain and domain in _DOMAIN_DEFAULT_AGENT:
        return _DOMAIN_DEFAULT_AGENT[domain]

    return "orquestrador_central"


def build_orchestration_decision(
    *,
    event_type: str,
    event_domain: str | None,
    metadata: dict[str, Any] | None,
    risk_level: str | None,
    risk_score: float | None,
) -> dict[str, Any]:
    normalized_event_type = _normalize_text(event_type)
    contract = _EVENT_TAXONOMY.get(normalized_event_type)
    payload = metadata if isinstance(metadata, dict) else {}

    inferred_domain = _normalize_text(event_domain)
    if not inferred_domain and contract:
        inferred_domain = _normalize_text(contract.get("domain"))

    contract_validation = validate_event_contract(normalized_event_type, payload)
    resolved_risk = classify_risk(
        risk_level=risk_level,
        risk_score=risk_score,
        default=str(contract.get("default_risk") or "medium") if contract else "medium",
    )
    autonomy = _AUTONOMY_BY_RISK[resolved_risk]
    selected_agent = select_agent_for_event(event_type=normalized_event_type, event_domain=inferred_domain)

    return {
        "event_type": normalized_event_type,
        "event_domain": inferred_domain or "unknown",
        "loop": str(contract.get("loop") or "unknown") if contract else "unknown",
        "selected_agent": selected_agent,
        "risk_level": resolved_risk,
        "autonomy_policy": autonomy,
        "contract_validation": contract_validation,
        "recommended_next_step": (
            "executar_agente"
            if not contract_validation["missing_fields"] and not autonomy["human_gate"]
            else "enfileirar_revisao_humana"
        ),
    }


def build_business_os_blueprint() -> dict[str, Any]:
    by_domain: dict[str, int] = {}
    by_loop: dict[str, int] = {}

    for item in _EVENT_TAXONOMY.values():
        domain = _normalize_text(item.get("domain"), default="unknown")
        loop = _normalize_text(item.get("loop"), default="unknown")
        by_domain[domain] = int(by_domain.get(domain, 0)) + 1
        by_loop[loop] = int(by_loop.get(loop, 0)) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "architecture_cycle": list(_ARCHITECTURE_CYCLE),
        "taxonomy": _EVENT_TAXONOMY,
        "autonomy_by_risk": _AUTONOMY_BY_RISK,
        "agent_defaults_by_domain": _DOMAIN_DEFAULT_AGENT,
        "summary": {
            "events_total": len(_EVENT_TAXONOMY),
            "domains": by_domain,
            "loops": by_loop,
        },
    }
