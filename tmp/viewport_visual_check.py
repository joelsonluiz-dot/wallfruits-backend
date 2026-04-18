from pathlib import Path
import json
import os
from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("WF_CHECK_BASE_URL", "http://127.0.0.1:8015")
OUT_DIR = Path("tmp/visual-check")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("store", "/store"),
    ("cart", "/store/cart"),
    ("checkout", "/store/checkout"),
    ("orders", "/store/orders"),
]

VIEWPORTS = [
    ("mobile", {"width": 390, "height": 844}),
    ("tablet-portrait", {"width": 768, "height": 1024}),
    ("tablet-landscape", {"width": 1024, "height": 768}),
]


def collect_metrics(page):
    return page.evaluate(
        """
        () => {
          const doc = document.documentElement;
          const body = document.body;
          const width = window.innerWidth;
          const scrollWidth = Math.max(doc ? doc.scrollWidth : 0, body ? body.scrollWidth : 0);
          const overflowX = scrollWidth > width + 1;

          const actions = Array.from(document.querySelectorAll('a,button,input,select')).slice(0, 120);
          let tinyTapTargets = 0;
          for (const el of actions) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0 && (rect.width < 32 || rect.height < 32)) {
              tinyTapTargets += 1;
            }
          }

          return {
            title: document.title || '',
            overflowX,
            innerWidth: width,
            scrollWidth,
            tinyTapTargets,
            hasHeader: !!document.querySelector('header'),
            cardCount: document.querySelectorAll('[class*="card"], article').length,
            alerts: document.querySelectorAll('.wf-alert').length,
          };
        }
        """
    )


results = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    for viewport_name, viewport in VIEWPORTS:
        context = browser.new_context(
            viewport=viewport,
            device_scale_factor=2,
            locale="pt-BR",
        )
        # Evita redirecionamento por ausência de token em páginas privadas.
        context.add_init_script("localStorage.setItem('token','visual-check-token');")
        page = context.new_page()

        for page_name, route in PAGES:
            url = f"{BASE_URL}{route}"
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1800)

            screenshot_name = f"{page_name}-{viewport_name}.png"
            screenshot_path = OUT_DIR / screenshot_name
            page.screenshot(path=str(screenshot_path), full_page=False, timeout=120000)

            metrics = collect_metrics(page)
            metrics.update(
                {
                    "page": page_name,
                    "route": route,
                    "viewport": viewport_name,
                    "screenshot": str(screenshot_path).replace('\\\\', '/'),
                }
            )
            results.append(metrics)

        context.close()

    browser.close()

report_path = OUT_DIR / "report.json"
report_path.write_text(json.dumps(results, ensure_ascii=True, indent=2), encoding="utf-8")
print(str(report_path))
