from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

from . import db


ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv-browser" / "bin" / "python"
OUT_DIR = ROOT / "data" / "browser_autonomy"
BENCHMARK_DIR = ROOT / "data" / "benchmark_gates"
LOG_DIR = ROOT / "logs" / "browser_autonomy"
WEB_ARENA_HOME = ROOT / "vendor" / "webarena" / "environment_docker" / "webarena-homepage"
WEB_ARENA_APP = WEB_ARENA_HOME / "app.py"
WEB_ARENA_URL = "http://127.0.0.1:4399/"
PID_FILE = OUT_DIR / "webarena_homepage_subset.pid"


def _now_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _http_probe(url: str, timeout: float = 2.5) -> dict[str, Any]:
    started = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(300).decode("utf-8", errors="replace")
        return {
            "ok": True,
            "url": url,
            "status": getattr(response, "status", 200),
            "latency_ms": round((time.time() - started) * 1000),
            "body_preview": " ".join(body.split())[:180],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "url": url,
            "latency_ms": round((time.time() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _latest(pattern: str, folder: Path) -> str:
    if not folder.exists():
        return ""
    files = sorted(folder.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return str(files[0]) if files else ""


def _parse_paths(stdout: str) -> dict[str, str]:
    paths: dict[str, str] = {}
    labels = {
        "json": r"^JSON:\s*(.+)$",
        "markdown": r"^Markdown:\s*(.+)$",
        "trace": r"^Trace:\s*(.+)$",
        "screenshot": r"^Screenshot:\s*(.+)$",
        "screenshot_dir": r"^Screenshot dir:\s*(.+)$",
    }
    for key, pattern in labels.items():
        match = re.search(pattern, stdout, flags=re.MULTILINE)
        if match:
            paths[key] = match.group(1).strip()
    return paths


def _stdout_value(stdout: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", stdout, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _stdout_bool(stdout: str, label: str) -> bool | None:
    value = _stdout_value(stdout, label).lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    return None


def _stdout_loaded(stdout: str) -> tuple[int, int] | None:
    value = _stdout_value(stdout, "Loaded")
    match = re.match(r"^(\d+)\s*/\s*(\d+)$", value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _load_json_payload(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _run_python_script(args: list[str], timeout: float = 180.0) -> dict[str, Any]:
    if not VENV_PYTHON.exists():
        return {"ok": False, "error": f"Browser venv missing: {VENV_PYTHON}"}
    started = time.time()
    proc = subprocess.run(
        [str(VENV_PYTHON), *args],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    paths = _parse_paths(proc.stdout)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "latency_ms": round((time.time() - started) * 1000),
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "paths": paths,
    }


def browser_mission_status() -> dict[str, Any]:
    subset = _http_probe(WEB_ARENA_URL, timeout=1.25)
    latest_action_json = _latest("tris_browser_action_trace_*.json", OUT_DIR)
    latest_action_md = _latest("tris_browser_action_trace_*.md", OUT_DIR)
    latest_trace = _latest("tris_browser_action_trace_*.zip", OUT_DIR)
    latest_live_json = _latest("tris_live_site_sequence_*.json", OUT_DIR)
    latest_live_md = _latest("tris_live_site_sequence_*.md", OUT_DIR)
    latest_live_trace = _latest("tris_live_site_sequence_*.zip", OUT_DIR)
    latest_smoke_md = _latest("tris_browser_cdp_smoke_*.md", OUT_DIR)
    latest_benchmark_md = _latest("tris_public_benchmark_gate_*.md", BENCHMARK_DIR)
    return {
        "ok": bool(VENV_PYTHON.exists() and WEB_ARENA_APP.exists()),
        "venv_python": str(VENV_PYTHON),
        "webarena_homepage_app": str(WEB_ARENA_APP),
        "webarena_subset": subset,
        "latest": {
            "browser_smoke_markdown": latest_smoke_md,
            "benchmark_gate_markdown": latest_benchmark_md,
            "action_trace_json": latest_action_json,
            "action_trace_markdown": latest_action_md,
            "action_trace_zip": latest_trace,
            "live_sequence_json": latest_live_json,
            "live_sequence_markdown": latest_live_md,
            "live_sequence_zip": latest_live_trace,
        },
        "stack": {
            "playwright": "primary browser-control worker",
            "cdp": "host-browser attachment bridge",
            "firecrawl": "fast RAG/source ingestion sidecar after core trace is stable",
            "webarena": "official benchmark harness; bounded homepage subset active first",
            "edge": "planner/executor split, page-state verification, action trace, workflow replay memory",
        },
        "next_gate": "Run WebArena subset, then browser action trace, then graduate to full WebArena domain containers for public task scoring.",
    }


def start_webarena_subset() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    existing = _http_probe(WEB_ARENA_URL, timeout=1.25)
    if existing.get("ok"):
        result = {
            "ok": True,
            "source": "webarena-official-homepage-subset",
            "url": WEB_ARENA_URL,
            "already_running": True,
            "probe": existing,
        }
        db.log_event("browser_mission_webarena_subset", result)
        return result
    if not VENV_PYTHON.exists():
        raise RuntimeError(f"Browser venv missing: {VENV_PYTHON}")
    if not WEB_ARENA_APP.exists():
        raise RuntimeError(f"WebArena homepage app missing: {WEB_ARENA_APP}")

    stamp = _now_id()
    log_path = LOG_DIR / f"webarena_homepage_subset_{stamp}.log"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    with log_path.open("ab") as log_file:
        process = subprocess.Popen(
            [str(VENV_PYTHON), str(WEB_ARENA_APP)],
            cwd=str(WEB_ARENA_HOME),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")

    probe = {"ok": False, "error": "not probed"}
    for _ in range(24):
        time.sleep(0.5)
        probe = _http_probe(WEB_ARENA_URL, timeout=1.25)
        if probe.get("ok"):
            break

    receipt = {
        "id": f"webarena_homepage_subset_{stamp}",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": bool(probe.get("ok")),
        "source": "webarena-official-homepage-subset",
        "url": WEB_ARENA_URL,
        "pid": process.pid,
        "pid_file": str(PID_FILE),
        "log": str(log_path),
        "probe": probe,
        "boundary": "Official WebArena homepage/calculator subset only. Full WebArena task scoring needs the heavier domain containers.",
    }
    json_path = OUT_DIR / f"{receipt['id']}.json"
    md_path = OUT_DIR / f"{receipt['id']}.md"
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# WebArena Homepage Subset {receipt['id']}",
                "",
                f"- URL: `{WEB_ARENA_URL}`",
                f"- PID: `{process.pid}`",
                f"- Log: `{log_path}`",
                f"- Probe OK: `{probe.get('ok')}`",
                "",
                "## Read",
                "",
                "This starts the official WebArena homepage service from the local vendor repo. It is the bounded first slice for Tris browser missions.",
                "",
                "## Boundary",
                "",
                str(receipt["boundary"]),
            ]
        ),
        encoding="utf-8",
    )
    receipt["paths"] = {"json": str(json_path), "markdown": str(md_path)}
    db.log_event("browser_mission_webarena_subset", receipt)
    db.save_memory_item(
        "browser_mission_receipt",
        receipt["id"],
        "WebArena homepage subset started",
        f"Official WebArena homepage subset at {WEB_ARENA_URL}. Probe OK: {probe.get('ok')}.",
        receipt,
    )
    return receipt


def run_browser_cdp_smoke(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    url = str(body.get("url") or "http://127.0.0.1:8898/")
    result = _run_python_script(["scripts/browser_cdp_smoke.py", "--url", url], timeout=90)
    result["source"] = "tris-browser-cdp-smoke"
    db.log_event("browser_mission_cdp_smoke", result)
    return result


def run_public_benchmark_gate() -> dict[str, Any]:
    result = _run_python_script(["scripts/run_public_benchmark_gates.py"], timeout=300)
    result["source"] = "tris-public-benchmark-gate"
    db.log_event("browser_mission_benchmark_gate", result)
    return result


def run_browser_action_trace(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    subset = start_webarena_subset()
    url = str(body.get("url") or WEB_ARENA_URL)
    expression = str(body.get("expression") or "67+5")
    result = _run_python_script(
        ["scripts/browser_action_trace.py", "--url", url, "--expression", expression],
        timeout=120,
    )
    result["source"] = "tris-browser-action-trace"
    result["webarena_subset"] = subset
    db.log_event("browser_mission_action_trace", result)
    return result


def run_live_site_sequence(body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    args = ["scripts/browser_live_site_sequence.py"]
    targets_json = str(body.get("targets_json") or "").strip()
    if targets_json:
        args.extend(["--targets-json", targets_json])
    result = _run_python_script(args, timeout=300)
    script_ok = _stdout_bool(str(result.get("stdout") or ""), "OK")
    loaded = _stdout_loaded(str(result.get("stdout") or ""))
    if script_ok is not None:
        result["ok"] = script_ok
        result["sequence_ok"] = script_ok
    if loaded:
        ok_count, target_count = loaded
        result["loaded"] = f"{ok_count}/{target_count}"
        result["partial_ok"] = ok_count > 0 and ok_count < target_count
        result["target_count"] = target_count
        result["ok_count"] = ok_count
    receipt_payload = _load_json_payload((result.get("paths") or {}).get("json"))
    if receipt_payload:
        for key in (
            "results",
            "objective_ok",
            "objective_ok_count",
            "target_count",
            "ok_count",
            "read",
            "boundary",
            "next_gate",
            "webarena_baseline_map",
        ):
            if key in receipt_payload:
                result[key] = receipt_payload[key]
    result["source"] = "tris-live-site-sequence"
    db.log_event("browser_mission_live_site_sequence", result)
    if result.get("ok"):
        db.save_memory_item(
            "browser_mission_receipt",
            "latest-live-site-sequence",
            "Tris live source navigation sequence",
            "Playwright/CDP visited NVIDIA quantum partner candidates, Nous careers, and the RFL public surface with saved trace receipts.",
            result,
        )
    return result
