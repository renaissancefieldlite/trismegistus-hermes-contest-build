#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "coherence_iters"
ITER_SCRIPT = ROOT / "scripts" / "run_coherence_iters.py"


def run_iter(backend: str, count: int, timeout: float) -> dict[str, Any]:
    command = [
        sys.executable,
        str(ITER_SCRIPT),
        "--backend",
        backend,
        "--count",
        str(count),
        "--timeout",
        str(timeout),
        "--pause",
        "0",
    ]
    print(f"\n=== {backend} ===")
    proc = subprocess.run(command, cwd=str(ROOT.parent), text=True, capture_output=True, check=False)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode:
        raise RuntimeError(f"{backend} failed with exit {proc.returncode}")
    json_path = None
    for line in proc.stdout.splitlines():
        if line.strip().startswith("JSON:"):
            json_path = line.split("JSON:", 1)[1].strip()
    if not json_path:
        raise RuntimeError(f"Could not locate JSON path for {backend}")
    return json.loads(Path(json_path).read_text(encoding="utf-8"))


def compare_runs(baseline: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []
    for base_turn, arch_turn in zip(baseline.get("turns", []), architecture.get("turns", []), strict=False):
        base_score = float(base_turn.get("score", {}).get("score") or 0)
        arch_score = float(arch_turn.get("score", {}).get("score") or 0)
        pairs.append(
            {
                "index": base_turn.get("index"),
                "lane": base_turn.get("lane"),
                "question": base_turn.get("question"),
                "baseline_score": base_score,
                "architecture_on_score": arch_score,
                "delta": round(arch_score - base_score, 3),
                "baseline_source": (base_turn.get("result") or {}).get("source"),
                "architecture_source": (arch_turn.get("result") or {}).get("source"),
                "baseline_prompt_spill": bool((base_turn.get("result") or {}).get("prompt_spill")),
                "architecture_prompt_spill": bool((arch_turn.get("result") or {}).get("prompt_spill")),
                "baseline_receipt_spill": bool((base_turn.get("result") or {}).get("raw_receipt_spill")),
                "architecture_receipt_spill": bool((arch_turn.get("result") or {}).get("raw_receipt_spill")),
            }
        )
    deltas = [item["delta"] for item in pairs]
    return {
        "pair_count": len(pairs),
        "baseline_run_id": baseline.get("run_id"),
        "architecture_run_id": architecture.get("run_id"),
        "baseline_mean": baseline.get("summary", {}).get("mean_score"),
        "architecture_on_mean": architecture.get("summary", {}).get("mean_score"),
        "mean_delta": round(statistics.mean(deltas), 3) if deltas else 0.0,
        "baseline_prompt_spills": baseline.get("summary", {}).get("prompt_spills"),
        "architecture_prompt_spills": architecture.get("summary", {}).get("prompt_spills"),
        "baseline_receipt_spills": baseline.get("summary", {}).get("raw_receipt_spills"),
        "architecture_receipt_spills": architecture.get("summary", {}).get("raw_receipt_spills"),
        "pairs": pairs,
    }


def write_outputs(payload: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = payload["id"]
    json_path = OUT_DIR / f"{run_id}.json"
    md_path = OUT_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    comparison = payload["comparison"]
    lines = [
        f"# Tris Baseline vs Architecture-On Benchmark {run_id}",
        "",
        f"- Count: `{comparison['pair_count']}`",
        f"- Baseline mean: `{comparison['baseline_mean']}`",
        f"- Architecture-on mean: `{comparison['architecture_on_mean']}`",
        f"- Mean delta: `{comparison['mean_delta']}`",
        f"- Baseline prompt spills: `{comparison['baseline_prompt_spills']}`",
        f"- Architecture prompt spills: `{comparison['architecture_prompt_spills']}`",
        "",
        "## Boundary",
        "",
        "Respectable small benchmark lane: same questions, baseline Hermes/GFL stack agent versus architecture-on Tris stack agent. This adds to the build evidence and does not replace deeper Golden Mark / C5B / HF checkpoint evaluation.",
        "",
        "## Comparison",
        "",
        "| # | Lane | Baseline | Architecture-On | Delta |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for item in comparison["pairs"]:
        lines.append(
            f"| {item['index']} | {item['lane']} | {item['baseline_score']} | "
            f"{item['architecture_on_score']} | {item['delta']} |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline Hermes vs architecture-on Tris coherence evals.")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    baseline = run_iter("baseline", args.count, args.timeout)
    architecture = run_iter("architecture_on", args.count, args.timeout)
    payload = {
        "id": time.strftime("tris_baseline_compare_%Y%m%dT%H%M%SZ", time.gmtime()),
        "truth_boundary": "Same-prompt benchmark lane comparing baseline Hermes/GFL stack agent to architecture-on Tris stack agent.",
        "baseline": baseline,
        "architecture_on": architecture,
        "comparison": compare_runs(baseline, architecture),
    }
    paths = write_outputs(payload)
    print("\nSaved comparison:")
    print(f"  JSON: {paths['json']}")
    print(f"  Markdown: {paths['markdown']}")
    print(
        "Summary: "
        f"baseline_mean={payload['comparison']['baseline_mean']} "
        f"architecture_on_mean={payload['comparison']['architecture_on_mean']} "
        f"delta={payload['comparison']['mean_delta']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
