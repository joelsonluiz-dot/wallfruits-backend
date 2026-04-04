from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.agenda_event import AgendaEvent
from app.models.offer import Offer
from app.models.profile import Profile
from app.models.transaction import Transaction
from app.models.user import User


class AutonomousCommerceAI:
    """Execucao comercial autonoma com guardrails para Agenda IA."""

    def __init__(self, db: Session):
        self.db = db

    def build_autonomous_plan(
        self,
        *,
        user_id: int,
        profile: dict[str, Any] | None,
        market_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        profile = profile or {}
        snapshot = market_snapshot or {}
        guardrails = self._normalize_guardrails(profile)
        now = datetime.now(timezone.utc)

        top_windows = list(snapshot.get("top_windows") or [])
        if not top_windows:
            return {
                "generated_at": now.isoformat(),
                "guardrails": guardrails,
                "offer_matches": [],
                "recommended_deals": [],
                "flash_auction_candidates": [],
                "recommended_actions": [],
            }

        offers = (
            self.db.query(Offer)
            .filter(Offer.user_id == user_id, Offer.status == "active")
            .all()
        )
        offers_by_id = {str(item.id): item for item in offers}

        candidates = self._load_buyer_candidates(exclude_user_id=user_id)
        candidate_ids = [item.id for item in candidates]
        candidate_profiles = self._load_profiles(candidate_ids)
        candidate_risk = self._load_buyer_risk(candidate_ids)

        offer_matches: list[dict[str, Any]] = []
        recommended_deals: list[dict[str, Any]] = []

        for item in top_windows[:6]:
            offer_id = str(item.get("offer_id") or "")
            offer = offers_by_id.get(offer_id)
            if not offer:
                continue

            unit_price = self._to_float(item.get("unit_price"), 0.0)
            if unit_price <= 0:
                unit_price = self._unit_price(offer)
            if unit_price <= 0:
                continue

            ranked = self._rank_buyer_matches(
                offer=offer,
                candidates=candidates,
                profiles=candidate_profiles,
                risk_map=candidate_risk,
                guardrails=guardrails,
            )
            if not ranked:
                continue

            top_ranked = ranked[:3]
            best = top_ranked[0]

            target_discount_pct = self._target_discount_pct(
                sell_window_score=float(item.get("sell_window_score", 0.0)),
                demand_score=float(item.get("demand_score", 0.4)),
                risk_index=float(best.get("risk_index", 0.35)),
                max_discount_pct=guardrails["max_discount_pct"],
            )

            platform_fee_per_kg = self._to_float(best.get("platform_fee_per_kg"), 0.0)
            freight_per_kg = self._to_float(best.get("freight_per_kg"), 0.0)
            default_risk_cost_per_kg = self._to_float(best.get("default_risk_cost_per_kg"), 0.0)
            total_cost_per_kg = platform_fee_per_kg + freight_per_kg + default_risk_cost_per_kg

            floor_by_discount = unit_price * (1.0 - (float(guardrails["max_discount_pct"]) / 100.0))
            margin_floor_denominator = max(0.01, 1.0 - float(guardrails["min_net_margin_pct"]))
            floor_by_margin = total_cost_per_kg / margin_floor_denominator
            producer_floor_price = max(0.0, floor_by_discount, floor_by_margin)

            discounted_target = max(0.0, unit_price * (1.0 - (target_discount_pct / 100.0)))
            proposed_unit_price = max(producer_floor_price, discounted_target)
            actual_discount_pct = (1.0 - (proposed_unit_price / unit_price)) * 100.0 if unit_price > 0 else 0.0
            expected_margin_pct = ((proposed_unit_price - total_cost_per_kg) / proposed_unit_price) if proposed_unit_price > 0 else -0.5

            max_response_hours = int(guardrails["max_response_hours"])
            response_deadline_at = now + timedelta(hours=max_response_hours)

            risk_allowed = self._risk_is_allowed(
                risk_index=float(best.get("risk_index", 0.35)),
                risk_tolerance=str(guardrails["risk_tolerance"]),
            )
            executable = (
                bool(guardrails["auto_negotiation_enabled"])
                and risk_allowed
                and expected_margin_pct >= float(guardrails["min_net_margin_pct"])
                and 0.0 <= actual_discount_pct <= float(guardrails["max_discount_pct"])
                and proposed_unit_price >= producer_floor_price
            )

            deal = {
                "offer_id": offer_id,
                "product_name": offer.product_name,
                "sell_window_score": round(float(item.get("sell_window_score", 0.0)), 2),
                "buyer_user_id": int(best["buyer_user_id"]),
                "buyer_name": str(best["buyer_name"]),
                "buyer_location": str(best.get("buyer_location") or ""),
                "fit_score": round(float(best.get("fit_score", 0.0)), 2),
                "risk_index": round(float(best.get("risk_index", 0.0)), 4),
                "freight_per_kg": round(freight_per_kg, 4),
                "platform_fee_per_kg": round(platform_fee_per_kg, 4),
                "default_risk_cost_per_kg": round(default_risk_cost_per_kg, 4),
                "total_cost_per_kg": round(total_cost_per_kg, 4),
                "base_unit_price": round(unit_price, 4),
                "producer_floor_price": round(producer_floor_price, 4),
                "target_discount_pct": round(target_discount_pct, 2),
                "actual_discount_pct": round(actual_discount_pct, 2),
                "proposed_unit_price": round(proposed_unit_price, 4),
                "expected_margin_pct": round(expected_margin_pct, 4),
                "max_response_hours": max_response_hours,
                "response_deadline_at": response_deadline_at.isoformat(),
                "guardrails_ok": bool(executable),
            }
            recommended_deals.append(deal)

            offer_matches.append(
                {
                    "offer_id": offer_id,
                    "product_name": offer.product_name,
                    "matches": top_ranked,
                }
            )

        flash_candidates = self._build_flash_auction_candidates(top_windows=top_windows, guardrails=guardrails)

        actions: list[dict[str, Any]] = []

        for deal in recommended_deals[:4]:
            cta = f"/offers/{deal['offer_id']}"
            if deal["guardrails_ok"]:
                actions.append(
                    {
                        "type": "auto_negotiation_execute",
                        "source": "offers",
                        "base_impact": min(96.0, 72.0 + (deal["fit_score"] * 0.2)),
                        "urgency": 1.11,
                        "title": f"Negociacao autonoma pronta para {deal['product_name']}",
                        "description": (
                            f"Comprador sugerido: {deal['buyer_name']} • desconto real {deal['actual_discount_pct']:.1f}% • "
                            f"margem final {deal['expected_margin_pct'] * 100:.1f}% • piso {deal['producer_floor_price']:.2f} • "
                            f"prazo maximo {deal['max_response_hours']}h"
                        ),
                        "cta": cta,
                        "notify": True,
                        "notify_key": f"auto_negotiation:{deal['offer_id']}:{deal['buyer_user_id']}",
                    }
                )
            else:
                actions.append(
                    {
                        "type": "auto_negotiation_review",
                        "source": "offers",
                        "base_impact": 63,
                        "urgency": 1.02,
                        "title": f"Revisar guardrails de {deal['product_name']}",
                        "description": (
                            f"Melhor match: {deal['buyer_name']}, margem final {deal['expected_margin_pct'] * 100:.1f}% e "
                            f"piso {deal['producer_floor_price']:.2f}. Risco/prazo pode nao atender limites definidos."
                        ),
                        "cta": cta,
                        "notify": False,
                    }
                )

        for candidate in flash_candidates[:2]:
            actions.append(
                {
                    "type": "flash_auction",
                    "source": "offers",
                    "base_impact": 84,
                    "urgency": 1.14,
                    "title": f"Leilao relampago para {candidate['product_name']}",
                    "description": (
                        f"Risco de perda {candidate['spoilage_risk_index']:.1f}/100 (gatilho >= {candidate['spoilage_trigger_threshold']:.1f}). "
                        f"Urgencia {candidate['urgency_score']:.1f}/100. "
                        f"Janela sugerida: {candidate['auction_window_minutes']} min."
                    ),
                    "cta": f"/offers/{candidate['offer_id']}",
                    "notify": True,
                    "notify_key": f"flash_auction:{candidate['offer_id']}",
                }
            )

        return {
            "generated_at": now.isoformat(),
            "guardrails": guardrails,
            "offer_matches": offer_matches,
            "recommended_deals": recommended_deals,
            "flash_auction_candidates": flash_candidates,
            "recommended_actions": actions,
        }

    def materialize_guardrail_automations(
        self,
        *,
        user_id: int,
        profile: dict[str, Any] | None,
        autonomous_plan: dict[str, Any] | None,
    ) -> dict[str, Any]:
        profile = profile or {}
        plan = autonomous_plan or {}

        autonomy_mode = str(profile.get("autonomy_mode") or "assistida")
        if autonomy_mode not in {"semi_autonoma", "autonoma"}:
            return {"events_created": 0, "automations": []}

        guardrails = self._normalize_guardrails(profile)
        max_events = int(guardrails["auto_execute_limit_per_day"])
        if max_events <= 0:
            return {"events_created": 0, "automations": []}

        now = datetime.now(timezone.utc)

        existing = (
            self.db.query(AgendaEvent)
            .filter(
                AgendaEvent.user_id == user_id,
                AgendaEvent.event_type == "task",
                AgendaEvent.status == "scheduled",
                AgendaEvent.starts_at >= now - timedelta(days=1),
            )
            .all()
        )
        existing_keys = {
            str((row.meta_json or {}).get("automation_key"))
            for row in existing
            if isinstance(row.meta_json, dict) and (row.meta_json or {}).get("automation_key")
        }

        automations: list[dict[str, Any]] = []
        created = 0

        if guardrails["auto_negotiation_enabled"]:
            for deal in plan.get("recommended_deals", []):
                if created >= max_events:
                    break
                if not isinstance(deal, dict) or not deal.get("guardrails_ok"):
                    continue

                offer_id = str(deal.get("offer_id") or "")
                buyer_id = int(deal.get("buyer_user_id") or 0)
                if not offer_id or buyer_id <= 0:
                    continue

                automation_key = f"auto-negotiation:{offer_id}:{buyer_id}"
                if automation_key in existing_keys:
                    continue

                starts_at = now + timedelta(hours=1 + created)
                ends_at = starts_at + timedelta(minutes=35)

                event = AgendaEvent(
                    user_id=user_id,
                    title=f"Negociacao autonoma: {deal.get('product_name', 'oferta')}",
                    description=(
                        f"Match sugerido com {deal.get('buyer_name', 'comprador')} | "
                        f"preco alvo {float(deal.get('proposed_unit_price', 0.0)):.2f} | "
                        f"margem estimada {float(deal.get('expected_margin_pct', 0.0)) * 100:.1f}% | "
                        f"prazo ate {str(deal.get('response_deadline_at') or '-') }"
                    ),
                    event_type="task",
                    starts_at=starts_at,
                    ends_at=ends_at,
                    location=str(deal.get("buyer_location") or "") or None,
                    status="scheduled",
                    is_all_day=False,
                    meta_json={
                        "source": "autonomous_commerce",
                        "automation_type": "negotiation",
                        "offer_id": offer_id,
                        "buyer_user_id": buyer_id,
                        "automation_key": automation_key,
                    },
                )
                self.db.add(event)
                created += 1
                existing_keys.add(automation_key)
                automations.append(
                    {
                        "type": "negotiation",
                        "offer_id": offer_id,
                        "buyer_user_id": buyer_id,
                        "title": event.title,
                        "starts_at": starts_at.isoformat(),
                    }
                )

        if guardrails["auto_flash_auction_enabled"]:
            for candidate in plan.get("flash_auction_candidates", []):
                if created >= max_events:
                    break
                if not isinstance(candidate, dict):
                    continue

                offer_id = str(candidate.get("offer_id") or "")
                if not offer_id:
                    continue

                automation_key = f"flash-auction:{offer_id}"
                if automation_key in existing_keys:
                    continue

                starts_at = now + timedelta(minutes=45 + (created * 10))
                duration = int(candidate.get("auction_window_minutes") or 90)
                ends_at = starts_at + timedelta(minutes=max(20, duration))

                event = AgendaEvent(
                    user_id=user_id,
                    title=f"Leilao relampago IA: {candidate.get('product_name', 'oferta')}",
                    description=(
                        f"Ative janela de leilao de {duration} min para reduzir perda de perecibilidade. "
                        f"Risco de perda {float(candidate.get('spoilage_risk_index', 0.0)):.1f}/100. "
                        f"Urgencia {float(candidate.get('urgency_score', 0.0)):.1f}/100."
                    ),
                    event_type="task",
                    starts_at=starts_at,
                    ends_at=ends_at,
                    location=None,
                    status="scheduled",
                    is_all_day=False,
                    meta_json={
                        "source": "autonomous_commerce",
                        "automation_type": "flash_auction",
                        "offer_id": offer_id,
                        "automation_key": automation_key,
                    },
                )
                self.db.add(event)
                created += 1
                existing_keys.add(automation_key)
                automations.append(
                    {
                        "type": "flash_auction",
                        "offer_id": offer_id,
                        "title": event.title,
                        "starts_at": starts_at.isoformat(),
                    }
                )

        return {"events_created": created, "automations": automations}

    def _normalize_guardrails(self, profile: dict[str, Any]) -> dict[str, Any]:
        def _num(key: str, default: float, min_value: float, max_value: float) -> float:
            try:
                value = float(profile.get(key, default))
            except (TypeError, ValueError):
                value = default
            return max(min_value, min(max_value, value))

        risk = str(profile.get("guardrail_risk_tolerance") or "medio").strip().lower()
        if risk not in {"baixo", "medio", "alto"}:
            risk = "medio"

        return {
            "auto_negotiation_enabled": bool(profile.get("auto_negotiation_enabled", True)),
            "auto_flash_auction_enabled": bool(profile.get("auto_flash_auction_enabled", True)),
            "max_discount_pct": _num("guardrail_max_discount_pct", 8.0, 0.0, 40.0),
            "min_net_margin_pct": _num("guardrail_min_net_margin_pct", 7.0, 0.0, 60.0) / 100.0,
            "max_response_hours": int(_num("guardrail_max_response_hours", 12.0, 1.0, 72.0)),
            "risk_tolerance": risk,
            "flash_auction_window_minutes": int(_num("flash_auction_window_minutes", 90.0, 15.0, 360.0)),
            "flash_spoilage_risk_threshold": _num("flash_spoilage_risk_threshold", 62.0, 30.0, 98.0),
            "auto_execute_limit_per_day": int(_num("auto_execute_limit_per_day", 2.0, 0.0, 10.0)),
        }

    def _load_buyer_candidates(self, *, exclude_user_id: int, limit: int = 120) -> list[User]:
        rows = (
            self.db.query(User)
            .filter(
                User.id != exclude_user_id,
                User.is_active.is_(True),
                User.role.in_(["buyer", "producer"]),
            )
            .order_by(User.rating.desc(), User.total_reviews.desc(), User.id.asc())
            .limit(limit)
            .all()
        )
        return rows

    def _load_profiles(self, user_ids: list[int]) -> dict[int, Profile]:
        if not user_ids:
            return {}

        rows = (
            self.db.query(Profile)
            .filter(Profile.user_id.in_(user_ids))
            .all()
        )
        return {row.user_id: row for row in rows}

    def _load_buyer_risk(self, user_ids: list[int]) -> dict[int, float]:
        if not user_ids:
            return {}

        cutoff = datetime.now(timezone.utc) - timedelta(days=180)
        rows = (
            self.db.query(Transaction)
            .filter(Transaction.buyer_id.in_(user_ids), Transaction.created_at >= cutoff)
            .all()
        )

        totals: dict[int, dict[str, float]] = {}
        for row in rows:
            bucket = totals.setdefault(int(row.buyer_id), {"total": 0.0, "bad": 0.0})
            bucket["total"] += 1.0
            status = str(row.status or "pending").lower()
            payment_status = str(row.payment_status or "pending").lower()

            if status in {"disputed", "cancelled", "canceled"}:
                bucket["bad"] += 1.0
            elif payment_status in {"refunded"}:
                bucket["bad"] += 0.6
            elif status in {"pending"}:
                bucket["bad"] += 0.15

        risk_map: dict[int, float] = {}
        for uid in user_ids:
            data = totals.get(uid)
            if not data:
                risk_map[uid] = 0.32
                continue

            total = max(1.0, float(data["total"]))
            bad = float(data["bad"])
            empirical = bad / total

            # Suavizacao bayesiana para usuarios com pouco historico.
            smoothed = ((empirical * total) + (0.28 * 5.0)) / (total + 5.0)
            risk_map[uid] = max(0.05, min(0.95, smoothed))

        return risk_map

    def _rank_buyer_matches(
        self,
        *,
        offer: Offer,
        candidates: list[User],
        profiles: dict[int, Profile],
        risk_map: dict[int, float],
        guardrails: dict[str, Any],
    ) -> list[dict[str, Any]]:
        unit_price = self._unit_price(offer)
        if unit_price <= 0:
            return []

        platform_fee = self._to_float(getattr(offer, "platform_fee", None), 0.03)
        quantity = self._to_float(getattr(offer, "quantity", None), 0.0)

        out: list[dict[str, Any]] = []
        for user in candidates:
            profile = profiles.get(user.id)
            freight = self._estimate_freight_per_kg(offer=offer, buyer=user, buyer_profile=profile, quantity=quantity)
            risk_index = float(risk_map.get(user.id, 0.32))

            risk_multiplier = {"baixo": 1.0, "medio": 0.85, "alto": 0.65}.get(str(guardrails["risk_tolerance"]), 0.85)
            risk_cost_per_kg = unit_price * risk_index * 0.18 * risk_multiplier

            margin_pct = (unit_price - platform_fee - freight - risk_cost_per_kg) / unit_price
            distance_score = self._distance_score(offer=offer, buyer=user, buyer_profile=profile)
            reliability_score = 1.0 - risk_index
            rating_score = min(1.0, max(0.0, float(user.rating or 0) / 5.0))

            fit_score = max(
                0.0,
                min(
                    100.0,
                    (
                        margin_pct * 130.0
                        + reliability_score * 28.0
                        + distance_score * 18.0
                        + rating_score * 12.0
                    ),
                ),
            )

            out.append(
                {
                    "buyer_user_id": int(user.id),
                    "buyer_name": str(user.name),
                    "buyer_location": str(user.location or ""),
                    "risk_index": round(risk_index, 4),
                    "freight_per_kg": round(freight, 4),
                    "platform_fee_per_kg": round(platform_fee, 4),
                    "default_risk_cost_per_kg": round(risk_cost_per_kg, 4),
                    "total_cost_per_kg": round(platform_fee + freight + risk_cost_per_kg, 4),
                    "estimated_margin_pct": round(margin_pct, 4),
                    "fit_score": round(fit_score, 2),
                }
            )

        out.sort(key=lambda row: float(row.get("fit_score", 0.0)), reverse=True)
        return out

    def _build_flash_auction_candidates(
        self,
        *,
        top_windows: list[dict[str, Any]],
        guardrails: dict[str, Any],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        threshold = float(guardrails.get("flash_spoilage_risk_threshold", 62.0))

        for item in top_windows:
            freshness = float(item.get("freshness_score", 0.0))
            engagement = float(item.get("engagement_score", 0.0))
            quantity = float(item.get("quantity", 0.0))
            sell_window = float(item.get("sell_window_score", 0.0))

            if quantity < 35:
                continue

            spoilage_risk_index = max(
                0.0,
                min(
                    100.0,
                    (1.0 - freshness) * 60.0
                    + (1.0 - engagement) * 18.0
                    + max(0.0, 55.0 - sell_window) * 0.45
                    + min(16.0, quantity * 0.03),
                ),
            )

            if spoilage_risk_index < threshold:
                continue

            urgency_score = max(
                0.0,
                min(
                    100.0,
                    (spoilage_risk_index * 0.78)
                    + (max(0.0, 62.0 - sell_window) * 0.45)
                    + min(20.0, quantity * 0.03),
                ),
            )

            out.append(
                {
                    "offer_id": str(item.get("offer_id") or ""),
                    "product_name": str(item.get("product_name") or "Oferta"),
                    "spoilage_risk_index": round(spoilage_risk_index, 2),
                    "spoilage_trigger_threshold": round(threshold, 2),
                    "urgency_score": round(urgency_score, 2),
                    "sell_window_score": round(sell_window, 2),
                    "auction_window_minutes": int(guardrails["flash_auction_window_minutes"]),
                }
            )

        out.sort(key=lambda row: float(row.get("urgency_score", 0.0)), reverse=True)
        return out

    def _target_discount_pct(
        self,
        *,
        sell_window_score: float,
        demand_score: float,
        risk_index: float,
        max_discount_pct: float,
    ) -> float:
        discount = 4.5

        if sell_window_score < 45:
            discount += 2.8
        elif sell_window_score < 62:
            discount += 1.4
        elif sell_window_score > 80:
            discount -= 0.8

        if demand_score < 0.35:
            discount += 1.4
        elif demand_score > 0.65:
            discount -= 0.9

        if risk_index > 0.45:
            discount -= 1.2

        return max(0.0, min(max_discount_pct, discount))

    @staticmethod
    def _risk_is_allowed(*, risk_index: float, risk_tolerance: str) -> bool:
        thresholds = {
            "baixo": 0.28,
            "medio": 0.43,
            "alto": 0.62,
        }
        return risk_index <= thresholds.get(risk_tolerance, 0.43)

    def _estimate_freight_per_kg(
        self,
        *,
        offer: Offer,
        buyer: User,
        buyer_profile: Profile | None,
        quantity: float,
    ) -> float:
        same_city = self._same_city(offer=offer, buyer=buyer, buyer_profile=buyer_profile)
        same_state = self._same_state(offer=offer, buyer_profile=buyer_profile)

        base = 0.11
        if same_city:
            base = 0.04
        elif same_state:
            base = 0.07

        if quantity > 500:
            base -= 0.012
        elif quantity < 100:
            base += 0.016

        return max(0.02, round(base, 4))

    def _distance_score(self, *, offer: Offer, buyer: User, buyer_profile: Profile | None) -> float:
        if self._same_city(offer=offer, buyer=buyer, buyer_profile=buyer_profile):
            return 1.0
        if self._same_state(offer=offer, buyer_profile=buyer_profile):
            return 0.68
        return 0.34

    def _same_city(self, *, offer: Offer, buyer: User, buyer_profile: Profile | None) -> bool:
        offer_location = str(getattr(offer, "location", "") or "").strip().lower()
        buyer_city = str(getattr(buyer_profile, "city", "") or "").strip().lower()
        buyer_location = str(getattr(buyer, "location", "") or "").strip().lower()

        if buyer_city and offer_location and buyer_city in offer_location:
            return True
        if buyer_location and offer_location and buyer_location == offer_location:
            return True
        return False

    def _same_state(self, *, offer: Offer, buyer_profile: Profile | None) -> bool:
        offer_location = str(getattr(offer, "location", "") or "").strip().lower()
        buyer_state = str(getattr(buyer_profile, "state", "") or "").strip().lower()
        if buyer_state and offer_location and buyer_state in offer_location:
            return True
        return False

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        if isinstance(value, Decimal):
            return float(value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _unit_price(self, offer: Offer) -> float:
        explicit = self._to_float(getattr(offer, "price_per_kg", None), 0.0)
        if explicit > 0:
            return explicit

        price = self._to_float(getattr(offer, "price", None), 0.0)
        quantity = self._to_float(getattr(offer, "quantity", None), 0.0)
        if price <= 0:
            return 0.0
        if quantity > 0:
            ratio = price / quantity
            if 0 < ratio <= price:
                return ratio
        return price
