#!/usr/bin/env python3
"""Run one WebArena task with WebArena-Verified task text.

The upstream `vendor/webarena/run.py` hardcodes `config_files/{task_id}.json`.
This wrapper temporarily overlays that one JSON with the WebArena-Verified
intent/start URL, runs the benchmark, and restores the original file.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PLACEHOLDERS = {
    "__REDDIT__": "REDDIT",
    "__SHOPPING__": "SHOPPING",
    "__SHOPPING_ADMIN__": "SHOPPING_ADMIN",
    "__GITLAB__": "GITLAB",
    "__WIKIPEDIA__": "WIKIPEDIA",
    "__MAP__": "MAP",
    "__HOMEPAGE__": "HOMEPAGE",
}


def load_verified_task(metadata_path: Path, task_id: int) -> dict:
    tasks = json.loads(metadata_path.read_text())
    if isinstance(tasks, dict):
        tasks = tasks.get("tasks") or tasks.get("data") or []
    for task in tasks:
        if int(task.get("task_id", -1)) == task_id:
            return task
    raise ValueError(f"task {task_id} not found in {metadata_path}")


def resolve_url(url: str) -> str:
    resolved = url
    for placeholder, env_name in PLACEHOLDERS.items():
        if placeholder in resolved:
            value = os.environ.get(env_name)
            if not value:
                raise EnvironmentError(f"{env_name} is required for {placeholder}")
            resolved = resolved.replace(placeholder, value)
    return resolved


def build_override(original: dict, verified: dict) -> dict:
    override = dict(original)
    start_urls = verified.get("start_urls") or [original.get("start_url", "")]
    override["intent"] = verified["intent"]
    override["start_url"] = " |AND| ".join(resolve_url(url) for url in start_urls)
    override["sites"] = verified.get("sites", original.get("sites"))
    override["task_id"] = verified.get("task_id", original.get("task_id"))
    override["webarena_verified_revision"] = verified.get("revision")
    override["webarena_verified_intent_template_id"] = verified.get(
        "intent_template_id"
    )
    return override


def webarena_python(root: Path) -> str:
    configured = os.environ.get("WEB_ARENA_PYTHON")
    if configured:
        return configured
    venv_python = root / ".venv-browser" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True, type=int)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--result-dir", required=True, type=Path)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("--max-steps", default=14, type=int)
    parser.add_argument("--max-tokens", default=180, type=int)
    parser.add_argument("--max-obs-length", default=1920, type=int)
    args = parser.parse_args()

    root = args.root.resolve()
    vendor = root / "vendor" / "webarena"
    config_path = vendor / "config_files" / f"{args.task_id}.json"
    if not config_path.exists():
        raise FileNotFoundError(config_path)

    verified = load_verified_task(args.metadata, args.task_id)
    original_text = config_path.read_text()
    original = json.loads(original_text)
    override = build_override(original, verified)
    args.result_dir.mkdir(parents=True, exist_ok=True)
    (args.result_dir / f"verified_override_{args.task_id}.json").write_text(
        json.dumps(override, indent=2) + "\n"
    )

    config_path.write_text(json.dumps(override, indent=2) + "\n")
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["WEB_ARENA_VERIFIED_METADATA"] = str(args.metadata.resolve())
    env["WEB_ARENA_VERIFIED_TASK_ID"] = str(args.task_id)
    env.setdefault("TRIS_LOCAL_GENERATE_URL", "http://127.0.0.1:8788/api/generate")
    cmd = [
        webarena_python(root),
        "run.py",
        "--instruction_path",
        "agent/prompts/jsons/p_direct_id_actree_2s_tris.json",
        "--test_start_idx",
        str(args.task_id),
        "--test_end_idx",
        str(args.task_id + 1),
        "--provider",
        "trislocal",
        "--model",
        "tris-hermes-local",
        "--mode",
        "completion",
        "--temperature",
        "0.0",
        "--top_p",
        "1.0",
        "--max_tokens",
        str(args.max_tokens),
        "--max_retry",
        "2",
        "--max_obs_length",
        str(args.max_obs_length),
        "--model_endpoint",
        "http://127.0.0.1:8788/api/generate",
        "--max_steps",
        str(args.max_steps),
        "--sleep_after_execution",
        "2",
        "--save_trace_enabled",
        "--current_viewport_only",
        "--result_dir",
        str(args.result_dir),
    ]
    try:
        print("verified_intent:", verified["intent"])
        print("override_config:", args.result_dir / f"verified_override_{args.task_id}.json")
        subprocess.run(cmd, cwd=vendor, env=env, check=True)
    finally:
        config_path.write_text(original_text)


if __name__ == "__main__":
    main()
