#!/usr/bin/env python3
"""Smoke test simples para endpoints operacionais de health/metrics.

Uso:
  python scripts/03_smoke_health_metrics.py --base-url https://wallfruits-backend.onrender.com
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class EndpointResult:
    path: str
    status: int
    latency_ms: float
    body: dict[str, Any] | str


def fetch_json(base_url: str, path: str, timeout: float) -> EndpointResult:
    url = f"{base_url.rstrip('/')}{path}"
    req = Request(url, headers={"Accept": "application/json"}, method="GET")
    started = time.perf_counter()

    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            latency_ms = (time.perf_counter() - started) * 1000
            try:
                body: dict[str, Any] | str = json.loads(raw)
            except json.JSONDecodeError:
                body = raw
            return EndpointResult(path=path, status=resp.status, latency_ms=latency_ms, body=body)
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        latency_ms = (time.perf_counter() - started) * 1000
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = raw
        return EndpointResult(path=path, status=exc.code, latency_ms=latency_ms, body=body)
    except URLError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return EndpointResult(path=path, status=0, latency_ms=latency_ms, body=f"falha de rede: {exc}")
    except (TimeoutError, socket.timeout) as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return EndpointResult(path=path, status=0, latency_ms=latency_ms, body=f"timeout: {exc}")


def print_result(result: EndpointResult) -> None:
    body_preview = result.body
    if isinstance(body_preview, dict):
        body_preview = json.dumps(body_preview, ensure_ascii=False)
    body_preview = str(body_preview)
    if len(body_preview) > 220:
        body_preview = body_preview[:217] + "..."

    print(
        f"[{result.status}] {result.path:<14} "
        f"{result.latency_ms:8.2f} ms | {body_preview}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test de health e metrics")
    parser.add_argument("--base-url", required=True, help="URL base da API")
    parser.add_argument("--timeout", type=float, default=10.0, help="timeout por request em segundos")
    parser.add_argument(
        "--strict-ready",
        action="store_true",
        help="falha se /health/ready responder diferente de 200",
    )
    args = parser.parse_args()

    endpoints = [
        "/health/live",
        "/health",
        "/health/ready",
        "/api/health",
        "/api/metrics",
    ]

    results: list[EndpointResult] = []
    for path in endpoints:
        result = fetch_json(args.base_url, path, args.timeout)
        results.append(result)
        print_result(result)

    status_map = {item.path: item.status for item in results}

    failures: list[str] = []

    # Liveness sempre precisa estar OK.
    if status_map.get("/health/live") != 200:
        failures.append("/health/live deve responder 200")

    # Metrics precisa estar acessivel para observabilidade.
    if status_map.get("/api/metrics") != 200:
        failures.append("/api/metrics deve responder 200")

    # /health pode retornar 503 em degradacao, mas endpoint deve responder.
    if status_map.get("/health") not in {200, 503}:
        failures.append("/health deve responder 200 ou 503")

    if status_map.get("/api/health") not in {200, 503}:
        failures.append("/api/health deve responder 200 ou 503")

    if args.strict_ready and status_map.get("/health/ready") != 200:
        failures.append("/health/ready deve responder 200 em modo --strict-ready")

    if failures:
        print("\nSMOKE TEST FALHOU:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nSMOKE TEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
