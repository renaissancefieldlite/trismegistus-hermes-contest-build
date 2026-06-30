#!/usr/bin/env python3
"""Run a small WebArena-Verified slice through the Tris browser route.

This is a receipt harness, not a scorer shortcut. For every task it:

1. overlays the WebArena-Verified task text into the upstream WebArena config,
2. runs the browser trace through the configured Tris local route,
3. mechanically adapts the final stop action into WebArena-Verified format,
4. invokes the official `webarena-verified` evaluator, and
5. writes a slice summary with exact artifact paths.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED_ENDPOINTS = (
    "SHOPPING",
    "SHOPPING_ADMIN",
    "REDDIT",
    "GITLAB",
    "MAP",
    "WIKIPEDIA",
    "HOMEPAGE",
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, env=env, text=True)


def load_eval_result(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def webarena_python(root: Path) -> str:
    configured = os.environ.get("WEB_ARENA_PYTHON")
    if configured:
        return configured
    venv_python = root / ".venv-browser" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-ids", nargs="+", type=int, required=True)
    parser.add_argument("--label", default="slice")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path(
            "data/benchmark_gates/webarena_verified_hard/"
            "webarena-verified-hard.exported-tasks.json"
        ),
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--max-steps", type=int, default=14)
    parser.add_argument("--max-tokens", type=int, default=180)
    parser.add_argument("--max-obs-length", type=int, default=1920)
    args = parser.parse_args()

    root = args.root.resolve()
    metadata = (root / args.metadata).resolve() if not args.metadata.is_absolute() else args.metadata
    if not metadata.exists():
        raise FileNotFoundError(metadata)

    missing = [name for name in REQUIRED_ENDPOINTS if not os.environ.get(name)]
    if missing:
        raise EnvironmentError(f"missing WebArena endpoint env vars: {', '.join(missing)}")

    stamp = utc_stamp()
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in args.label)
    slice_dir = root / "data" / "benchmark_gates" / "webarena_verified_hard" / f"{safe_label}_{stamp}"
    runs_dir = root / "data" / "eval_runs" / f"webarena_verified_{safe_label}_{stamp}"
    slice_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PATH"] = f"{root / '.venv-browser' / 'bin'}:{env.get('PATH', '')}"
    env.setdefault("TRIS_LOCAL_GENERATE_URL", "http://127.0.0.1:8788/api/generate")

    rows: list[dict] = []
    for task_id in args.task_ids:
        task_run_dir = runs_dir / str(task_id)
        task_out_dir = slice_dir / str(task_id)
        task_run_dir.mkdir(parents=True, exist_ok=True)
        row = {
            "task_id": task_id,
            "run_dir": str(task_run_dir),
            "verified_output_dir": str(task_out_dir),
            "run_status": "not_started",
            "adapter_status": "not_started",
            "eval_status": "not_started",
            "score": None,
            "error": None,
        }
        rows.append(row)

        run_cmd = [
            webarena_python(root),
            "scripts/run_webarena_verified_task.py",
            "--task-id",
            str(task_id),
            "--metadata",
            str(metadata),
            "--result-dir",
            str(task_run_dir),
            "--root",
            str(root),
            "--max-steps",
            str(args.max_steps),
            "--max-tokens",
            str(args.max_tokens),
            "--max-obs-length",
            str(args.max_obs_length),
        ]
        proc = run(run_cmd, cwd=root, env=env)
        row["run_returncode"] = proc.returncode
        row["run_status"] = "ok" if proc.returncode == 0 else "failed"
        if proc.returncode != 0:
            row["error"] = "webarena run failed"
            continue

        adapter_cmd = [
            sys.executable,
            "scripts/webarena_verified_adapter_from_run.py",
            "--run-dir",
            str(task_run_dir),
            "--task-id",
            str(task_id),
            "--out-dir",
            str(slice_dir),
            "--task-metadata",
            str(metadata),
        ]
        proc = run(adapter_cmd, cwd=root, env=env)
        row["adapter_returncode"] = proc.returncode
        row["adapter_status"] = "ok" if proc.returncode == 0 else "failed"
        if proc.returncode != 0:
            row["error"] = "adapter failed"
            continue

        eval_cmd = [
            "webarena-verified",
            "eval-tasks",
            "--output-dir",
            str(slice_dir),
            "--task-ids",
            str(task_id),
        ]
        proc = run(eval_cmd, cwd=root, env=env)
        row["eval_returncode"] = proc.returncode
        result = load_eval_result(task_out_dir / "eval_result.json")
        if result:
            row["eval_status"] = result.get("status")
            row["score"] = result.get("score")
            row["eval_result_path"] = str(task_out_dir / "eval_result.json")
        else:
            row["eval_status"] = "missing_result"
            row["error"] = "missing eval_result.json"

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "label": safe_label,
        "task_ids": args.task_ids,
        "slice_dir": str(slice_dir),
        "runs_dir": str(runs_dir),
        "metadata": str(metadata),
        "rows": rows,
        "success_count": sum(1 for row in rows if row.get("score") == 1.0),
        "failure_count": sum(
            1
            for row in rows
            if row.get("eval_status") not in {"not_started", "success"} or row.get("score") != 1.0
        ),
    }
    (slice_dir / "SLICE_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    (slice_dir / "SLICE_RECEIPT.md").write_text(
        "# WebArena-Verified slice receipt\n\n"
        f"- label: `{safe_label}`\n"
        f"- task_ids: `{args.task_ids}`\n"
        f"- runs_dir: `{runs_dir}`\n"
        f"- slice_dir: `{slice_dir}`\n"
        f"- success_count: `{summary['success_count']}`\n"
        f"- failure_count: `{summary['failure_count']}`\n"
        "- boundary: official `webarena-verified` eval receipts only; no public "
        "leaderboard claim.\n"
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
