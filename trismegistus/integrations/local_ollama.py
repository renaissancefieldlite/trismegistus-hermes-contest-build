from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any


def base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")


def model_name() -> str:
    return os.environ.get("TRISMEGISTUS_LOCAL_MODEL", "openhermes:latest")


def _request_json(path: str, payload: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    url = f"{base_url()}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def status() -> dict[str, Any]:
    started = time.time()
    try:
        payload = _request_json("/api/tags", timeout=4)
    except Exception as exc:  # noqa: BLE001 - surfaced as runtime truth
        return {
            "name": "Local Ollama",
            "base_url": base_url(),
            "model": model_name(),
            "ready": False,
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }

    models = [item.get("name", "") for item in payload.get("models", [])]
    target = model_name()
    return {
        "name": "Local Ollama",
        "base_url": base_url(),
        "model": target,
        "models": models,
        "ready": target in models,
        "latency_ms": round((time.time() - started) * 1000),
    }


def _prompt_from_messages(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.get("role", "user").strip().upper()
        content = message.get("content", "").strip()
        if not content:
            continue
        lines.append(f"{role}:\n{content}")
    lines.append("ASSISTANT:")
    return "\n\n".join(lines)


def generate(messages: list[dict[str, str]], max_tokens: int = 700) -> dict[str, Any]:
    target = model_name()
    payload = {
        "model": target,
        "prompt": _prompt_from_messages(messages),
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": max_tokens,
        },
    }
    started = time.time()
    try:
        data = _request_json("/api/generate", payload=payload, timeout=80)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "source": "ollama",
            "model": target,
            "error": f"HTTP {exc.code}: {detail[:500]}",
            "latency_ms": round((time.time() - started) * 1000),
        }
    except Exception as exc:  # noqa: BLE001 - surfaced as runtime truth
        return {
            "ok": False,
            "source": "ollama",
            "model": target,
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }
    return {
        "ok": True,
        "source": "ollama",
        "model": target,
        "text": data.get("response", "").strip(),
        "latency_ms": round((time.time() - started) * 1000),
        "raw": data,
    }
