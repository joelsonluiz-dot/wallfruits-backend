#!/usr/bin/env python3
"""Smoke test: web desktop permitido, web mobile redirecionado para app nativo."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request


def _fetch(url: str, user_agent: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
    try:
        with opener.open(req, timeout=20) as response:
            final_url = response.geturl()
            return response.status, final_url
    except urllib.error.HTTPError as exc:
        return exc.code, exc.geturl()


def run(base_url: str) -> int:
    base = base_url.rstrip("/")

    desktop_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    mobile_ua = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Mobile/15E148 Safari/604.1"
    )

    desktop_status, desktop_final = _fetch(base, desktop_ua)
    mobile_status, mobile_final = _fetch(base, mobile_ua)

    print(f"Desktop: status={desktop_status} final_url={desktop_final}")
    print(f"Mobile:  status={mobile_status} final_url={mobile_final}")

    ok = True

    if desktop_status >= 400:
        print("ERRO: desktop web retornou erro.")
        ok = False

    expected_mobile_suffix = "/mobile-app.html"
    parsed_mobile = urllib.parse.urlparse(mobile_final)
    if not parsed_mobile.path.endswith(expected_mobile_suffix):
        print("ERRO: mobile web nao redirecionou para /mobile-app.html.")
        ok = False

    if ok:
        print("OK: politica desktop/mobile valida.")
        return 0

    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valida que desktop web funciona e mobile web redireciona para /mobile-app.html"
    )
    parser.add_argument("--base-url", required=True, help="URL base do site web (ex: https://wallfruits.com.br)")
    args = parser.parse_args()
    return run(args.base_url)


if __name__ == "__main__":
    sys.exit(main())
