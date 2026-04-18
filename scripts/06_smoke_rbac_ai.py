#!/usr/bin/env python3
"""Smoke test automatizado de RBAC + IA em producao.

Uso:
  python scripts/06_smoke_rbac_ai.py --base-url https://wallfruits-backend.onrender.com

Tokens podem ser passados por argumento ou variavel de ambiente:
  WF_TOKEN_PLATFORM_SUPPORT
  WF_TOKEN_PLATFORM_OPS
  WF_TOKEN_ACCOUNT_VIEWER
  WF_TOKEN_ACCOUNT_MANAGER
  WF_TOKEN_ACCOUNT_ANALYST
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
    skipped: bool = False


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


def _has_key(body: dict[str, Any] | str, key: str) -> bool:
    if isinstance(body, dict):
        return key in body
    return False


def _ok_check(
    *,
    name: str,
    result: HttpResult,
    expected_statuses: set[int],
    required_body_key: str | None = None,
) -> CheckResult:
    status_ok = result.status in expected_statuses
    body_ok = True
    if required_body_key:
        body_ok = _has_key(result.body, required_body_key)

    ok = status_ok and body_ok

    details = f"esperado status {sorted(expected_statuses)}, recebido {result.status}"
    if required_body_key and result.status in expected_statuses and not body_ok:
        details = f"status ok, mas faltou chave {required_body_key}"

    return CheckResult(
        name=name,
        ok=ok,
        status=result.status,
        latency_ms=result.latency_ms,
        details=details,
    )


def _skip_check(name: str, reason: str) -> CheckResult:
    return CheckResult(
        name=name,
        ok=True,
        status=None,
        latency_ms=None,
        details=reason,
        skipped=True,
    )


def _print_result(result: CheckResult) -> None:
    tag = "SKIP" if result.skipped else ("OK" if result.ok else "FAIL")
    status = "-" if result.status is None else str(result.status)
    latency = "-" if result.latency_ms is None else f"{result.latency_ms:.2f}"
    print(f"[{tag}] {result.name:<52} status={status:<4} latency={latency:<10} | {result.details}")


def _profile_payload(*, main_goal: str) -> dict[str, Any]:
    return {
        "autonomy_mode": "assistida",
        "main_goal": main_goal,
        "decision_style": "equilibrado",
        "preferred_contact_period": "manha",
        "guardrail_max_discount_pct": 8,
        "guardrail_min_net_margin_pct": 7,
        "guardrail_max_response_hours": 12,
        "guardrail_risk_tolerance": "medio",
        "flash_auction_window_minutes": 90,
        "flash_spoilage_risk_threshold": 62,
        "auto_execute_limit_per_day": 0,
    }


def _analyst_expected_statuses(value: str) -> set[int]:
    if value == "200":
        return {200}
    if value == "403":
        return {403}
    return {200, 403}


def _token_arg(parser: argparse.ArgumentParser, arg_name: str, env_name: str, help_text: str) -> None:
    parser.add_argument(
        arg_name,
        default=os.getenv(env_name, ""),
        help=f"{help_text} (padrao: env {env_name})",
    )


def _normalize_api_prefix(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    normalized = "/" + raw.strip("/")
    return "" if normalized == "/" else normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test RBAC + IA")
    parser.add_argument("--base-url", required=True, help="URL base da API")
    parser.add_argument(
        "--api-prefix",
        default="/api",
        help="prefixo da API (default: /api). Use vazio para ambiente sem prefixo.",
    )
    parser.add_argument("--timeout", type=float, default=12.0, help="timeout por request em segundos")
    parser.add_argument(
        "--strict-ready",
        action="store_true",
        help="falha se /health/ready responder diferente de 200",
    )
    parser.add_argument(
        "--analyst-expected-status",
        choices=["200", "403", "200_or_403"],
        default="200_or_403",
        help="status esperado para /api/ai/agenda/autonomous-commerce com token analyst",
    )

    _token_arg(parser, "--token-platform-support", "WF_TOKEN_PLATFORM_SUPPORT", "token staff_support")
    _token_arg(parser, "--token-platform-ops", "WF_TOKEN_PLATFORM_OPS", "token staff_ops/staff_admin")
    _token_arg(parser, "--token-account-viewer", "WF_TOKEN_ACCOUNT_VIEWER", "token account_viewer")
    _token_arg(parser, "--token-account-manager", "WF_TOKEN_ACCOUNT_MANAGER", "token account_manager/account_owner")
    _token_arg(parser, "--token-account-analyst", "WF_TOKEN_ACCOUNT_ANALYST", "token account_analyst")

    args = parser.parse_args()
    api_prefix = _normalize_api_prefix(args.api_prefix)

    def api_path(path: str) -> str:
        value = str(path or "").strip()
        if not value:
            return api_prefix or "/"
        if not value.startswith("/"):
            value = "/" + value
        return f"{api_prefix}{value}" if api_prefix else value

    checks: list[CheckResult] = []

    live = _request(base_url=args.base_url, path="/health/live", method="GET", timeout=args.timeout)
    checks.append(_ok_check(name="health live", result=live, expected_statuses={200}))

    ready_expected = {200} if args.strict_ready else {200, 503}
    ready = _request(base_url=args.base_url, path="/health/ready", method="GET", timeout=args.timeout)
    checks.append(_ok_check(name="health ready", result=ready, expected_statuses=ready_expected))

    metrics = _request(base_url=args.base_url, path=api_path("/metrics"), method="GET", timeout=args.timeout)
    checks.append(_ok_check(name="api metrics", result=metrics, expected_statuses={200}))

    if args.token_platform_support:
        gov = _request(
            base_url=args.base_url,
            path=api_path("/ai/ops/governance-summary?days=7"),
            method="GET",
            timeout=args.timeout,
            token=args.token_platform_support,
        )
        checks.append(_ok_check(name="platform support governance summary", result=gov, expected_statuses={200}))

        support_write = _request(
            base_url=args.base_url,
            path=api_path("/ai/ops/business-os/marketing-funnel?days=7&min_segment_signals=3&persist=true"),
            method="GET",
            timeout=args.timeout,
            token=args.token_platform_support,
        )
        checks.append(_ok_check(name="platform support write blocked", result=support_write, expected_statuses={403}))
    else:
        checks.append(_skip_check("platform support governance summary", "sem token platform support"))
        checks.append(_skip_check("platform support write blocked", "sem token platform support"))

    if args.token_platform_ops:
        ops_write = _request(
            base_url=args.base_url,
            path=api_path("/ai/ops/business-os/marketing-funnel?days=7&min_segment_signals=3&persist=true"),
            method="GET",
            timeout=args.timeout,
            token=args.token_platform_ops,
        )
        checks.append(_ok_check(name="platform ops write allowed", result=ops_write, expected_statuses={200}))
    else:
        checks.append(_skip_check("platform ops write allowed", "sem token platform ops"))

    if args.token_account_viewer:
        viewer_profile = _request(
            base_url=args.base_url,
            path=api_path("/ai/agenda/profile"),
            method="GET",
            timeout=args.timeout,
            token=args.token_account_viewer,
        )
        checks.append(
            _ok_check(
                name="account viewer profile read",
                result=viewer_profile,
                expected_statuses={200},
                required_body_key="subscription_capabilities",
            )
        )

        viewer_write = _request(
            base_url=args.base_url,
            path=api_path("/ai/agenda/profile"),
            method="POST",
            timeout=args.timeout,
            token=args.token_account_viewer,
            payload=_profile_payload(main_goal="produtividade"),
        )
        checks.append(_ok_check(name="account viewer write blocked", result=viewer_write, expected_statuses={403}))
    else:
        checks.append(_skip_check("account viewer profile read", "sem token account viewer"))
        checks.append(_skip_check("account viewer write blocked", "sem token account viewer"))

    if args.token_account_manager:
        manager_write = _request(
            base_url=args.base_url,
            path=api_path("/ai/agenda/profile"),
            method="POST",
            timeout=args.timeout,
            token=args.token_account_manager,
            payload=_profile_payload(main_goal="margem"),
        )
        checks.append(_ok_check(name="account manager write allowed", result=manager_write, expected_statuses={200}))
    else:
        checks.append(_skip_check("account manager write allowed", "sem token account manager"))

    if args.token_account_analyst:
        analyst_expected = _analyst_expected_statuses(args.analyst_expected_status)
        analyst_auto = _request(
            base_url=args.base_url,
            path=api_path("/ai/agenda/autonomous-commerce"),
            method="GET",
            timeout=args.timeout,
            token=args.token_account_analyst,
        )

        analyst_body_key = "subscription_capabilities" if 200 in analyst_expected else None
        analyst_check = _ok_check(
            name="account analyst autonomous commerce",
            result=analyst_auto,
            expected_statuses=analyst_expected,
            required_body_key=analyst_body_key if analyst_auto.status == 200 else None,
        )
        checks.append(analyst_check)
    else:
        checks.append(_skip_check("account analyst autonomous commerce", "sem token account analyst"))

    print("\n=== RESULTADOS SMOKE RBAC + IA ===")
    for check in checks:
        _print_result(check)

    failures = [item for item in checks if not item.ok and not item.skipped]
    skipped = [item for item in checks if item.skipped]

    print("\n=== RESUMO ===")
    print(f"Total checks: {len(checks)}")
    print(f"Falhas: {len(failures)}")
    print(f"Pulados: {len(skipped)}")

    if failures:
        print("\nSMOKE RBAC + IA FALHOU")
        for failure in failures:
            print(f"- {failure.name}: {failure.details}")
        return 1

    if skipped:
        print("\nSMOKE RBAC + IA OK COM CHECKS PULADOS")
        print("Forneca todos os tokens para cobertura completa.")
    else:
        print("\nSMOKE RBAC + IA OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
