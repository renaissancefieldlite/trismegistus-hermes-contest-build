#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from browser_cdp_smoke import chrome_binary, wait_for_cdp


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "browser_autonomy"
TRACE_PORT = 9224
TRACE_PROFILE = ROOT / "data" / "browser_profiles" / "tris-live-site-sequence"

DEFAULT_TARGETS = [
    {
        "id": "quantinuum",
        "label": "Quantinuum",
        "lane": "nvidia_quantum_partner_candidate",
        "url": "https://www.quantinuum.com/",
        "source_basis": "NVIDIA Accelerated Quantum Research Center / Quantum Day source lane",
        "benchmark_task": "Load the public Quantinuum site and verify that the page identifies a quantum-company source.",
        "objective_checks": [
            {"id": "source_identity", "kind": "text_contains_any", "terms": ["quantinuum"]},
            {"id": "quantum_context", "kind": "text_contains_any", "terms": ["quantum"]},
        ],
    },
    {
        "id": "quera",
        "label": "QuEra",
        "lane": "nvidia_quantum_partner_candidate",
        "url": "https://www.quera.com/",
        "source_basis": "NVIDIA Accelerated Quantum Research Center / Quantum Day source lane",
        "benchmark_task": "Load the public QuEra site and verify quantum/neutral-atom partner context.",
        "objective_checks": [
            {"id": "source_identity", "kind": "text_contains_any", "terms": ["quera"]},
            {"id": "quantum_context", "kind": "text_contains_any", "terms": ["quantum", "neutral atom"]},
        ],
    },
    {
        "id": "quantum_machines",
        "label": "Quantum Machines",
        "lane": "nvidia_quantum_partner_candidate",
        "url": "https://www.quantum-machines.co/",
        "source_basis": "NVIDIA Accelerated Quantum Research Center source lane",
        "benchmark_task": "Load the public Quantum Machines site and verify quantum-control partner context.",
        "objective_checks": [
            {"id": "source_identity", "kind": "text_contains_any", "terms": ["quantum machines"]},
            {"id": "quantum_control_context", "kind": "text_contains_any", "terms": ["quantum control", "orchestration", "quantum"]},
        ],
    },
    {
        "id": "ionq",
        "label": "IonQ",
        "lane": "nvidia_quantum_partner_candidate",
        "url": "https://ionq.com/",
        "source_basis": "NVIDIA Quantum Day source lane",
        "benchmark_task": "Load the public IonQ site and verify quantum/trapped-ion partner context.",
        "objective_checks": [
            {"id": "source_identity", "kind": "text_contains_any", "terms": ["ionq"]},
            {"id": "quantum_context", "kind": "text_contains_any", "terms": ["quantum", "trapped ion"]},
        ],
    },
    {
        "id": "dwave",
        "label": "D-Wave",
        "lane": "nvidia_quantum_partner_candidate",
        "url": "https://www.dwavequantum.com/",
        "source_basis": "NVIDIA Quantum Day source lane",
        "benchmark_task": "Load the public D-Wave site and verify quantum/annealing or optimization context.",
        "objective_checks": [
            {"id": "source_identity", "kind": "text_contains_any", "terms": ["d-wave", "dwave"]},
            {"id": "quantum_context", "kind": "text_contains_any", "terms": ["quantum", "annealing", "optimization"]},
        ],
    },
    {
        "id": "nous_careers",
        "label": "Nous Research careers",
        "lane": "nous_research_roles",
        "url": "https://nousresearch.com/careers",
        "source_basis": "Official Nous Research careers page",
        "benchmark_task": "Load the official Nous careers page and verify role/application evidence.",
        "objective_checks": [
            {"id": "source_identity", "kind": "text_contains_any", "terms": ["nous research"]},
            {"id": "careers_context", "kind": "text_contains_any", "terms": ["research scientist", "forward deployed engineer", "recruiting@nousresearch.com", "careers"]},
        ],
    },
    {
        "id": "rfl_public_stack",
        "label": "Renaissance Field Lite public evidence stack",
        "lane": "renaissance_field_lite_public_surface",
        "url": "https://github.com/renaissancefieldlite/Mirror-Interface-and-Architecture-Evidence-Stack-and-Next-Phases",
        "source_basis": "Public Renaissance Field Lite GitHub surface provided by Architect D",
        "benchmark_task": "Load the public RFL evidence stack and verify Novel Discovery / Mirror Architecture source terms.",
        "objective_checks": [
            {"id": "source_identity", "kind": "text_contains_any", "terms": ["renaissancefieldlite", "mirror-interface-and-architecture-evidence-stack"]},
            {"id": "evidence_context", "kind": "text_contains_any", "terms": ["novel discovery", "pennylane", "qiskit", "phase 12b", "v7"]},
        ],
    },
]

WEB_ARENA_BASELINE_MAP = {
    "official_repo": str(ROOT / "vendor" / "webarena"),
    "task_source_raw": str(ROOT / "vendor" / "webarena" / "config_files" / "test.raw.json"),
    "generated_task_configs": str(ROOT / "vendor" / "webarena" / "config_files"),
    "runner": str(ROOT / "vendor" / "webarena" / "run.py"),
    "environment_urls": str(ROOT / "vendor" / "webarena" / "browser_env" / "env_config.py"),
    "evaluators": str(ROOT / "vendor" / "webarena" / "evaluation_harness" / "evaluators.py"),
    "baseline_prompts": str(ROOT / "vendor" / "webarena" / "agent" / "prompts" / "raw"),
    "browsergym_webarena": str(ROOT / "vendor" / "BrowserGym" / "browsergym" / "webarena"),
    "browsergym_verified": str(ROOT / "vendor" / "BrowserGym" / "browsergym" / "webarena_verified"),
    "boundary": (
        "Current Tris action trace uses the official WebArena homepage subset. "
        "A real WebArena score requires the full self-hosted domain stack, generated task configs, "
        "auth cookies, evaluator harness, and task runner."
    ),
}


def _stamp() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "site"


def _body_text(page: Any, limit: int = 60000) -> str:
    try:
        text = page.locator("body").inner_text(timeout=3500)
    except Exception:  # noqa: BLE001
        return ""
    return " ".join(text.split())[:limit]


def _preview(text: str, limit: int = 900) -> str:
    return " ".join(str(text or "").split())[:limit]


def _normalize_terms(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip().lower() for value in values if str(value).strip()]


def _evaluate_objective_checks(target: dict[str, Any], row: dict[str, Any], body_text: str) -> dict[str, Any]:
    checks = target.get("objective_checks") or []
    if not isinstance(checks, list):
        checks = []
    title = str(row.get("title") or "")
    final_url = str(row.get("final_url") or row.get("url") or "")
    haystacks = {
        "text": f"{title}\n{final_url}\n{body_text}".lower(),
        "title": title.lower(),
        "url": final_url.lower(),
        "body": body_text.lower(),
    }
    evaluated: list[dict[str, Any]] = []
    for index, check in enumerate(checks, start=1):
        if not isinstance(check, dict):
            continue
        kind = str(check.get("kind") or "text_contains_any")
        scope = kind.split("_contains_", 1)[0] if "_contains_" in kind else "text"
        mode = kind.rsplit("_", 1)[-1] if kind.endswith(("_any", "_all")) else "any"
        haystack = haystacks.get(scope, haystacks["text"])
        terms = _normalize_terms(check.get("terms"))
        matches = [term for term in terms if term in haystack]
        if not terms:
            passed = False
        elif mode == "all":
            passed = len(matches) == len(terms)
        else:
            passed = bool(matches)
        evaluated.append(
            {
                "id": str(check.get("id") or f"check_{index}"),
                "kind": kind,
                "terms": terms,
                "matched_terms": matches,
                "passed": passed,
            }
        )
    if not evaluated:
        evaluated.append(
            {
                "id": "page_loaded",
                "kind": "load_check",
                "terms": [],
                "matched_terms": [],
                "passed": bool(row.get("ok")),
            }
        )
    passed_count = sum(1 for item in evaluated if item.get("passed"))
    return {
        "objective_ok": bool(row.get("ok")) and passed_count == len(evaluated),
        "objective_pass_count": passed_count,
        "objective_check_count": len(evaluated),
        "objective_checks": evaluated,
        "benchmark_task": str(target.get("benchmark_task") or "Load public source target and verify objective criteria."),
    }


def _load_targets(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return [dict(item) for item in DEFAULT_TARGETS]
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Target file must contain a JSON list.")
    targets: list[dict[str, str]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict) or not item.get("url"):
            raise ValueError(f"Target {index} is missing url.")
        targets.append(
            {
                "id": str(item.get("id") or _slug(str(item["url"]))),
                "label": str(item.get("label") or item["url"]),
                "lane": str(item.get("lane") or "live_source"),
                "url": str(item["url"]),
                "source_basis": str(item.get("source_basis") or "operator provided"),
                "benchmark_task": str(item.get("benchmark_task") or item.get("task") or "Load public source target."),
                "objective_checks": item.get("objective_checks") or item.get("checks") or [],
            }
        )
    return targets


def run_sequence(targets: list[dict[str, Any]], port: int, timeout: float) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sequence_id = f"tris_live_site_sequence_{_stamp()}"
    screenshot_dir = OUT_DIR / sequence_id
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    trace_path = OUT_DIR / f"{sequence_id}.zip"
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
        "about:blank",
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cdp = wait_for_cdp(port, timeout)
    if not cdp.get("ok"):
        raise RuntimeError(cdp.get("error") or f"CDP did not respond on {port}")

    started = time.time()
    results: list[dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=timeout * 1000)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        try:
            for index, target in enumerate(targets, start=1):
                site_started = time.time()
                screenshot_path = screenshot_dir / f"{index:02d}_{_slug(target['id'])}.png"
                row: dict[str, Any] = {
                    "index": index,
                    "id": target["id"],
                    "label": target["label"],
                    "lane": target["lane"],
                    "url": target["url"],
                    "source_basis": target["source_basis"],
                    "ok": False,
                    "status": None,
                    "title": "",
                    "final_url": "",
                    "body_preview": "",
                    "screenshot": str(screenshot_path),
                }
                try:
                    response = page.goto(target["url"], wait_until="domcontentloaded", timeout=timeout * 1000)
                    page.wait_for_timeout(900)
                    row["status"] = response.status if response else None
                    row["title"] = page.title()
                    row["final_url"] = page.url
                    body_text = _body_text(page)
                    row["body_preview"] = _preview(body_text)
                    row["ok"] = bool(row["title"] or row["body_preview"]) and (
                        row["status"] is None or int(row["status"]) < 500
                    )
                    row.update(_evaluate_objective_checks(target, row, body_text))
                    page.screenshot(path=str(screenshot_path), full_page=False)
                except Exception as exc:  # noqa: BLE001
                    row["error"] = f"{type(exc).__name__}: {exc}"
                    row.update(_evaluate_objective_checks(target, row, ""))
                    try:
                        page.screenshot(path=str(screenshot_path), full_page=False)
                    except Exception:  # noqa: BLE001
                        row["screenshot"] = ""
                row["latency_ms"] = round((time.time() - site_started) * 1000)
                results.append(row)
        finally:
            context.tracing.stop(path=str(trace_path))
            browser.close()
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()

    ok_count = sum(1 for item in results if item.get("ok"))
    objective_ok_count = sum(1 for item in results if item.get("objective_ok"))
    return {
        "id": sequence_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": ok_count == len(results),
        "partial_ok": ok_count > 0,
        "ok_count": ok_count,
        "objective_ok": objective_ok_count == len(results),
        "objective_ok_count": objective_ok_count,
        "target_count": len(results),
        "port": port,
        "chrome_binary": binary,
        "profile": str(TRACE_PROFILE),
        "trace": str(trace_path),
        "screenshot_dir": str(screenshot_dir),
        "results": results,
        "webarena_baseline_map": WEB_ARENA_BASELINE_MAP,
        "read": (
            "Tris navigated live public source targets through Playwright over CDP, saved screenshots/trace, "
            "and scored objective source checks for each target. This is real public-web validation for the "
            "field mission bridge, not outreach and not a full official WebArena/SWE/GAIA score."
        ),
        "next_gate": (
            "Promote objective-passing pages into Tris source/evidence tables, then run baseline Hermes versus "
            "Tris architecture-on against the same public-web tasks before graduating to official WebArena."
        ),
        "boundary": (
            "Visited pages can change, block, or render client-side. This receipt is a tangible real-world browser "
            "benchmark slice with objective checks; public claims should not treat it as partnership proof or as an "
            "official WebArena benchmark score."
        ),
        "latency_ms": round((time.time() - started) * 1000),
    }


def write_receipt(receipt: dict[str, Any]) -> dict[str, str]:
    json_path = OUT_DIR / f"{receipt['id']}.json"
    md_path = OUT_DIR / f"{receipt['id']}.md"
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# Tris Live Site Sequence {receipt['id']}",
        "",
        f"- OK: `{receipt['ok']}`",
        f"- Partial OK: `{receipt['partial_ok']}`",
        f"- Targets loaded: `{receipt['ok_count']}/{receipt['target_count']}`",
        f"- Objective checks passed: `{receipt.get('objective_ok_count')}/{receipt['target_count']}`",
        f"- Objective OK: `{receipt.get('objective_ok')}`",
        f"- Trace: `{receipt['trace']}`",
        f"- Screenshots: `{receipt['screenshot_dir']}`",
        "",
        "## Live Targets",
        "",
    ]
    for item in receipt["results"]:
        lines.extend(
            [
                f"### {item['index']}. {item['label']}",
                "",
                f"- Lane: `{item['lane']}`",
                f"- URL: `{item['url']}`",
                f"- Final URL: `{item.get('final_url')}`",
                f"- Status: `{item.get('status')}`",
                f"- Title: `{item.get('title')}`",
                f"- Loaded: `{item.get('ok')}`",
                f"- Benchmark task: {item.get('benchmark_task')}",
                f"- Objective OK: `{item.get('objective_ok')}`",
                f"- Objective checks: `{item.get('objective_pass_count')}/{item.get('objective_check_count')}`",
                f"- Screenshot: `{item.get('screenshot')}`",
                f"- Source basis: {item.get('source_basis')}",
                "",
                "Objective check detail:",
                "",
                *[
                    f"- `{check.get('id')}`: passed=`{check.get('passed')}` "
                    f"matched=`{', '.join(check.get('matched_terms') or []) or 'none'}`"
                    for check in item.get("objective_checks") or []
                ],
                "",
                "Preview:",
                "",
                item.get("body_preview") or item.get("error") or "No body preview captured.",
                "",
            ]
        )
    lines.extend(
        [
            "## WebArena Baseline Map",
            "",
        ]
    )
    for key, value in receipt["webarena_baseline_map"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Read",
            "",
            receipt["read"],
            "",
            "## Boundary",
            "",
            receipt["boundary"],
            "",
            "## Next Gate",
            "",
            receipt["next_gate"],
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    first_screenshot = next((item.get("screenshot") for item in receipt["results"] if item.get("screenshot")), "")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "trace": str(receipt["trace"]),
        "screenshot": str(first_screenshot),
        "screenshot_dir": str(receipt["screenshot_dir"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Tris live source target navigation over Playwright/CDP.")
    parser.add_argument("--targets-json", default="")
    parser.add_argument("--port", type=int, default=TRACE_PORT)
    parser.add_argument("--timeout", type=float, default=24.0)
    args = parser.parse_args()

    try:
        targets = _load_targets(args.targets_json or None)
        receipt = run_sequence(targets, args.port, args.timeout)
        paths = write_receipt(receipt)
    except Exception as exc:  # noqa: BLE001
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        failed = {
            "id": f"tris_live_site_sequence_{_stamp()}",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "boundary": "Live source sequence failed before a verified navigation receipt was saved.",
            "webarena_baseline_map": WEB_ARENA_BASELINE_MAP,
        }
        json_path = OUT_DIR / f"{failed['id']}.json"
        md_path = OUT_DIR / f"{failed['id']}.md"
        json_path.write_text(json.dumps(failed, indent=2, sort_keys=True), encoding="utf-8")
        md_path.write_text(f"# Tris Live Site Sequence {failed['id']}\n\n{failed['error']}\n", encoding="utf-8")
        print("Tris live site sequence")
        print(f"JSON: {json_path}")
        print(f"Markdown: {md_path}")
        print(f"Error: {failed['error']}")
        return 2

    print("Tris live site sequence")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    print(f"Trace: {paths['trace']}")
    print(f"Screenshot: {paths['screenshot']}")
    print(f"Screenshot dir: {paths['screenshot_dir']}")
    print(f"OK: {receipt['ok']}")
    print(f"Loaded: {receipt['ok_count']}/{receipt['target_count']}")
    print(f"Objective: {receipt.get('objective_ok_count')}/{receipt['target_count']}")
    return 0 if receipt["partial_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
