from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.offer import Offer
from app.models.transaction import Transaction


class MarketIntelligenceAI:
    """Motor de inteligência comercial para apoiar decisões da Agenda IA."""

    def __init__(self, db: Session):
        self.db = db

    def build_market_snapshot(
        self,
        *,
        user_id: int,
        profile: dict[str, Any] | None = None,
        max_offers: int = 5,
    ) -> dict[str, Any]:
        profile = profile or {}
        decision_style = str(profile.get("decision_style") or "equilibrado").strip().lower()

        offers = (
            self.db.query(Offer)
            .filter(Offer.user_id == user_id, Offer.status == "active")
            .order_by(Offer.updated_at.desc(), Offer.created_at.desc())
            .limit(40)
            .all()
        )

        if not offers:
            return {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "portfolio": {
                    "active_offers": 0,
                    "avg_sell_window_score": 0.0,
                    "avg_net_margin_pct": 0.0,
                    "portfolio_health": "insuficiente",
                },
                "top_windows": [],
                "recommended_actions": [
                    {
                        "type": "market_bootstrap",
                        "source": "offers",
                        "base_impact": 72,
                        "urgency": 1.0,
                        "title": "Criar ofertas para ativar o radar de mercado",
                        "description": "Sem ofertas ativas no momento. Publique lotes para a IA estimar janela ótima e margem líquida.",
                        "cta": "/offers/new",
                        "notify": False,
                    }
                ],
            }

        category_stats = self._category_market_stats(offers)

        signals: list[dict[str, Any]] = []
        for offer in offers:
            signal = self._score_offer(
                offer=offer,
                category_stats=category_stats,
                decision_style=decision_style,
            )
            signals.append(signal)

        signals.sort(key=lambda row: float(row.get("sell_window_score", 0.0)), reverse=True)
        top_windows = signals[: max(1, max_offers)]

        avg_window = sum(float(item.get("sell_window_score", 0.0)) for item in signals) / max(len(signals), 1)
        avg_margin_pct = sum(float(item.get("net_margin_pct", 0.0)) for item in signals) / max(len(signals), 1)

        portfolio_health = "forte"
        if avg_window < 58 or avg_margin_pct < 0.08:
            portfolio_health = "atencao"
        if avg_window < 44 or avg_margin_pct < 0.02:
            portfolio_health = "critico"

        actions = self._build_actions(
            top_windows=top_windows,
            decision_style=decision_style,
            autonomy_mode=str(profile.get("autonomy_mode") or "assistida"),
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "portfolio": {
                "active_offers": len(offers),
                "avg_sell_window_score": round(avg_window, 2),
                "avg_net_margin_pct": round(avg_margin_pct, 4),
                "portfolio_health": portfolio_health,
            },
            "top_windows": top_windows,
            "recommended_actions": actions,
        }

    def materialize_guardrail_automations(
        self,
        *,
        user_id: int,
        profile: dict[str, Any] | None,
        market_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        profile = profile or {}
        autonomy_mode = str(profile.get("autonomy_mode") or "assistida")
        if autonomy_mode != "autonoma":
            return {"events_created": 0, "automations": []}

        now = datetime.now(timezone.utc)
        existing = (
            self.db.query(Offer.id, Offer.product_name)
            .filter(Offer.user_id == user_id, Offer.status == "active")
            .all()
        )
        existing_ids = {str(item.id) for item in existing}

        from app.models.agenda_event import AgendaEvent

        already_scheduled_rows = (
            self.db.query(AgendaEvent)
            .filter(
                AgendaEvent.user_id == user_id,
                AgendaEvent.event_type == "task",
                AgendaEvent.status == "scheduled",
                AgendaEvent.starts_at >= now - timedelta(days=2),
            )
            .all()
        )
        already_scheduled_offer_ids = {
            str((row.meta_json or {}).get("market_offer_id"))
            for row in already_scheduled_rows
            if isinstance(row.meta_json, dict) and (row.meta_json or {}).get("market_offer_id")
        }

        automations: list[dict[str, Any]] = []
        events_created = 0

        for item in market_snapshot.get("top_windows", [])[:3]:
            offer_id = str(item.get("offer_id") or "")
            if not offer_id or offer_id not in existing_ids:
                continue
            if offer_id in already_scheduled_offer_ids:
                continue

            score = float(item.get("sell_window_score", 0.0))
            confidence = float(item.get("confidence", 0.0))
            if score < 80 or confidence < 0.62:
                continue

            starts_at = now + timedelta(hours=2 + events_created)
            ends_at = starts_at + timedelta(minutes=45)

            event = AgendaEvent(
                user_id=user_id,
                title=f"Execução IA: priorizar {item.get('product_name', 'oferta')}",
                description=(
                    f"Janela de venda detectada ({score:.1f}/100). "
                    f"Margem líquida estimada: {float(item.get('net_margin_pct', 0.0)) * 100:.1f}% por kg."
                ),
                event_type="task",
                starts_at=starts_at,
                ends_at=ends_at,
                location=item.get("location") or None,
                status="scheduled",
                is_all_day=False,
                meta_json={
                    "source": "market_intelligence",
                    "market_offer_id": offer_id,
                    "sell_window_score": score,
                    "confidence": confidence,
                },
            )
            self.db.add(event)
            events_created += 1
            automations.append(
                {
                    "offer_id": offer_id,
                    "title": event.title,
                    "starts_at": starts_at.isoformat(),
                    "score": round(score, 2),
                }
            )

            if events_created >= 2:
                break

        return {"events_created": events_created, "automations": automations}

    def _category_market_stats(self, offers: list[Offer]) -> dict[str, dict[str, float]]:
        categories_raw = {
            str(offer.category).strip()
            for offer in offers
            if str(offer.category or "").strip()
        }
        if not categories_raw:
            categories_raw = {"geral"}

        categories = {self._norm_category(value) for value in categories_raw}

        supply_rows = (
            self.db.query(Offer)
            .filter(Offer.status == "active")
            .filter(Offer.category.in_(list(categories_raw)))
            .all()
        )

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        transaction_rows = (
            self.db.query(Transaction, Offer)
            .join(Offer, Offer.id == Transaction.offer_id)
            .filter(Offer.category.in_(list(categories_raw)), Transaction.created_at >= cutoff)
            .all()
        )

        by_category_supply: dict[str, list[Offer]] = {cat: [] for cat in categories}
        for row in supply_rows:
            by_category_supply.setdefault(self._norm_category(row.category), []).append(row)

        by_category_tx: dict[str, int] = {cat: 0 for cat in categories}
        for tx, offer in transaction_rows:
            by_category_tx[self._norm_category(offer.category)] = by_category_tx.get(self._norm_category(offer.category), 0) + 1

        stats: dict[str, dict[str, float]] = {}
        for category in categories:
            supply_list = by_category_supply.get(category, [])
            tx_count = float(by_category_tx.get(category, 0))

            unit_prices = [self._unit_price(item) for item in supply_list]
            unit_prices = [value for value in unit_prices if value > 0]
            avg_price = sum(unit_prices) / max(len(unit_prices), 1) if unit_prices else 0.0

            supply_count = float(len(supply_list))
            demand_ratio = tx_count / max(1.0, (supply_count * 0.75) + 2.0)

            stats[category] = {
                "active_supply": supply_count,
                "transactions_30d": tx_count,
                "avg_unit_price": avg_price,
                "demand_score": max(0.0, min(1.0, demand_ratio)),
                "competition_score": max(0.0, min(1.0, max(0.0, supply_count - 1.0) / 45.0)),
            }

        return stats

    def _score_offer(
        self,
        *,
        offer: Offer,
        category_stats: dict[str, dict[str, float]],
        decision_style: str,
    ) -> dict[str, Any]:
        category_key = self._norm_category(offer.category)
        stats = category_stats.get(category_key) or {
            "active_supply": 1.0,
            "transactions_30d": 0.0,
            "avg_unit_price": 0.0,
            "demand_score": 0.4,
            "competition_score": 0.35,
        }

        unit_price = self._unit_price(offer)
        platform_fee = self._to_float(offer.platform_fee, 0.03)
        logistics_per_kg = self._estimate_logistics_per_kg(offer=offer, decision_style=decision_style)

        net_margin_per_kg = unit_price - platform_fee - logistics_per_kg
        net_margin_pct = (net_margin_per_kg / unit_price) if unit_price > 0 else 0.0
        net_margin_score = max(0.0, min(100.0, ((net_margin_pct + 0.05) / 0.35) * 100.0))

        freshness_score = self._freshness_score(offer)
        engagement_score = self._engagement_score(offer)
        demand_score = float(stats.get("demand_score", 0.4))
        competition_score = float(stats.get("competition_score", 0.35))
        price_edge_score = self._price_edge_score(unit_price=unit_price, avg_unit_price=float(stats.get("avg_unit_price", 0.0)))

        base_window = (
            demand_score * 0.32
            + freshness_score * 0.22
            + engagement_score * 0.18
            + price_edge_score * 0.16
            + (1.0 - competition_score) * 0.12
        ) * 100.0

        if decision_style == "agressivo":
            base_window += (demand_score * 5.5) + ((1.0 - competition_score) * 2.5)
        elif decision_style == "conservador":
            base_window += (freshness_score * 4.0) + ((net_margin_score / 100.0) * 6.0)
        else:
            base_window += ((net_margin_score / 100.0) * 4.0)

        sell_window_score = max(0.0, min(100.0, base_window))
        confidence = self._confidence_score(stats=stats, offer=offer)

        return {
            "offer_id": str(offer.id),
            "product_name": offer.product_name,
            "category": offer.category,
            "location": offer.location,
            "quantity": round(self._to_float(offer.quantity, 0.0), 2),
            "unit": offer.unit,
            "unit_price": round(unit_price, 4),
            "avg_market_unit_price": round(float(stats.get("avg_unit_price", 0.0)), 4),
            "sell_window_score": round(sell_window_score, 2),
            "sell_window_label": self._window_label(sell_window_score),
            "net_margin_per_kg": round(net_margin_per_kg, 4),
            "net_margin_pct": round(net_margin_pct, 4),
            "net_margin_score": round(net_margin_score, 2),
            "demand_score": round(demand_score, 4),
            "competition_score": round(competition_score, 4),
            "engagement_score": round(engagement_score, 4),
            "freshness_score": round(freshness_score, 4),
            "price_edge_score": round(price_edge_score, 4),
            "confidence": round(confidence, 4),
            "recommended_move": self._recommended_move(
                sell_window_score=sell_window_score,
                net_margin_pct=net_margin_pct,
                demand_score=demand_score,
                price_edge_score=price_edge_score,
            ),
        }

    def _build_actions(
        self,
        *,
        top_windows: list[dict[str, Any]],
        decision_style: str,
        autonomy_mode: str,
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

        for item in top_windows[:3]:
            score = float(item.get("sell_window_score", 0.0))
            margin_pct = float(item.get("net_margin_pct", 0.0))
            offer_id = str(item.get("offer_id") or "")
            cta = f"/offers/{offer_id}" if offer_id else "/offers"

            if score >= 78:
                actions.append(
                    {
                        "type": "market_sell_window",
                        "source": "offers",
                        "base_impact": min(95.0, 68.0 + (score * 0.22)),
                        "urgency": 1.10 if autonomy_mode in {"semi_autonoma", "autonoma"} else 1.04,
                        "title": f"Janela premium para {item.get('product_name', 'oferta')}",
                        "description": (
                            f"Score de janela {score:.1f}/100 e margem líquida estimada de {margin_pct * 100:.1f}% por kg. "
                            "Recomendação: acelerar negociação nas próximas 24h."
                        ),
                        "cta": cta,
                        "notify": True,
                        "notify_key": f"market_sell_window:{offer_id}",
                    }
                )
                continue

            if score < 52 or margin_pct < 0.05:
                actions.append(
                    {
                        "type": "market_reprice",
                        "source": "offers",
                        "base_impact": 74 if score < 45 else 61,
                        "urgency": 1.03,
                        "title": f"Revisar preço/posicionamento de {item.get('product_name', 'oferta')}",
                        "description": (
                            f"Janela em {score:.1f}/100 com margem líquida de {margin_pct * 100:.1f}%. "
                            "Ajustar preço e segmentação tende a recuperar conversão."
                        ),
                        "cta": cta,
                        "notify": score < 45,
                        "notify_key": f"market_reprice:{offer_id}",
                    }
                )

        if not actions and top_windows:
            best = top_windows[0]
            offer_id = str(best.get("offer_id") or "")
            actions.append(
                {
                    "type": "market_monitor",
                    "source": "offers",
                    "base_impact": 49,
                    "urgency": 0.94,
                    "title": "Radar de mercado estável",
                    "description": (
                        f"Melhor janela atual: {best.get('sell_window_score', 0):.1f}/100 em {best.get('product_name', 'oferta')} "
                        f"({best.get('sell_window_label', 'janela moderada')})."
                    ),
                    "cta": f"/offers/{offer_id}" if offer_id else "/offers",
                    "notify": False,
                }
            )

        if decision_style == "agressivo":
            for action in actions:
                action["urgency"] = round(float(action.get("urgency", 1.0)) * 1.04, 2)

        return actions

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

    @staticmethod
    def _norm_category(value: Any) -> str:
        return str(value or "geral").strip().lower()

    def _estimate_logistics_per_kg(self, *, offer: Offer, decision_style: str) -> float:
        quantity = self._to_float(getattr(offer, "quantity", None), 0.0)
        base = 0.08

        if quantity < 80:
            base += 0.03
        elif quantity > 600:
            base -= 0.015

        if not str(getattr(offer, "location", "") or "").strip():
            base += 0.01

        if decision_style == "agressivo":
            base -= 0.006
        elif decision_style == "conservador":
            base += 0.006

        return max(0.02, round(base, 4))

    def _freshness_score(self, offer: Offer) -> float:
        now_date = datetime.now(timezone.utc).date()

        harvest_date_actual = getattr(offer, "harvest_date_actual", None)
        if harvest_date_actual is not None:
            days = max(0, (now_date - harvest_date_actual).days)
        else:
            harvest_date = getattr(offer, "harvest_date", None)
            if harvest_date:
                if getattr(harvest_date, "tzinfo", None) is None:
                    days = max(0, (datetime.now() - harvest_date).days)
                else:
                    days = max(0, (datetime.now(timezone.utc) - harvest_date.astimezone(timezone.utc)).days)
            else:
                created = getattr(offer, "created_at", None)
                if created is None:
                    days = 14
                elif getattr(created, "tzinfo", None) is None:
                    days = max(0, (datetime.now() - created).days)
                else:
                    days = max(0, (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).days)

        if days <= 3:
            return 1.0
        if days <= 7:
            return 0.86
        if days <= 14:
            return 0.63
        if days <= 21:
            return 0.42
        return 0.24

    def _engagement_score(self, offer: Offer) -> float:
        views = max(0.0, self._to_float(getattr(offer, "views", 0), 0.0))
        favorites = max(0.0, self._to_float(getattr(offer, "favorites_count", 0), 0.0))

        views_norm = min(1.0, views / 120.0)
        favorites_norm = min(1.0, favorites / 25.0)
        return max(0.0, min(1.0, (views_norm * 0.55) + (favorites_norm * 0.45)))

    @staticmethod
    def _price_edge_score(*, unit_price: float, avg_unit_price: float) -> float:
        if unit_price <= 0 or avg_unit_price <= 0:
            return 0.5

        delta_pct = (avg_unit_price - unit_price) / avg_unit_price
        # Abaixo da média tende a acelerar giro, acima da média exige diferencial.
        return max(0.0, min(1.0, 0.5 + (delta_pct * 1.2)))

    @staticmethod
    def _window_label(score: float) -> str:
        if score >= 82:
            return "janela premium (0-24h)"
        if score >= 68:
            return "janela forte (24-72h)"
        if score >= 52:
            return "janela moderada (3-6 dias)"
        return "janela defensiva (revisar estratégia)"

    @staticmethod
    def _recommended_move(
        *,
        sell_window_score: float,
        net_margin_pct: float,
        demand_score: float,
        price_edge_score: float,
    ) -> str:
        if sell_window_score >= 80 and net_margin_pct >= 0.1:
            return "executar_prioridade_maxima"
        if sell_window_score >= 65 and demand_score >= 0.45:
            return "acelerar_followups"
        if net_margin_pct < 0.05:
            return "reprecificar"
        if price_edge_score < 0.42:
            return "reposicionar_valor"
        return "monitorar"

    @staticmethod
    def _confidence_score(*, stats: dict[str, float], offer: Offer) -> float:
        transactions = float(stats.get("transactions_30d", 0.0))
        supply = float(stats.get("active_supply", 1.0))
        engagement_points = float(getattr(offer, "views", 0) or 0) + (float(getattr(offer, "favorites_count", 0) or 0) * 2.0)

        confidence = 0.45
        confidence += min(0.22, transactions / 80.0)
        confidence += min(0.16, supply / 120.0)
        confidence += min(0.13, engagement_points / 220.0)

        return max(0.35, min(0.96, confidence))
