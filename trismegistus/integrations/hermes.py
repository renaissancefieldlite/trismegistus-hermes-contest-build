from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _api_key() -> str:
    return os.environ.get("HERMES_API_KEY", "").strip() or os.environ.get("NOUS_API_KEY", "").strip()


def _api_key_source() -> str:
    if os.environ.get("HERMES_API_KEY", "").strip():
        return "HERMES_API_KEY"
    if os.environ.get("NOUS_API_KEY", "").strip():
        return "NOUS_API_KEY"
    return ""


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = _api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def endpoint() -> str:
    return os.environ.get("HERMES_BASE_URL", "http://127.0.0.1:8642/v1/chat/completions")


def _base_url() -> str:
    url = endpoint()
    if url.endswith("/chat/completions"):
        return url.rsplit("/chat/completions", 1)[0]
    return url.rstrip("/")


def _models_probe() -> dict[str, Any]:
    url = f"{_base_url().rstrip('/')}/models"
    request = urllib.request.Request(url, headers=_headers(), method="GET")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                data: Any = json.loads(raw)
            except json.JSONDecodeError:
                data = {"raw": raw[:500]}
        models = data.get("data") if isinstance(data, dict) else None
        sample: list[str] = []
        if isinstance(models, list):
            for item in models[:8]:
                if isinstance(item, dict) and item.get("id"):
                    sample.append(str(item["id"]))
        return {
            "ok": True,
            "url": url,
            "latency_ms": round((time.time() - started) * 1000),
            "model_count": len(models) if isinstance(models, list) else None,
            "sample_models": sample,
        }
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {
            "ok": False,
            "url": url,
            "latency_ms": round((time.time() - started) * 1000),
            "error": str(exc),
        }


def _run_hermes_status() -> dict[str, Any]:
    hermes_bin = shutil.which("hermes")
    if not hermes_bin:
        home_bin = Path.home() / ".local" / "bin" / "hermes"
        hermes_bin = str(home_bin) if home_bin.exists() else None
    if not hermes_bin:
        return {"ok": False, "error": "hermes command not found"}
    env = os.environ.copy()
    # Keep this project scoped to the SSD-backed Hermes home when the launcher sets it.
    try:
        proc = subprocess.run(
            [hermes_bin, "status"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=12,
            env=env,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {"ok": False, "command": hermes_bin, "error": str(exc)}
    text = proc.stdout
    # Avoid surfacing any credential fragments from the CLI output in the UI.
    redacted = []
    for line in text.splitlines():
        if "sk_" in line or "API" in line and "✓" in line:
            redacted.append(line.split("✓", 1)[0] + "✓ configured")
        else:
            redacted.append(line)
    return {
        "ok": proc.returncode == 0,
        "command": hermes_bin,
        "returncode": proc.returncode,
        "text": "\n".join(redacted)[-5000:],
    }


def status() -> dict[str, Any]:
    url = endpoint()
    probe = _models_probe()
    cli = _run_hermes_status()
    cli_text = str(cli.get("text", ""))
    cli_ready = bool(
        cli.get("ok")
        and "Nous Portal" in cli_text
        and ("logged in" in cli_text or "✓" in cli_text)
    )
    return {
        "name": "Hermes Agent",
        "endpoint": url,
        "model": os.environ.get("HERMES_MODEL", "hermes-agent"),
        "configured": bool(url),
        "api_key_present": bool(_api_key()),
        "api_key_source": _api_key_source(),
        "mode": "gateway-or-cli",
        "probe": probe,
        "cli": cli,
        "cli_ready": cli_ready,
        "ready": bool(probe.get("ok", False) or cli_ready),
    }


def _prompt_from_messages(messages: list[dict[str, str]]) -> str:
    parts: list[str] = []
    for message in messages:
        role = str(message.get("role", "user")).strip().upper()
        content = " ".join(str(message.get("content", "")).strip().split())
        if content:
            parts.append(f"{role}: {content}")
    return " | ".join(parts)


def _run_hermes_oneshot(messages: list[dict[str, str]], started: float) -> dict[str, Any]:
    hermes_bin = shutil.which("hermes")
    if not hermes_bin:
        home_bin = Path.home() / ".local" / "bin" / "hermes"
        hermes_bin = str(home_bin) if home_bin.exists() else None
    if not hermes_bin:
        return {"ok": False, "source": "hermes-cli", "error": "hermes command not found"}
    prompt = _prompt_from_messages(messages)
    if not prompt:
        return {"ok": False, "source": "hermes-cli", "error": "empty prompt"}
    try:
        proc = subprocess.run(
            [hermes_bin, "-z", prompt, "--yolo"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=90,
            env=os.environ.copy(),
            check=False,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {
            "ok": False,
            "source": "hermes-cli",
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }
    text = proc.stdout.strip()
    return {
        "ok": proc.returncode == 0 and bool(text),
        "source": "hermes-cli",
        "provider": "Nous Portal",
        "model": os.environ.get("HERMES_MODEL", "hermes-agent"),
        "text": text,
        "returncode": proc.returncode,
        "latency_ms": round((time.time() - started) * 1000),
        "raw": text[-5000:],
    }


def generate(messages: list[dict[str, str]], max_tokens: int = 450) -> dict[str, Any]:
    url = endpoint()
    remote_auth_required = url.startswith("https://") or "nousresearch.com" in url
    if remote_auth_required and not _api_key():
        return {
            "ok": False,
            "source": "hermes",
            "error": "Hermes/Nous provider key is not configured. Set HERMES_API_KEY or NOUS_API_KEY.",
            "latency_ms": 0,
        }
    payload = {
        "model": os.environ.get("HERMES_MODEL", "hermes-agent"),
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=_headers(),
        method="POST",
    )
    started = time.time()
    try:
        timeout_seconds = int(os.environ.get("HERMES_TIMEOUT_SECONDS", "20"))
    except ValueError:
        timeout_seconds = 20
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        cli = _run_hermes_oneshot(messages, started)
        if cli.get("ok"):
            cli["gateway_error"] = f"HTTP {exc.code}: {detail[:500]}"
            return cli
        return {
            "ok": False,
            "source": "hermes",
            "error": f"HTTP {exc.code}: {detail[:500]}",
            "latency_ms": round((time.time() - started) * 1000),
            "cli": cli,
        }
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        cli = _run_hermes_oneshot(messages, started)
        if cli.get("ok"):
            cli["gateway_error"] = str(exc)
            return cli
        return {
            "ok": False,
            "source": "hermes",
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
            "cli": cli,
        }

    text = ""
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        text = json.dumps(data, indent=2)[:1200]
    return {
        "ok": True,
        "source": "hermes",
        "text": text,
        "latency_ms": round((time.time() - started) * 1000),
        "raw": data,
    }
