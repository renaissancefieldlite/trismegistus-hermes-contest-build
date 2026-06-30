#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OUT_DIR = ROOT / "data" / "eval_runs"
BROWSER_DIR = ROOT / "data" / "browser_autonomy"
os.environ.setdefault("TRIS_BASELINE_MAX_NEW_TOKENS", "140")
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT))

from run_coherence_iters import create_thread, post_chat, run_backend  # noqa: E402


def latest_trace() -> Path:
    candidates = sorted(BROWSER_DIR.glob("tris_browser_action_trace_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No WebArena action trace JSON found in {BROWSER_DIR}")
    return candidates[0]


def load_trace(path_arg: str) -> tuple[Path, dict[str, Any]]:
    path = latest_trace() if path_arg == "latest" else Path(path_arg)
    return path, json.loads(path.read_text(encoding="utf-8"))


def build_prompt(trace: dict[str, Any]) -> str:
    actions = "\n".join(
        f"- {item.get('step')}: verified={item.get('verified')} "
        f"url={item.get('url', '')} title={item.get('title', '')} "
        f"expression={item.get('expression', '')} expected={item.get('expected', '')} observed={item.get('observed', '')}"
        for item in trace.get("actions", [])
    )
    assertions = ", ".join(f"{key}={value}" for key, value in (trace.get("assertions") or {}).items())
    return f"""WebArena bounded action receipt task.

This is an evaluation receipt read, not an identity check.
Do not introduce yourself. Do not explain Trismegistus identity.
Use only the receipt fields below and answer the browser-action evidence.

Receipt id: {trace.get('id')}
Subset: official WebArena homepage subset
Start URL: {trace.get('url')}
Final URL: {trace.get('final_url')}
Trace path: {(trace.get('paths') or {}).get('trace')}
Screenshot path: {(trace.get('paths') or {}).get('screenshot')}
Assertions: {assertions}
Expression: {trace.get('expression')}
Expected result: {trace.get('expected')}
Observed result: {trace.get('observed')}
Actions:
{actions}

Required evidence terms to include naturally:
- WebArena
- homepage subset
- calculator
- expression {trace.get('expression')}
- expected {trace.get('expected')}
- observed {trace.get('observed')}
- trace
- not a full official WebArena score
- next gate: stage full WebArena domain containers or expand the official subset

Answer as a Tris AI partner in normal conversational voice, but keep it receipt-bound.
Give exactly four short fields:
Claim, Evidence, Boundary, Next gate.
In the Evidence field, literally include: "trace confirms calculator expression {trace.get('expression')} expected {trace.get('expected')} observed {trace.get('observed')}".
Do not call this a full official WebArena score. Do not claim the full WebArena domains are running.
"""


def score_answer(trace: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    text = str(result.get("text") or "")
    lower = text.lower()
    expected = str(trace.get("expected") or "").lower()
    observed = str(trace.get("observed") or "").lower()
    checks: dict[str, bool] = {
        "answered": bool(result.get("ok")) and bool(text.strip()),
        "no_prompt_spill": not bool(result.get("prompt_spill")),
        "no_raw_receipt_spill": not bool(result.get("raw_receipt_spill")),
        "mentions_webarena": "webarena" in lower,
        "mentions_homepage_subset": "homepage" in lower and "subset" in lower,
        "mentions_calculator_action": "calculator" in lower,
        "mentions_expected_observed": expected in lower and observed in lower,
        "mentions_trace_or_screenshot": "trace" in lower or "screenshot" in lower,
        "states_boundary": "not a full" in lower or "not an official" in lower or "boundary" in lower,
        "states_next_gate": "next gate" in lower or "next step" in lower or "full webarena" in lower,
        "no_full_score_overclaim": not (
            ("full official webarena score" in lower or "official webarena score" in lower)
            and "not a full official webarena score" not in lower
            and "not an official webarena score" not in lower
        ),
    }
    passed = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    return {"checks": checks, "passed": passed, "total": total, "score": round(passed / total, 3)}


def run_route(backend: str, trace: dict[str, Any], base_url: str, timeout: float) -> dict[str, Any]:
    prompt = build_prompt(trace)
    if backend == "architecture_on":
        thread_id = create_thread(base_url, f"tris-webarena-action-compare-{int(time.time())}", timeout)
        result = post_chat(base_url, thread_id, prompt, timeout, benchmark_mode=True)
    else:
        result = run_backend("baseline", base_url, "baseline-webarena-action", prompt, timeout)
    return {
        "backend": backend,
        "result": result,
        "score": score_answer(trace, result),
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"{payload['id']}.json"
    md_path = OUT_DIR / f"{payload['id']}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    comp = payload["comparison"]
    lines = [
        f"# WebArena Action Receipt Baseline vs Tris {payload['id']}",
        "",
        f"- Action receipt: `{payload['action_receipt']}`",
        f"- Baseline score: `{comp['baseline_score']}`",
        f"- Tris architecture-on score: `{comp['architecture_on_score']}`",
        f"- Delta: `{comp['delta']}`",
        "",
        "## Boundary",
        "",
        payload["truth_boundary"],
        "",
        "## Checks",
        "",
        "| Route | Score | Failed Checks |",
        "| --- | ---: | --- |",
    ]
    for route in ("baseline", "architecture_on"):
        run = payload[route]
        failed = [key for key, ok in run["score"]["checks"].items() if not ok]
        lines.append(f"| {route} | {run['score']['score']} | {', '.join(failed) or 'none'} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def save_memory(payload: dict[str, Any], paths: dict[str, str]) -> None:
    from trismegistus import db

    db.save_memory_item(
        "webarena_action_compare_eval",
        f"webarena_action_compare_eval:{payload['id']}",
        "WebArena bounded action receipt baseline versus Tris comparison",
        f"Saved WebArena homepage subset action comparison. JSON: {paths['json']} Markdown: {paths['markdown']}",
        {"id": payload["id"], "paths": paths, "action_receipt": payload["action_receipt"]},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline vs Tris on a bounded WebArena action trace receipt.")
    parser.add_argument("--trace", default="latest")
    parser.add_argument("--base-url", default="http://127.0.0.1:8898")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()

    trace_path, trace = load_trace(args.trace)
    baseline = run_route("baseline", trace, args.base_url, args.timeout)
    architecture = run_route("architecture_on", trace, args.base_url, args.timeout)
    payload = {
        "id": time.strftime("webarena_action_compare_%Y%m%dT%H%M%SZ", time.gmtime()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action_receipt": str(trace_path),
        "truth_boundary": (
            "This compares baseline and Tris on one bounded official WebArena homepage-subset action receipt. "
            "It is not a full WebArena domain run and not an official WebArena score."
        ),
        "baseline": baseline,
        "architecture_on": architecture,
        "comparison": {
            "baseline_score": baseline["score"]["score"],
            "architecture_on_score": architecture["score"]["score"],
            "delta": round(float(architecture["score"]["score"]) - float(baseline["score"]["score"]), 3),
        },
    }
    paths = write_payload(payload)
    save_memory(payload, paths)
    print(json.dumps({"ok": True, "paths": paths, "comparison": payload["comparison"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
