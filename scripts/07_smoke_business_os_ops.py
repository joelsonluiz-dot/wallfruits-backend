#!/usr/bin/env python3
"""Smoke test Business OS Ops em producao.

Uso:
  python scripts/07_smoke_business_os_ops.py --base-url https://wallfruits-backend.onrender.com \
    --admin-email admin@wallfruits.com.br --admin-password '***'

Tambem aceita variaveis de ambiente:
  WF_ADMIN_EMAIL
  WF_ADMIN_PASSWORD
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class HttpResult:
    status: int
    latency_ms: float
    body: dict[str, Any] | str


@dataclass
class CheckResult:
    name: str
    ok: bool
    status: int | None
    latency_ms: float | None
    details: str


def _parse_body(raw: str) -> dict[str, Any] | str:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    except json.JSONDecodeError:
        return raw


def _request(
    *,
    base_url: str,
    path: str,
    method: str,
    timeout: float,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> HttpResult:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Accept": "application/json"}
    data: bytes | None = None

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = Request(url, headers=headers, data=data, method=method)
    started = time.perf_counter()

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return HttpResult(
                status=resp.status,
                latency_ms=(time.perf_counter() - started) * 1000,
                body=_parse_body(raw),
            )
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return HttpResult(
            status=exc.code,
            latency_ms=(time.perf_counter() - started) * 1000,
            body=_parse_body(raw),
        )
    except URLError as exc:
        return HttpResult(
            status=0,
            latency_ms=(time.perf_counter() - started) * 1000,
            body=f"falha de rede: {exc}",
        )
    except (TimeoutError, socket.timeout) as exc:
        return HttpResult(
            status=0,
            latency_ms=(time.perf_counter() - started) * 1000,
            body=f"timeout: {exc}",
        )


def _has_keys(body: dict[str, Any] | str, keys: list[str]) -> bool:
    if not isinstance(body, dict):
        return False
    return all(key in body for key in keys)


def _check(
    *,
    name: str,
    result: HttpResult,
    expected_statuses: set[int],
    required_keys: list[str] | None = None,
) -> CheckResult:
    status_ok = result.status in expected_statuses
    keys_ok = True

    if required_keys:
        keys_ok = _has_keys(result.body, required_keys)

    ok = status_ok and keys_ok
    details = f"esperado status {sorted(expected_statuses)}, recebido {result.status}"
    if status_ok and required_keys and not keys_ok:
        details = f"status ok, mas faltam chaves: {', '.join(required_keys)}"

    return CheckResult(
        name=name,
        ok=ok,
        status=result.status,
        latency_ms=result.latency_ms,
        details=details,
    )


def _print_result(item: CheckResult) -> None:
    tag = "OK" if item.ok else "FAIL"
    status = "-" if item.status is None else str(item.status)
    latency = "-" if item.latency_ms is None else f"{item.latency_ms:.2f}"
    print(f"[{tag}] {item.name:<45} status={status:<4} latency={latency:<10} | {item.details}")


def _assert_token(login_result: HttpResult) -> str:
    if login_result.status != 200:
        raise RuntimeError(f"falha no login admin: status {login_result.status}")
    if not isinstance(login_result.body, dict):
        raise RuntimeError("falha no login admin: resposta sem JSON")

    token = str(login_result.body.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("falha no login admin: access_token ausente")

    return token


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Business OS Ops")
    parser.add_argument("--base-url", required=True, help="URL base da API")
    parser.add_argument("--timeout", type=float, default=15.0, help="timeout por request")
    parser.add_argument(
        "--admin-email",
        default=os.getenv("WF_ADMIN_EMAIL", ""),
        help="email admin (ou WF_ADMIN_EMAIL)",
    )
    parser.add_argument(
        "--admin-password",
        default=os.getenv("WF_ADMIN_PASSWORD", ""),
        help="senha admin (ou WF_ADMIN_PASSWORD)",
    )
    parser.add_argument(
        "--apply-autopilot",
        action="store_true",
        help="executa governance autopilot com apply=true",
    )

    args = parser.parse_args()

    if not args.admin_email or not args.admin_password:
        print("ERRO: informe --admin-email e --admin-password (ou WF_ADMIN_EMAIL/WF_ADMIN_PASSWORD)")
        return 2

    checks: list[CheckResult] = []

    login = _request(
        base_url=args.base_url,
        path="/api/auth/login",
        method="POST",
        timeout=args.timeout,
        payload={"email": args.admin_email, "password": args.admin_password},
    )

    try:
        token = _assert_token(login)
    except RuntimeError as exc:
        checks.append(
            CheckResult(
                name="admin login",
                ok=False,
                status=login.status,
                latency_ms=login.latency_ms,
                details=str(exc),
            )
        )
        for item in checks:
            _print_result(item)
        return 1

    checks.append(_check(name="admin login", result=login, expected_statuses={200}, required_keys=["access_token"]))

    readiness = _request(
        base_url=args.base_url,
        path="/api/ai/ops/business-os/readiness?days=30",
        method="GET",
        timeout=args.timeout,
        token=token,
    )
    checks.append(
        _check(
            name="business os readiness",
            result=readiness,
            expected_statuses={200},
            required_keys=["readiness", "implementation_plan"],
        )
    )

    roadmap = _request(
        base_url=args.base_url,
        path="/api/ai/ops/business-os/transformation-roadmap?days=30",
        method="GET",
        timeout=args.timeout,
        token=token,
    )
    checks.append(
        _check(
            name="business os transformation roadmap",
            result=roadmap,
            expected_statuses={200},
            required_keys=["readiness", "implementation_plan", "weekly_learning_ritual"],
        )
    )

    pipeline = _request(
        base_url=args.base_url,
        path="/api/ai/ops/business-os/signal-pipeline",
        method="POST",
        timeout=args.timeout,
        token=token,
        payload={
            "source": "smoke_business_os",
            "persist_only_accepted": True,
            "events": [
                {
                    "event_type": "checkout_started",
                    "event_domain": "conversion",
                    "entity_type": "order",
                    "entity_id": "smoke-order-001",
                    "risk_level": "low",
                    "risk_score": 0.31,
                    "metadata": {
                        "channel": "web",
                        "segment": "hortifruti|varejo",
                        "amount": 119.9,
                    },
                },
                {
                    "event_type": "support_escalation",
                    "event_domain": "efficiency_risk",
                    "entity_type": "ticket",
                    "entity_id": "smoke-ticket-002",
                    "risk_level": "high",
                    "risk_score": 0.86,
                    "metadata": {
                        "category": "payment_dispute",
                        "segment": "insumos|varejo",
                    },
                },
            ],
        },
    )
    checks.append(
        _check(
            name="business os signal pipeline",
            result=pipeline,
            expected_statuses={200},
            required_keys=["summary", "events", "priority_recommendations"],
        )
    )

    autopilot = _request(
        base_url=args.base_url,
        path="/api/ai/ops/business-os/governance-autopilot?days=30",
        method="POST",
        timeout=args.timeout,
        token=token,
        payload={
            "apply": bool(args.apply_autopilot),
            "source": "smoke_business_os",
            "max_actions": 5,
        },
    )
    checks.append(
        _check(
            name="business os governance autopilot",
            result=autopilot,
            expected_statuses={200},
            required_keys=["summary", "actions", "readiness"],
        )
    )

    print("\n" + "=" * 88)
    print("SMOKE BUSINESS OS OPS")
    print("=" * 88)

    for item in checks:
        _print_result(item)

    failed = [item for item in checks if not item.ok]
    print("-" * 88)
    print(f"TOTAL={len(checks)} OK={len(checks) - len(failed)} FAIL={len(failed)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
