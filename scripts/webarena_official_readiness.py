#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "webarena"
OUT_DIR = ROOT / "data" / "benchmark_gates"


DOMAINS = {
    "SHOPPING": ("shopping", "7770", ""),
    "SHOPPING_ADMIN": ("shopping_admin", "7780", "/admin"),
    "REDDIT": ("reddit", "9999", ""),
    "GITLAB": ("gitlab", "8023", ""),
    "WIKIPEDIA": (
        "wikipedia",
        "8888",
        "/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing",
    ),
    "MAP": ("map", "3000", ""),
    "HOMEPAGE": ("homepage", "4399", ""),
}

EXPECTED_AUTH = [
    "gitlab_state.json",
    "reddit_state.json",
    "shopping_state.json",
    "shopping_admin_state.json",
]


def _domain_url(name: str, host: str) -> str:
    _, port, path = DOMAINS[name]
    env = os.environ.get(name, "").strip()
    return env or f"http://{host}:{port}{path}"


def _wa_url(name: str) -> str:
    browsergym_key = f"WA_{name}"
    return os.environ.get(browsergym_key, "").strip()


def _http_check(url: str, timeout: float) -> dict[str, Any]:
    started = time.time()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read(512).decode("utf-8", errors="replace")
            return {
                "ok": 200 <= int(response.status) < 400,
                "status": int(response.status),
                "latency_ms": round((time.time() - started) * 1000),
                "preview": " ".join(body.split())[:160],
            }
    except Exception as exc:  # noqa: BLE001 - receipt should capture exact block
        return {
            "ok": False,
            "error": type(exc).__name__,
            "detail": str(exc)[:220],
            "latency_ms": round((time.time() - started) * 1000),
        }


def _run(command: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=15, check=False)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": type(exc).__name__, "detail": str(exc)}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def _docker_state() -> dict[str, Any]:
    images = _run(["docker", "images", "--format", "{{.Repository}}:{{.Tag}} {{.Size}}"])
    containers = _run(["docker", "ps", "--format", "{{.Names}} {{.Image}} {{.Ports}}"])
    terms = ("shopping", "gitlab", "postmill", "forum", "kiwix", "wikipedia", "webarena", "magento")
    return {
        "images_available": images.get("ok"),
        "matching_images": [
            line
            for line in str(images.get("stdout") or "").splitlines()
            if any(term in line.lower() for term in terms)
        ],
        "containers_available": containers.get("ok"),
        "matching_containers": [
            line
            for line in str(containers.get("stdout") or "").splitlines()
            if any(term in line.lower() for term in terms)
        ],
        "errors": {
            "images": images.get("stderr") or images.get("detail"),
            "containers": containers.get("stderr") or containers.get("detail"),
        },
    }


def build_payload(host: str, timeout: float) -> dict[str, Any]:
    endpoint_checks: dict[str, Any] = {}
    env_urls: dict[str, str] = {}
    browsergym_urls: dict[str, str] = {}
    for name in DOMAINS:
        url = _domain_url(name, host)
        env_urls[name] = url
        browsergym_urls[f"WA_{name}"] = _wa_url(name)
        endpoint_checks[name] = {"url": url, **_http_check(url, timeout)}

    auth_dir = VENDOR / ".auth"
    auth_files = {name: str(auth_dir / name) for name in EXPECTED_AUTH}
    auth_present = {name: (auth_dir / name).exists() for name in EXPECTED_AUTH}
    generated_configs = sorted(
        p
        for p in (VENDOR / "config_files").glob("*.json")
        if p.name != "test.raw.json" and p.name[0].isdigit()
    )
    docker_state = _docker_state()
    ok_domains = [name for name, result in endpoint_checks.items() if result.get("ok")]
    missing_domains = [name for name, result in endpoint_checks.items() if not result.get("ok")]
    full_domain_ready = len(ok_domains) == len(DOMAINS)
    auth_ready = all(auth_present.values())
    config_ready = bool(generated_configs)
    runner_ready = (VENDOR / "run.py").exists()
    raw_tasks_ready = (VENDOR / "config_files" / "test.raw.json").exists()
    status = "official_ready" if full_domain_ready and auth_ready and config_ready else "not_ready"
    if status != "official_ready" and ok_domains == ["HOMEPAGE"]:
        status = "homepage_subset_only"
    elif status != "official_ready" and ok_domains:
        status = "partial_domain_ready"
    return {
        "id": time.strftime("webarena_official_readiness_%Y%m%dT%H%M%SZ", time.gmtime()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": status,
        "ok": status == "official_ready",
        "host": host,
        "env_urls": env_urls,
        "browsergym_env_urls": browsergym_urls,
        "endpoint_checks": endpoint_checks,
        "ok_domains": ok_domains,
        "missing_domains": missing_domains,
        "auth": {
            "dir": str(auth_dir),
            "files": auth_files,
            "present": auth_present,
            "ready": auth_ready,
        },
        "configs": {
            "raw_tasks": str(VENDOR / "config_files" / "test.raw.json"),
            "raw_tasks_ready": raw_tasks_ready,
            "generated_count": len(generated_configs),
            "generated_examples": [str(p) for p in generated_configs[:8]],
            "ready": config_ready,
        },
        "runner": {
            "run_py": str(VENDOR / "run.py"),
            "ready": runner_ready,
        },
        "docker": docker_state,
        "boundary": (
            "This is an official WebArena readiness receipt. It does not run or claim an official "
            "WebArena score. A real score requires all required domains live, generated task configs, "
            "auth storage state, runner execution, and evaluator output."
        ),
        "next_gate": (
            "Bring up missing domains via the WebArena AMI or local image downloads, run "
            "scripts/generate_test_data.py, run browser_env/auto_login.py, then evaluate a one-task "
            "official slice through vendor/webarena/run.py."
        ),
    }


def write_payload(payload: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"{payload['id']}.json"
    md_path = OUT_DIR / f"{payload['id']}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# WebArena Official Readiness {payload['id']}",
        "",
        f"- Status: `{payload['status']}`",
        f"- Ready: `{payload['ok']}`",
        f"- OK domains: `{', '.join(payload['ok_domains']) or 'none'}`",
        f"- Missing domains: `{', '.join(payload['missing_domains']) or 'none'}`",
        f"- Generated configs: `{payload['configs']['generated_count']}`",
        f"- Auth ready: `{payload['auth']['ready']}`",
        "",
        "## Endpoint Checks",
        "",
        "| Domain | URL | OK | Status/Error |",
        "| --- | --- | ---: | --- |",
    ]
    for name, result in payload["endpoint_checks"].items():
        status = result.get("status") or f"{result.get('error')}: {result.get('detail')}"
        lines.append(f"| {name} | `{result['url']}` | `{result.get('ok')}` | `{status}` |")
    lines.extend(["", "## Boundary", "", payload["boundary"], "", "## Next Gate", "", payload["next_gate"]])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a WebArena official-domain readiness receipt.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--timeout", type=float, default=3.0)
    args = parser.parse_args()
    payload = build_payload(args.host, args.timeout)
    paths = write_payload(payload)
    print(json.dumps({"ok": True, "paths": paths, "status": payload["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
