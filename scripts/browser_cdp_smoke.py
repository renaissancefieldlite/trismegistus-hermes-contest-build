#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "browser_autonomy"
DEFAULT_PORT = 9222
DEFAULT_PROFILE = ROOT / "data" / "browser_profiles" / "tris-cdp"


def chrome_binary() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def wait_for_cdp(port: int, timeout: float) -> dict[str, Any]:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                return {"ok": True, "version": json.loads(response.read().decode("utf-8"))}
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.5)
    return {"ok": False, "error": last_error or "CDP endpoint did not respond"}


def run_playwright_cdp(port: int, url: str, timeout: float) -> dict[str, Any]:
    started = time.time()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "stage": "import_playwright", "error": f"{type(exc).__name__}: {exc}"}

    screenshot_path = OUT_DIR / f"cdp_smoke_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.png"
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=timeout * 1000)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            title = page.title()
            page.screenshot(path=str(screenshot_path), full_page=False)
            browser.close()
        return {
            "ok": True,
            "stage": "playwright_connect_over_cdp",
            "url": url,
            "title": title,
            "screenshot": str(screenshot_path),
            "latency_ms": round((time.time() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "stage": "playwright_connect_over_cdp",
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": round((time.time() - started) * 1000),
        }


def write_receipt(receipt: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_id = receipt["id"]
    json_path = OUT_DIR / f"{receipt_id}.json"
    md_path = OUT_DIR / f"{receipt_id}.md"
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# Tris Browser CDP Smoke {receipt_id}",
        "",
        f"- Chrome binary: `{receipt.get('chrome_binary')}`",
        f"- CDP port: `{receipt.get('port')}`",
        f"- URL: `{receipt.get('url')}`",
        f"- CDP responding: `{receipt.get('cdp', {}).get('ok')}`",
        f"- Playwright attached: `{receipt.get('playwright', {}).get('ok')}`",
        f"- Screenshot: `{receipt.get('playwright', {}).get('screenshot')}`",
        "",
        "## Read",
        "",
        "Playwright is the browser-control engine. CDP is the host-browser attachment bridge.",
        "",
        "## Boundary",
        "",
        "This proves the local browser bridge can be launched and attached. It is not a WebArena task-success score.",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch local Chrome CDP and attach with Playwright.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--url", default="http://127.0.0.1:8898/")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--no-launch", action="store_true", help="Do not launch Chrome; attach to an existing CDP endpoint.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PROFILE.mkdir(parents=True, exist_ok=True)
    binary = chrome_binary()
    process = None
    if not args.no_launch:
        if not binary:
            raise SystemExit("No Chrome/Chromium/Brave binary found.")
        command = [
            binary,
            f"--remote-debugging-port={args.port}",
            f"--user-data-dir={DEFAULT_PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
            args.url,
        ]
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cdp = wait_for_cdp(args.port, args.timeout)
    playwright_result = run_playwright_cdp(args.port, args.url, args.timeout) if cdp.get("ok") else {"ok": False, "stage": "cdp_not_ready"}
    receipt = {
        "id": time.strftime("tris_browser_cdp_smoke_%Y%m%dT%H%M%SZ", time.gmtime()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "chrome_binary": binary,
        "port": args.port,
        "url": args.url,
        "profile": str(DEFAULT_PROFILE),
        "launched_pid": process.pid if process else None,
        "cdp": cdp,
        "playwright": playwright_result,
        "stack_decision": "Combined stack: Playwright browser control, CDP host-browser attachment, Firecrawl fast source/RAG sidecar.",
    }
    paths = write_receipt(receipt)
    print("Tris browser CDP smoke")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"CDP: {cdp.get('ok')}")
    print(f"Playwright attach: {playwright_result.get('ok')}")
    if not playwright_result.get("ok"):
        print(f"Error: {playwright_result.get('error') or cdp.get('error')}")
    return 0 if cdp.get("ok") and playwright_result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
