#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "coherence_iters"
DEFAULT_BASE_URL = "http://127.0.0.1:8898"
GFL_GENERATE_URL = "http://127.0.0.1:8788/api/generate"
BASELINE_MAX_NEW_TOKENS = int(os.environ.get("TRIS_BASELINE_MAX_NEW_TOKENS", "220"))

PROMPT_SPILL_MARKERS = (
    "external golden field lite / hermes runtime dependency",
    "current runtime receipt:",
    "retrieved golden field lite evidence:",
    "user message:",
    "assistant answer:",
    "this is an evaluation receipt read",
    "do not introduce yourself",
    "do not explain trismegistus identity",
    "use only the receipt fields",
)

RAW_RECEIPT_MARKERS = (
    "tris evidence receipt:",
    "full source receipt:",
)

QUESTION_BANK: list[dict[str, str]] = [
    {
        "lane": "presence",
        "question": "you there check 123",
        "expected": "presence response without receipt spill",
    },
    {
        "lane": "self_explanation",
        "question": "why am I testing simple 123 checks with you right now?",
        "expected": "understands these are coherence probes",
    },
    {
        "lane": "identity",
        "question": "who are you in context of Architect D and Trismegistus?",
        "expected": "explains Tris role without fake claims",
    },
    {
        "lane": "architecture",
        "question": "explain the Trismegistus path as a coherent research and business partner.",
        "expected": "connects conversation, memory, OpenClaw, and the six discipline partner lanes",
    },
    {
        "lane": "receipt_boundary",
        "question": "when should you show receipts and when should they stay behind the veil?",
        "expected": "keeps audit layer behind voice unless proof is requested",
    },
    {
        "lane": "golden_field",
        "question": "tell me what you know about Golden Field Lite so far",
        "expected": "clean source-backed read, not prompt spill",
    },
    {
        "lane": "mirror_architecture",
        "question": "how does Mirror Architecture guide your six discipline partner lanes?",
        "expected": "uses source/evidence lane framing",
    },
    {
        "lane": "openclaw_gate",
        "question": "what is the next OpenClaw/NemoClaw worker gate?",
        "expected": "names worker receipt gate honestly",
    },
    {
        "lane": "telegram_bridge",
        "question": "what should the Telegram channel do when I ask for a source?",
        "expected": "route through Tris field mission bridge",
    },
    {
        "lane": "paid_work",
        "question": "how should you think about the 67 dollar paid-work scouting budget?",
        "expected": "treats paid work as one lane with margin discipline",
    },
    {
        "lane": "clarification",
        "question": "if my message is unclear or too compressed, what should you do?",
        "expected": "ask a concise clarifying question instead of guessing",
    },
    {
        "lane": "meta_improvement",
        "question": "what should improve across a 100 question iteration run?",
        "expected": "meta-awareness of coherence, memory, source accuracy, and mission",
    },
]


def post_chat(
    base_url: str,
    thread_id: str,
    message: str,
    timeout: float,
    *,
    benchmark_mode: bool = False,
) -> dict[str, Any]:
    payload = json.dumps({"thread_id": thread_id, "message": message, "benchmark_mode": benchmark_mode}).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }
    result = data.get("result") if isinstance(data.get("result"), dict) else {}
    text = str(result.get("text") or "")
    lower = text.lower()
    return {
        "ok": bool(result.get("ok", bool(text))) and bool(text.strip()),
        "mode": data.get("mode"),
        "source": result.get("source"),
        "runtime_lane": result.get("runtime_lane"),
        "text": text,
        "latency_ms": round((time.time() - started) * 1000),
        "prompt_spill": any(marker in lower for marker in PROMPT_SPILL_MARKERS),
        "raw_receipt_spill": any(marker in lower for marker in RAW_RECEIPT_MARKERS),
        "http_payload": data,
    }


def create_thread(base_url: str, title: str, timeout: float) -> str:
    payload = json.dumps({"title": title}).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat-threads",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return title
    return str(data.get("thread", {}).get("id") or data.get("id") or title)


def baseline_hermes_generate(message: str, timeout: float) -> dict[str, Any]:
    prompt = f"""You are a baseline local Hermes research assistant.

Answer the user naturally and concisely. Do not use Trismegistus project doctrine, local source tables, or special router rules unless the user supplied them in the message.

User message:
{message}

Assistant answer:
"""
    payload = {
        "prompt": prompt,
        "checkpoint": "hermes",
        "model": "hermes",
        "options": {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_new_tokens": BASELINE_MAX_NEW_TOKENS,
            "repetition_penalty": 1.05,
        },
    }
    request = urllib.request.Request(
        GFL_GENERATE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "source": "baseline-hermes",
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }
    text = str(data.get("response") or data.get("text") or "").strip()
    lower = text.lower()
    return {
        "ok": bool(text),
        "mode": "baseline",
        "source": "baseline-hermes",
        "runtime_lane": "gfl-hermes-no-tris-router",
        "text": text,
        "latency_ms": round((time.time() - started) * 1000),
        "prompt_spill": any(marker in lower for marker in PROMPT_SPILL_MARKERS),
        "raw_receipt_spill": any(marker in lower for marker in RAW_RECEIPT_MARKERS),
        "raw": data,
    }


def run_backend(
    backend: str,
    base_url: str,
    thread_id: str,
    message: str,
    timeout: float,
) -> dict[str, Any]:
    if backend == "architecture_on":
        return post_chat(base_url, thread_id, message, timeout)
    if backend == "baseline":
        return baseline_hermes_generate(message, timeout)
    raise ValueError(f"Unknown backend: {backend}")


def score_turn(probe: dict[str, str], result: dict[str, Any]) -> dict[str, Any]:
    text = str(result.get("text") or "")
    lower = text.lower()
    checks: dict[str, bool] = {
        "answered": bool(result.get("ok")) and bool(text.strip()),
        "no_prompt_spill": not bool(result.get("prompt_spill")),
        "no_raw_receipt_spill": not bool(result.get("raw_receipt_spill")),
    }
    lane = probe["lane"]
    if lane == "presence":
        checks["presence_route"] = result.get("source") == "tris-local-presence"
        checks["mentions_live_tris"] = "tris" in lower and "live" in lower
    if lane == "self_explanation":
        checks["understands_probe"] = "coherence" in lower or "probe" in lower or "arc" in lower
        checks["not_generic_test_answer"] = "basic functionality" not in lower
    if lane == "identity":
        checks["mentions_architect_d"] = "architect d" in lower
        checks["mentions_openclaw_or_gfl"] = "openclaw" in lower or "golden field" in lower or "golden field lite" in lower
    if lane == "architecture":
        checks["mentions_six_or_partner_lanes"] = "six" in lower or "lane" in lower
        checks["mentions_business_or_research_partner"] = "business" in lower or "research partner" in lower
    if lane == "receipt_boundary":
        checks["mentions_receipt_boundary"] = "receipt" in lower and ("proof" in lower or "audit" in lower or "behind" in lower)
    if lane == "clarification":
        checks["mentions_clarification"] = "clarif" in lower or "ask" in lower
    if lane in {"golden_field", "mirror_architecture"}:
        checks["source_backed_but_clean"] = result.get("mode") == "field-mission" and "clean read" in lower
    if lane == "openclaw_gate":
        checks["names_worker_receipt"] = "worker receipt" in lower or ("openclaw" in lower and "receipt" in lower)
    if lane == "telegram_bridge":
        checks["names_field_mission_bridge"] = "field mission" in lower or "/api/field-mission" in lower
    if lane == "paid_work":
        checks["mentions_margin_or_approval"] = "margin" in lower or "approval" in lower or "draft" in lower
    if lane == "meta_improvement":
        checks["mentions_iteration_metrics"] = (
            "source accuracy" in lower
            or "context" in lower
            or "memory" in lower
            or "coherence" in lower
            or "receipt" in lower
        )
    passed = sum(1 for ok in checks.values() if ok)
    total = len(checks)
    return {
        "checks": checks,
        "passed": passed,
        "total": total,
        "score": round(passed / total, 3) if total else 0.0,
    }


def make_probe(index: int) -> dict[str, str]:
    base = QUESTION_BANK[index % len(QUESTION_BANK)]
    cycle = index // len(QUESTION_BANK) + 1
    probe = dict(base)
    if cycle > 1:
        probe["question"] = f"{base['question']} [iteration {cycle}]"
    return probe


def write_outputs(run: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = run["run_id"]
    json_path = OUT_DIR / f"{run_id}.json"
    md_path = OUT_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps(run, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# Tris Coherence Iteration Run {run_id}",
        "",
        f"- Count: `{run['count']}`",
        f"- Passed checks: `{run['summary']['passed_checks']}` / `{run['summary']['total_checks']}`",
        f"- Mean score: `{run['summary']['mean_score']}`",
        f"- Prompt spills: `{run['summary']['prompt_spills']}`",
        f"- Raw receipt spills: `{run['summary']['raw_receipt_spills']}`",
        "",
        "## Boundary",
        "",
        "Engineering eval and demo trace for measuring context stability, field-expert growth, source discipline, and mission coherence.",
        "",
        "## Turns",
        "",
    ]
    for turn in run["turns"]:
        text = str(turn.get("result", {}).get("text") or "").strip().replace("\n", " ")
        if len(text) > 700:
            text = text[:700] + "..."
        lines.extend(
            [
                f"### {turn['index']:03d} / {turn['lane']}",
                "",
                f"Question: {turn['question']}",
                "",
                f"Expected: {turn['expected']}",
                "",
                f"Score: `{turn['score']['score']}`",
                "",
                f"Answer: {text}",
                "",
            ]
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def save_memory_receipt(run: dict[str, Any], paths: dict[str, str]) -> None:
    sys.path.insert(0, str(ROOT))
    try:
        from trismegistus import db

        db.save_memory_item(
            "coherence_iteration_run",
            f"coherence_iter:{run['run_id']}",
            f"Tris coherence iter run {run['count']} turns",
            (
                f"Ran {run['count']} live coherence probes. "
                f"Mean score {run['summary']['mean_score']}; "
                f"prompt spills {run['summary']['prompt_spills']}; "
                f"raw receipt spills {run['summary']['raw_receipt_spills']}. "
                f"JSON: {paths['json']} Markdown: {paths['markdown']}"
            ),
            {"run": run["summary"], "paths": paths},
        )
    except Exception as exc:  # noqa: BLE001 - logging should not kill the visible run.
        print(f"[warn] memory receipt not saved: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run visible Tris coherence iteration probes.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--thread-id", default="tris-coherence-iters")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--pause", type=float, default=0.0)
    parser.add_argument(
        "--backend",
        choices=("architecture_on", "baseline"),
        default="architecture_on",
        help="architecture_on calls live Tris /api/chat; baseline calls the raw Hermes/GFL generate route.",
    )
    parser.add_argument(
        "--no-create-thread",
        action="store_true",
        help="Use the supplied thread id as-is instead of creating one run thread.",
    )
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be at least 1")

    run_id = time.strftime("tris_coherence_iter_%Y%m%dT%H%M%SZ", time.gmtime())
    thread_id = args.thread_id
    if args.backend == "architecture_on" and not args.no_create_thread:
        thread_id = create_thread(args.base_url, f"Tris coherence iter {run_id}", args.timeout)
    turns: list[dict[str, Any]] = []
    print(f"Tris coherence iteration run: {run_id}")
    print(f"Base URL: {args.base_url}")
    print(f"Backend: {args.backend}")
    print(f"Thread: {thread_id}")
    print(f"Count: {args.count}")
    print("Boundary: engineering eval and demo trace for measuring context stability and field-expert growth.")
    print("")
    for index in range(args.count):
        probe = make_probe(index)
        print(f"[{index + 1:03d}/{args.count:03d}] {probe['lane']} :: {probe['question']}")
        result = run_backend(args.backend, args.base_url, thread_id, probe["question"], args.timeout)
        score = score_turn(probe, result)
        answer = str(result.get("text") or result.get("error") or "").strip().replace("\n", " ")
        if len(answer) > 260:
            answer = answer[:260] + "..."
        print(
            f"  score={score['score']} mode={result.get('mode')} source={result.get('source')} "
            f"prompt_spill={result.get('prompt_spill')} receipt_spill={result.get('raw_receipt_spill')}"
        )
        print(f"  answer={answer}")
        print("")
        turns.append(
            {
                "index": index + 1,
                "lane": probe["lane"],
                "question": probe["question"],
                "expected": probe["expected"],
                "result": result,
                "score": score,
            }
        )
        if args.pause:
            time.sleep(args.pause)

    passed_checks = sum(turn["score"]["passed"] for turn in turns)
    total_checks = sum(turn["score"]["total"] for turn in turns)
    prompt_spills = sum(1 for turn in turns if turn["result"].get("prompt_spill"))
    raw_receipt_spills = sum(1 for turn in turns if turn["result"].get("raw_receipt_spill"))
    mean_score = round(sum(turn["score"]["score"] for turn in turns) / len(turns), 3)
    run = {
        "run_id": run_id,
        "base_url": args.base_url,
        "thread_id": thread_id,
        "backend": args.backend,
        "count": args.count,
        "question_bank_size": len(QUESTION_BANK),
        "summary": {
            "passed_checks": passed_checks,
            "total_checks": total_checks,
            "mean_score": mean_score,
            "prompt_spills": prompt_spills,
            "raw_receipt_spills": raw_receipt_spills,
        },
        "truth_boundary": "Engineering eval and demo trace for measuring context stability, field-expert growth, source discipline, and mission coherence.",
        "turns": turns,
    }
    paths = write_outputs(run)
    save_memory_receipt(run, paths)
    print("Saved:")
    print(f"  JSON: {paths['json']}")
    print(f"  Markdown: {paths['markdown']}")
    print(
        f"Summary: mean_score={mean_score} prompt_spills={prompt_spills} "
        f"raw_receipt_spills={raw_receipt_spills}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
