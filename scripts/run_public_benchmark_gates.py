#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "benchmark_gates"
TASK_BANK_DIR = ROOT / "data" / "eval_task_banks"
EVAL_RUN_DIR = ROOT / "data" / "eval_runs"


def module_available(name: str) -> dict[str, Any]:
    spec = importlib.util.find_spec(name)
    return {"name": name, "available": bool(spec), "origin": spec.origin if spec else None}


def http_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    started = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
        return {
            "ok": True,
            "url": url,
            "latency_ms": round((time.time() - started) * 1000),
            "body": json.loads(body),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "url": url,
            "latency_ms": round((time.time() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def latest_task_bank() -> dict[str, Any]:
    latest = TASK_BANK_DIR / "golden_mark_udp_six_lane_task_bank_latest.json"
    candidates = sorted(TASK_BANK_DIR.glob("golden_mark_udp_six_lane_task_bank_*.json")) if TASK_BANK_DIR.exists() else []
    path = latest if latest.exists() else (candidates[-1] if candidates else None)
    if not path:
        return {"ok": False, "status": "task_bank_missing", "path": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "task_bank_unreadable", "path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    result = {
        "ok": True,
        "status": "task_bank_ready_unscored",
        "path": str(path),
        "id": payload.get("id"),
        "task_count": payload.get("task_count"),
        "six_lanes": payload.get("six_lanes", []),
    }
    eval_candidates = sorted(EVAL_RUN_DIR.glob("golden_mark_udp_compare_*.json")) if EVAL_RUN_DIR.exists() else []
    if eval_candidates:
        eval_path = eval_candidates[-1]
        try:
            eval_payload = json.loads(eval_path.read_text(encoding="utf-8"))
            comparison = eval_payload.get("comparison") or {}
            result.update(
                {
                    "status": "scored_internal_eval_ready",
                    "latest_eval_path": str(eval_path),
                    "latest_eval_markdown": str(eval_path.with_suffix(".md")),
                    "latest_eval_id": eval_payload.get("id"),
                    "pair_count": comparison.get("pair_count"),
                    "baseline_mean": comparison.get("baseline_mean"),
                    "architecture_on_mean": comparison.get("architecture_on_mean"),
                    "mean_delta": comparison.get("mean_delta"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            result.update(
                {
                    "status": "task_bank_ready_eval_unreadable",
                    "latest_eval_path": str(eval_path),
                    "latest_eval_error": f"{type(exc).__name__}: {exc}",
                }
            )
    return result


def latest_path(pattern: str) -> Path | None:
    candidates = sorted(ROOT.glob(pattern))
    return candidates[-1] if candidates else None


def read_json_file(path: Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def read_text_file_optional(path: Path | None) -> str:
    if not path:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def regex_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def latest_benchmark_receipts() -> dict[str, Any]:
    swe_path = latest_path("data/swebench/codex_helper_missions/codex_helper_unique_ledger_*.md")
    swe_text = read_text_file_optional(swe_path)
    swe_resolved = regex_int(swe_text, r"Unique official local resolved:\s*`?(\d+)")
    swe_total = regex_int(swe_text, r"Dataset total:\s*`?(\d+)")
    swe_missing = regex_int(swe_text, r"Official local missing:\s*`?(\d+)")

    web_path = latest_path("data/benchmark_gates/webarena_verified_hard/tris_hard_official_rollup_*.md")
    web_text = read_text_file_optional(web_path)
    web_success = regex_int(web_text, r"Unique official successes:\s*`?(\d+)")
    web_total = regex_int(web_text, r"Hard tasks total:\s*`?(\d+)")
    web_missing_match = re.search(r"Missing rows:\s*`?([^`\n]+)", web_text, flags=re.IGNORECASE)
    web_missing_rows = []
    if web_missing_match:
        web_missing_rows = [item.strip() for item in web_missing_match.group(1).split(",") if item.strip()]

    gaia_status_path = latest_path("data/gaia/status/gaia_status_*.json")
    gaia_status = read_json_file(gaia_status_path) or {}
    gaia_smoke_path = latest_path("data/gaia/local_source_smoke/gaia_local_source_smoke_*.json")
    gaia_smoke = read_json_file(gaia_smoke_path) or {}
    gaia_summary = gaia_smoke.get("summary") if isinstance(gaia_smoke.get("summary"), dict) else {}

    coherence_runs: dict[int, dict[str, Any]] = {}
    for candidate in sorted(ROOT.glob("data/coherence_iters/tris_coherence_iter_*.json")):
        payload = read_json_file(candidate)
        if not payload or payload.get("backend") != "architecture_on":
            continue
        count = payload.get("count")
        if isinstance(count, int) and count in {100, 500}:
            coherence_runs[count] = {
                "path": str(candidate),
                "markdown": str(candidate.with_suffix(".md")),
                "summary": payload.get("summary") if isinstance(payload.get("summary"), dict) else {},
            }

    coherence_500 = coherence_runs.get(500)
    coherence_100 = coherence_runs.get(100)
    coherence_summary = None
    if coherence_500:
        summary = coherence_500.get("summary") or {}
        coherence_summary = (
            f"500-turn architecture-on coherence: mean {summary.get('mean_score')}, "
            f"{summary.get('passed_checks')}/{summary.get('total_checks')} checks, "
            f"{summary.get('prompt_spills')} prompt spills, "
            f"{summary.get('raw_receipt_spills')} raw receipt spills"
        )

    return {
        "swe_bench_verified": {
            "path": str(swe_path) if swe_path else None,
            "resolved": swe_resolved,
            "total": swe_total,
            "missing": swe_missing,
            "score_summary": (
                f"{swe_resolved}/{swe_total} official local selected-test resolves"
                if swe_resolved is not None and swe_total is not None
                else None
            ),
            "boundary": "Internal Codex-helper source-backed ledger; not a blind hosted leaderboard submission.",
        },
        "webarena_verified_hard": {
            "path": str(web_path) if web_path else None,
            "success": web_success,
            "total": web_total,
            "missing_rows": web_missing_rows,
            "score_summary": (
                f"{web_success}/{web_total} official WebArena-Verified hard successes"
                if web_success is not None and web_total is not None
                else None
            ),
            "boundary": "Official local/self-hosted hard-task receipts; remaining rows are map-fixture/dataset blockers unless rerun against reachable expected URLs.",
        },
        "gaia": {
            "status_path": str(gaia_status_path) if gaia_status_path else None,
            "smoke_path": str(gaia_smoke_path) if gaia_smoke_path else None,
            "status": gaia_status.get("status"),
            "tris_api_ok": ((gaia_status.get("runtime") or {}).get("tris_api") or {}).get("ok"),
            "baseline_bridge_ok": ((gaia_status.get("runtime") or {}).get("baseline_bridge") or {}).get("ok"),
            "exact_matches": gaia_summary.get("exact_matches"),
            "scored_rows": gaia_summary.get("scored_rows"),
            "score_summary": (
                f"{gaia_summary.get('exact_matches')}/{gaia_summary.get('scored_rows')} local source-backed smoke exact"
                if gaia_summary.get("exact_matches") is not None and gaia_summary.get("scored_rows") is not None
                else None
            ),
            "boundary": "Local source-backed GAIA-style smoke only; no official GAIA score until Hugging Face/private GAIA access opens.",
        },
        "coherence_iters": {
            "latest_100": coherence_100,
            "latest_500": coherence_500,
            "score_summary": coherence_summary,
            "boundary": "Architecture-on local coherence harness over the Tris 12-question probe bank repeated to scale; supports conversational stability, not a public benchmark replacement.",
        },
    }


def check_hf_dataset(dataset: str, config: str | None = None, split: str = "test") -> dict[str, Any]:
    available = module_available("datasets")
    result: dict[str, Any] = {
        "dataset": dataset,
        "requested_config": config,
        "requested_split": split,
        "datasets_package": available,
    }
    if not available["available"]:
        result.update({"ok": False, "status": "datasets_package_missing"})
        return result
    try:
        from datasets import get_dataset_config_names, get_dataset_split_names, load_dataset

        configs = get_dataset_config_names(dataset)
        chosen_config = config or (configs[0] if configs else "default")
        splits = get_dataset_split_names(dataset, chosen_config)
        chosen_split = split if split in splits else (splits[0] if splits else split)
        preview_split = f"{chosen_split}[:1]"
        preview = load_dataset(dataset, chosen_config, split=preview_split)
        row = preview[0] if len(preview) else {}
        result.update(
            {
                "ok": True,
                "status": "dataset_accessible",
                "configs": configs[:20],
                "config_count": len(configs),
                "chosen_config": chosen_config,
                "splits": splits,
                "chosen_split": chosen_split,
                "preview_columns": list(row.keys()),
                "preview_row_keys": list(row.keys()),
            }
        )
    except Exception as exc:  # noqa: BLE001
        result.update(
            {
                "ok": False,
                "status": "dataset_blocked_or_unavailable",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
    return result


def gate_status(checks: dict[str, Any]) -> list[dict[str, Any]]:
    modules = {item["name"]: item for item in checks["modules"]}
    swe = checks["datasets"]["swe_bench_verified"]
    gaia = checks["datasets"]["gaia"]
    tris = checks["local_routes"]["tris_status"]
    gfl = checks["local_routes"]["gfl_health"]
    task_bank = checks["task_banks"]["golden_mark_udp"]
    receipts = checks.get("bench_receipts", {})
    swe_receipt = receipts.get("swe_bench_verified", {})
    web_receipt = receipts.get("webarena_verified_hard", {})
    gaia_receipt = receipts.get("gaia", {})
    coherence_receipt = receipts.get("coherence_iters", {})
    web_modules_ready = all(
        modules[name]["available"] for name in ("playwright", "gymnasium", "browsergym")
    )
    browser_vendor_ready = bool(checks["vendor_repos"]["webarena"]["present"] and checks["vendor_repos"]["browsergym"]["present"])
    cdp_possible = bool(checks["browser_stack"]["chrome_binary"])
    webarena_sites_ready = bool(checks["browser_stack"]["webarena_sites"]["all_env_set"])
    if web_modules_ready and webarena_sites_ready:
        webarena_status = "browser_harness_and_self_hosted_sites_ready"
    elif web_modules_ready:
        webarena_status = "browser_runtime_ready_self_hosted_sites_pending"
    elif browser_vendor_ready:
        webarena_status = "vendor_staged_runtime_missing"
    else:
        webarena_status = "browser_agent_harness_missing"
    gates = [
        {
            "id": "swe_bench_verified",
            "name": "SWE-bench Verified",
            "status": (
                "official_local_selected_test_receipt_ready"
                if swe_receipt.get("score_summary")
                else "dataset_ready_harness_missing"
                if swe.get("ok") and not modules["swebench"]["available"]
                else "ready_or_needs_attention"
            ),
            "ready_for_public_score": bool(swe_receipt.get("score_summary")),
            "score_summary": swe_receipt.get("score_summary"),
            "current_receipt": swe_receipt or ("dataset accessible" if swe.get("ok") else swe.get("error")),
            "next_gate": (
                "Run hosted/blind-compatible submission packaging if the contest needs a leaderboard-style artifact; keep the local official selected-test boundary in public copy."
                if swe_receipt.get("score_summary")
                else "Run the official SWE-bench evaluator on the same baseline and architecture-on prediction slice."
                if swe.get("ok") and modules["swebench"]["available"]
                else "Install/stage the official SWE-bench harness, then run baseline and architecture-on on the same issue slice."
            ),
        },
        {
            "id": "gaia",
            "name": "GAIA",
            "status": "dataset_ready" if gaia.get("ok") else "blocked_hf_access_or_dataset_gate",
            "ready_for_public_score": bool(gaia.get("ok")),
            "score_summary": gaia_receipt.get("score_summary"),
            "current_receipt": gaia_receipt or ("dataset accessible" if gaia.get("ok") else gaia.get("error")),
            "next_gate": "Confirm Hugging Face access/token for GAIA, then run baseline and architecture-on on the same validation slice.",
        },
        {
            "id": "webarena",
            "name": "WebArena",
            "status": "official_verified_hard_receipt_ready" if web_receipt.get("score_summary") else webarena_status,
            "ready_for_public_score": bool(web_receipt.get("score_summary")),
            "score_summary": web_receipt.get("score_summary"),
            "current_receipt": {
                "score_receipt": web_receipt,
                "playwright": modules["playwright"]["available"],
                "gymnasium": modules["gymnasium"]["available"],
                "browsergym": modules["browsergym"]["available"],
                "webarena_vendor": checks["vendor_repos"]["webarena"],
                "browsergym_vendor": checks["vendor_repos"]["browsergym"],
                "chrome_cdp_possible": cdp_possible,
                "webarena_sites": checks["browser_stack"]["webarena_sites"],
                "firecrawl": checks["browser_stack"]["firecrawl"],
            },
            "next_gate": (
                "Repair the map fixture and rerun rows 425, 429, and 430 against reachable expected URLs, or package the 255/258 receipt with the map-fixture boundary."
                if web_receipt.get("score_summary")
                else "Bring up official self-hosted WebArena domains/containers, then run bounded WebArena tasks with saved action traces."
            ),
        },
        {
            "id": "tris_internal_coherence",
            "name": "Tris 100/500 coherence iterations",
            "status": "500_turn_architecture_on_receipt_ready" if coherence_receipt.get("score_summary") else "ready" if tris.get("ok") else "tris_server_not_confirmed",
            "ready_for_public_score": False,
            "score_summary": coherence_receipt.get("score_summary"),
            "current_receipt": coherence_receipt or ("Tris API responding" if tris.get("ok") else tris.get("error")),
            "next_gate": (
                "Keep as architecture-on coherence evidence; next upgrade is a broader source/task bank with less deterministic repetition."
                if coherence_receipt.get("score_summary")
                else "Run 100 turns, patch failures, then scale to 500. This supports long-session coherence, not public benchmark replacement."
            ),
        },
        {
            "id": "ani15d_lattice_companion",
            "name": "ANI15D / lattice companion custom eval",
            "status": task_bank["status"],
            "ready_for_public_score": False,
            "current_receipt": task_bank if task_bank.get("ok") else "custom eval spine defined in docs; task bank not yet generated",
            "next_gate": (
                "Use the latest scored internal eval as the architecture-on receipt, then run visible WebArena-style browser tasks before official benchmark claims."
                if task_bank.get("status") == "scored_internal_eval_ready"
                else "Run baseline and architecture-on on the same six-lane task-bank slice, then scale to 100/500."
                if task_bank.get("ok")
                else "Build the cross-field pattern task bank across the six discipline partner lanes: AI partner/expert architecture, quantum computing/circuits and mathematics, structured matter/physical systems, life sciences/medical research, Mirror Architecture/Golden Mark evidence, and relationship/paid-work field operations."
            ),
        },
        {
            "id": "baseline_runtime",
            "name": "Baseline untuned model route",
            "status": "ready" if gfl.get("ok") else "baseline_route_not_confirmed",
            "ready_for_public_score": bool(gfl.get("ok")),
            "current_receipt": "GFL/Hermes route responding" if gfl.get("ok") else gfl.get("error"),
            "next_gate": "Use this as the no-Tris-router baseline whenever comparing against architecture-on Tris.",
        },
    ]
    return gates


def write_outputs(payload: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gate_id = payload["id"]
    json_path = OUT_DIR / f"{gate_id}.json"
    md_path = OUT_DIR / f"{gate_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        f"# Tris Public Benchmark Gate {gate_id}",
        "",
        f"- Generated: `{payload['generated_at']}`",
        "- Purpose: prepare baseline untuned model versus architecture-on Tris for public benchmarks and Tris-native evals.",
        "",
        "## Gate Status",
        "",
        "| Gate | Status | Score / Receipt | Public Score Ready | Next Gate |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for gate in payload["gates"]:
        score_summary = gate.get("score_summary") or "receipt pending"
        lines.append(
            f"| {gate['name']} | `{gate['status']}` | {score_summary} | `{gate['ready_for_public_score']}` | {gate['next_gate']} |"
        )
    lines.extend(
        [
            "",
            "## Benchmark Order",
            "",
            "1. Run baseline untuned model route.",
            "2. Run architecture-on Tris route.",
            "3. Use the same task slice, same budget accounting, and saved receipts.",
            "4. Compare task success, cost per task, source accuracy, long-session coherence, and repair quality.",
            "5. Feed coding benchmark receipts into the future paid-work/coding-gig scouting lane.",
            "",
            "## Commands",
            "",
            "```bash",
            ".venv-browser/bin/python scripts/run_public_benchmark_gates.py",
            ".venv-browser/bin/python scripts/browser_cdp_smoke.py --url http://127.0.0.1:8898/",
            "python3 scripts/run_coherence_iters.py --backend baseline --count 100 --timeout 180",
            "python3 scripts/run_coherence_iters.py --backend architecture_on --count 100 --timeout 180",
            "python3 scripts/run_benchmark_compare.py --count 12 --timeout 180",
            "```",
            "",
            "## Boundary",
            "",
            "This receipt checks readiness and reads local benchmark receipts. SWE-bench is an official-local selected-test ledger, WebArena is an official local/self-hosted hard-task receipt, and GAIA remains a local source-backed smoke until Hugging Face/private GAIA access opens. Do not present any row as a blind hosted leaderboard submission unless a separate hosted submission receipt exists.",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def main() -> int:
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    modules = [
        module_available(name)
        for name in ("datasets", "requests", "swebench", "playwright", "gymnasium", "browsergym")
    ]
    checks = {
        "modules": modules,
        "environment": {
            "hf_token_present": bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")),
            "python": sys.version.split()[0],
        },
        "datasets": {
            "swe_bench_verified": check_hf_dataset("SWE-bench/SWE-bench_Verified", "default", "test"),
            "gaia": check_hf_dataset("gaia-benchmark/GAIA", None, "validation"),
        },
        "local_routes": {
            "tris_status": http_json("http://127.0.0.1:8898/api/status"),
            "gfl_health": http_json("http://127.0.0.1:8788/health"),
        },
        "task_banks": {
            "golden_mark_udp": latest_task_bank(),
        },
        "bench_receipts": latest_benchmark_receipts(),
        "vendor_repos": {
            "webarena": {
                "present": (ROOT / "vendor" / "webarena" / ".git").exists(),
                "path": str(ROOT / "vendor" / "webarena"),
            },
            "browsergym": {
                "present": (ROOT / "vendor" / "BrowserGym" / ".git").exists(),
                "path": str(ROOT / "vendor" / "BrowserGym"),
            },
        },
        "browser_stack": {
            "decision": "Combined stack: Playwright action, CDP host-browser attachment, Firecrawl source/RAG sidecar, BrowserGym/WebArena tasks, Tris receipt memory.",
            "chrome_binary": next(
                (
                    path
                    for path in (
                        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                        "/Applications/Chromium.app/Contents/MacOS/Chromium",
                        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                    )
                    if Path(path).exists()
                ),
                None,
            ),
            "cdp_port": 9222,
            "firecrawl": {
                "api_url": os.environ.get("FIRECRAWL_API_URL", "http://localhost:3002"),
                "api_key_present": bool(os.environ.get("FIRECRAWL_API_KEY")),
                "role": "fast source/RAG ingestion sidecar",
            },
            "webarena_sites": {
                "required_env": [
                    "WA_SHOPPING",
                    "WA_SHOPPING_ADMIN",
                    "WA_REDDIT",
                    "WA_GITLAB",
                    "WA_WIKIPEDIA",
                    "WA_MAP",
                    "WA_HOMEPAGE",
                ],
                "set_env": [
                    name
                    for name in (
                        "WA_SHOPPING",
                        "WA_SHOPPING_ADMIN",
                        "WA_REDDIT",
                        "WA_GITLAB",
                        "WA_WIKIPEDIA",
                        "WA_MAP",
                        "WA_HOMEPAGE",
                    )
                    if os.environ.get(name)
                ],
                "all_env_set": all(
                    os.environ.get(name)
                    for name in (
                        "WA_SHOPPING",
                        "WA_SHOPPING_ADMIN",
                        "WA_REDDIT",
                        "WA_GITLAB",
                        "WA_WIKIPEDIA",
                        "WA_MAP",
                        "WA_HOMEPAGE",
                    )
                ),
            },
        },
    }
    payload = {
        "id": time.strftime("tris_public_benchmark_gate_%Y%m%dT%H%M%SZ", time.gmtime()),
        "generated_at": generated_at,
        "objective": "Baseline untuned model versus architecture-on Tris across public benchmarks, long-session coherence, cost, and custom ANI15D/lattice field cognition.",
        "checks": checks,
        "gates": gate_status(checks),
        "primary_public_benchmarks": ["SWE-bench Verified", "GAIA", "WebArena"],
        "tris_native_benchmarks": [
            "100/500 turn coherence iterations",
            "Golden Mark / C5B / SSP architecture-on comparison",
            "ANI15D / lattice companion cross-field pattern recognition",
        ],
    }
    paths = write_outputs(payload)
    print("Tris public benchmark gate")
    print(f"JSON: {paths['json']}")
    print(f"Markdown: {paths['markdown']}")
    for gate in payload["gates"]:
        print(f"- {gate['name']}: {gate['status']} / public_ready={gate['ready_for_public_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
