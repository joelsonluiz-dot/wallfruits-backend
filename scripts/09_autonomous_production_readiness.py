#!/usr/bin/env python3
"""Checklist autonomo de readiness para producao.

Valida:
- Arquivos e workflows criticos para estrategia mobile nativo + web desktop.
- Regra de bloqueio mobile no Nginx.
- Pagina mobile de orientacao para app nativo.
- (Opcional) smoke remoto da API e da politica desktop/mobile web.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Check:
    name: str
    ok: bool
    details: str


def _print(check: Check) -> None:
    tag = "OK" if check.ok else "FAIL"
    print(f"[{tag}] {check.name}: {check.details}")


def _exists(path: str) -> Check:
    full = ROOT / path
    return Check(path, full.exists(), f"presente em {full}" if full.exists() else "arquivo ausente")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _check_nginx_policy() -> Check:
    path = "desktop-web/nginx.conf"
    try:
        content = _read(path)
    except OSError as exc:
        return Check("nginx policy", False, f"falha ao ler {path}: {exc}")

    required = [
        "map $http_user_agent $is_mobile_web",
        "if ($is_mobile_web = 1)",
        "return 302 /mobile-app.html;",
    ]

    missing = [token for token in required if token not in content]
    if missing:
        return Check("nginx policy", False, f"faltando: {', '.join(missing)}")

    return Check("nginx policy", True, "regra mobile->/mobile-app.html detectada no desktop-web/nginx.conf")


def _check_mobile_page() -> Check:
    path = "desktop-web/public/mobile-app.html"
    try:
        content = _read(path)
    except OSError as exc:
        return Check("mobile page", False, f"falha ao ler {path}: {exc}")

    has_play = "play.google.com" in content
    # Accept both canonical App Store patterns used in docs/pages.
    has_app_store = (
        "apple.com/app-store" in content
        or "apps.apple.com" in content
    )

    if not (has_play and has_app_store):
        return Check("mobile page", False, "links de loja nao encontrados")

    placeholder = (
        "Substitua os links das lojas pelos URLs oficiais" in content
        or "Substitua os links das lojas" in content
    )

    if placeholder:
        return Check("mobile page", False, "links ainda estao placeholders")

    return Check("mobile page", True, "links de loja definidos")


def _run_python(script_rel: str, args: list[str]) -> tuple[bool, str]:
    script = ROOT / script_rel
    if not script.exists():
        return False, f"script ausente: {script_rel}"

    cmd = [sys.executable, str(script), *args]
    started = time.perf_counter()

    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    elapsed = (time.perf_counter() - started) * 1000

    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    output = output.strip()
    if len(output) > 450:
        output = output[:450] + "..."

    if proc.returncode != 0:
        return False, f"rc={proc.returncode}, {elapsed:.0f}ms, out={output}"

    return True, f"rc=0, {elapsed:.0f}ms"


def _fetch(url: str, user_agent: str) -> tuple[int, str, str]:
    req = Request(url, headers={"User-Agent": user_agent})
    opener = build_opener(HTTPRedirectHandler())
    started = time.perf_counter()
    try:
        with opener.open(req, timeout=20) as response:
            return response.status, response.geturl(), f"{(time.perf_counter() - started) * 1000:.0f}ms"
    except HTTPError as exc:
        return exc.code, exc.geturl(), f"{(time.perf_counter() - started) * 1000:.0f}ms"
    except (URLError, TimeoutError, socket.timeout) as exc:
        return 0, url, f"erro de rede: {exc}"


def _smoke_web_policy(base_url: str) -> Check:
    desktop_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    mobile_ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    )

    d_status, d_url, d_lat = _fetch(base_url, desktop_ua)
    m_status, m_url, m_lat = _fetch(base_url, mobile_ua)

    ok = d_status < 400 and m_url.endswith("/mobile-app.html")
    details = (
        f"desktop={d_status} {d_lat} -> {d_url} | "
        f"mobile={m_status} {m_lat} -> {m_url}"
    )
    return Check("web desktop/mobile smoke", ok, details)


def main() -> int:
    parser = argparse.ArgumentParser(description="Readiness autonomo de producao")
    parser.add_argument("--api-base-url", default="", help="URL base da API para smoke remoto")
    parser.add_argument("--web-base-url", default="", help="URL base da web para smoke remoto")
    parser.add_argument("--strict", action="store_true", help="falhar se houver pendencias manuais")
    args = parser.parse_args()

    checks: list[Check] = []

    required_files = [
        "desktop-web/nginx.conf",
        "desktop-web/public/mobile-app.html",
        ".github/workflows/build-android-aab-release.yml",
        ".github/workflows/ios-testflight-native.yml",
        ".github/workflows/smoke-web-desktop-mobile-policy.yml",
        "docs/UPGRADE_PRODUCAO_NATIVO_DESKTOP_WEB.md",
        "docs/CI_CD_MOBILE_PRODUCAO.md",
    ]

    checks.extend(_exists(path) for path in required_files)
    checks.append(_check_nginx_policy())

    # Sem --strict, placeholder de loja vira warning informativo (ok=True com detalhe).
    mobile_page = _check_mobile_page()
    if not args.strict and mobile_page.details == "links ainda estao placeholders":
        checks.append(Check("mobile page", True, "placeholder detectado (pendencia manual conhecida)"))
    else:
        checks.append(mobile_page)

    if args.api_base_url:
        ok, details = _run_python(
            "scripts/03_smoke_health_metrics.py",
            ["--base-url", args.api_base_url, "--strict-ready"],
        )
        checks.append(Check("api smoke health/metrics", ok, details))

    if args.web_base_url:
        checks.append(_smoke_web_policy(args.web_base_url))

    has_fail = False
    print("\n=== AUTONOMOUS PRODUCTION READINESS ===")
    for check in checks:
        _print(check)
        if not check.ok:
            has_fail = True

    if has_fail:
        print("\nRESULTADO: FAIL")
        return 1

    print("\nRESULTADO: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
