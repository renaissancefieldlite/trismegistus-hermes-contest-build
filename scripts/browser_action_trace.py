#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from typing import Any

from browser_cdp_smoke import DEFAULT_PROFILE, chrome_binary, wait_for_cdp


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "browser_autonomy"
TRACE_PORT = 9223
TRACE_PROFILE = ROOT / "data" / "browser_profiles" / "tris-action-trace"


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def expected_value(expression: str) -> str:
    allowed = set("0123456789+-*/(). ")
    if not expression or any(char not in allowed for char in expression):
        raise ValueError("Expression must be simple calculator arithmetic.")
    value = eval(expression, {"__builtins__": {}}, {})  # noqa: S307 - bounded demo calculator expression.
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def run_trace(url: str, expression: str, port: int, timeout: float) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trace_id = f"tris_browser_action_trace_{_stamp()}"
    trace_path = OUT_DIR / f"{trace_id}.zip"
    screenshot_path = OUT_DIR / f"{trace_id}.png"
    expected = expected_value(expression)
    process: subprocess.Popen[Any] | None = None
    binary = chrome_binary()
    if not binary:
        raise RuntimeError("No Chrome/Chromium/Brave binary found.")
    TRACE_PROFILE.mkdir(parents=True, exist_ok=True)
    command = [
        binary,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={TRACE_PROFILE}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = wait_for_cdp(port, timeout)
    if not cdp.get("ok"):
        raise RuntimeError(cdp.get("error") or f"CDP did not respond on {port}")

    actions: list[dict[str, Any]] = []
    assertions: dict[str, bool] = {}
    started = time.time()
    title = ""
    current_url = ""
    result_text = ""
    cards: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=timeout * 1000)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            title = page.title()
            current_url = page.url
            assertions["homepage_loaded"] = "Homepage" in title or "WebArena" in page.locator("body").inner_text(timeout=3000)
            cards = [text.strip() for text in page.locator(".card h2").all_inner_texts() if text.strip()]
            actions.append(
                {
                    "step": "open_webarena_homepage",
                    "url": current_url,
                    "title": title,
                    "verified": assertions["homepage_loaded"],
                    "observed_cards": cards,
                }
            )

            page.locator('a[href="calculator.html"]').first.click(timeout=timeout * 1000)
            page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
            title = page.title()
            current_url = page.url
            assertions["calculator_loaded"] = "calculator" in title.lower() and page.locator("#inputExpression").count() == 1
            actions.append(
                {
                    "step": "open_calculator",
                    "url": current_url,
                    "title": title,
                    "verified": assertions["calculator_loaded"],
                }
            )

            page.fill("#inputExpression", expression)
            page.click("#calculate")
            result_text = page.locator("#calculationResult").inner_text(timeout=3000).strip()
            assertions["calculator_result_verified"] = result_text == expected
            actions.append(
                {
                    "step": "calculate_expression",
                    "expression": expression,
                    "expected": expected,
                    "observed": result_text,
                    "verified": assertions["calculator_result_verified"],
                }
            )
            page.screenshot(path=str(screenshot_path), full_page=False)
        finally:
            context.tracing.stop(path=str(trace_path))
            browser.close()
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()

    return {
        "id": trace_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": all(assertions.values()),
        "url": url,
        "final_url": current_url,
        "title": title,
        "port": port,
        "chrome_binary": binary,
        "expression": expression,
        "expected": expected,
        "observed": result_text,
        "latency_ms": round((time.time() - started) * 1000),
        "assertions": assertions,
        "actions": actions,
        "paths": {
            "trace": str(trace_path),
            "screenshot": str(screenshot_path),
        },
        "playwright_edge": {
            "planner": "bounded task plan: homepage -> calculator -> expression -> state check",
            "executor": "Playwright over CDP with a separate Chrome profile",
            "verifier": "DOM title, input presence, observed calculator result, and saved trace",
            "workflow_memory_seed": actions,
            "next_upgrade": "store successful sequences by site/task and replay them before asking the model to rediscover the workflow.",
        },
        "boundary": "First bounded browser action trace against the official WebArena homepage subset. This is an action receipt, not a full WebArena score.",
    }


def write_receipt(receipt: dict[str, Any]) -> dict[str, str]:
    json_path = OUT_DIR / f"{receipt['id']}.json"
    md_path = OUT_DIR / f"{receipt['id']}.md"
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# Tris Browser Action Trace {receipt['id']}",
        "",
        f"- URL: `{receipt['url']}`",
        f"- Final URL: `{receipt['final_url']}`",
        f"- OK: `{receipt['ok']}`",
        f"- Expression: `{receipt['expression']}`",
        f"- Expected: `{receipt['expected']}`",
        f"- Observed: `{receipt['observed']}`",
        f"- Trace: `{receipt['paths']['trace']}`",
        f"- Screenshot: `{receipt['paths']['screenshot']}`",
        "",
        "## Actions",
        "",
    ]
    for action in receipt["actions"]:
        lines.append(f"- `{action['step']}` verified=`{action.get('verified')}`")
    lines.extend(
        [
            "",
            "## Edge Pattern",
            "",
            "- Planner/executor split.",
            "- Page-state verification after each action.",
            "- Playwright trace saved for replay and failure review.",
            "- Successful sequence stored as a workflow-memory seed.",
            "",
            "## Boundary",
            "",
            receipt["boundary"],
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), **receipt["paths"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a bounded Tris browser action trace against WebArena homepage.")
    parser.add_argument("--url", default="http://127.0.0.1:4399/")
    parser.add_argument("--expression", default="67+5")
    parser.add_argument("--port", type=int, default=TRACE_PORT)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    try:
        receipt = run_trace(args.url, args.expression, args.port, args.timeout)
        paths = write_receipt(receipt)
    except Exception as exc:  # noqa: BLE001
        failed = {
            "id": f"tris_browser_action_trace_{_stamp()}",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ok": False,
            "url": args.url,
            "expression": args.expression,
            "error": f"{type(exc).__name__}: {exc}",
            "boundary": "Trace failed before a verified action receipt was saved.",
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = OUT_DIR / f"{failed['id']}.json"
        md_path = OUT_DIR / f"{failed['id']}.md"
        json_path.write_text(json.dumps(failed, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(f"# Tris Browser Action Trace {failed['id']}\n\n{failed['error']}\n", encoding="utf-8")
        print("Tris browser action trace")
        print(f"JSON: {json_path}")
        print(f"Markdown: {md_path}")
        print(f"Error: {failed['error']}")
        return 2

    print("Tris browser action trace")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"Trace: {paths['trace']}")
    print(f"Screenshot: {paths['screenshot']}")
    print(f"OK: {receipt['ok']}")
    return 0 if receipt["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
