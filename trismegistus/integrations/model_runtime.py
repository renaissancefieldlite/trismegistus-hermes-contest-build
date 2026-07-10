from __future__ import annotations

import os
import shutil
import threading
import time
from typing import Any

from . import hermes, local_ollama, nemoclaw
from .. import gfl_bridge


_STATUS_CACHE: dict[str, Any] | None = None
_STATUS_CACHE_TS = 0.0
_STATUS_CACHE_TTL = 45.0
_STATUS_REFRESHING = False
_STATUS_LOCK = threading.Lock()


def _build_status() -> dict[str, Any]:
    global _STATUS_CACHE, _STATUS_CACHE_TS
    now = time.time()

    gfl_status = gfl_bridge.status()
    hermes_status = hermes.status()
    openclaw_status = nemoclaw.status()
    if gfl_status.get("ready"):
        active = "golden-field-lite-hermes-bridge"
    elif hermes_status.get("ready"):
        active = "hermes"
    elif openclaw_status.get("ready"):
        active = "nemohermes-openclaw"
        ollama_status = {"ready": False, "skipped": "OpenClaw route is active"}
    else:
        active = "none"
        ollama_status = local_ollama.status()
        if ollama_status.get("ready"):
            active = "ollama-standby"

    payload = {
        "name": "Trismegistus model runtime",
        "active": active,
        "ready": active in {"nemohermes-openclaw", "hermes"},
        "openclaw": openclaw_status,
        "golden_field_lite": gfl_status,
        "hermes": hermes_status,
        "ollama": ollama_status,
        "contest_target": "NemoHermes + OpenClaw + NemoClaw",
        "current_truth": (
            "Golden Field Lite supplies the known-good research partner bridge when ready. "
            "OpenClaw/NemoClaw remains the worker receipt layer. External apply, email, "
            "spend, or payment collection remains a separate connector receipt gate."
        ),
    }
    _STATUS_CACHE = payload
    _STATUS_CACHE_TS = now
    return payload


def _refresh_status_background() -> None:
    global _STATUS_REFRESHING
    try:
        _build_status()
    finally:
        with _STATUS_LOCK:
            _STATUS_REFRESHING = False


def _ensure_background_refresh() -> None:
    global _STATUS_REFRESHING
    with _STATUS_LOCK:
        if _STATUS_REFRESHING:
            return
        _STATUS_REFRESHING = True
    thread = threading.Thread(target=_refresh_status_background, name="tris-runtime-status-refresh", daemon=True)
    thread.start()


def _checking_status() -> dict[str, Any]:
    return {
        "name": "Trismegistus model runtime",
        "active": "checking",
        "ready": False,
        "refreshing": True,
        "golden_field_lite": {
            "name": "Golden Field Lite bridge",
            "ready": False,
            "refreshing": True,
        },
        "openclaw": {
            "name": "NemoHermes / OpenClaw / NemoClaw",
            "sandbox": nemoclaw.SANDBOX_NAME,
            "agent": nemoclaw.OPENCLAW_AGENT_ID,
            "model": nemoclaw.OPENCLAW_MODEL,
            "ready": False,
            "openclaw_ready": False,
            "blockers": ["runtime status refresh in progress"],
        },
        "hermes": {"ready": False, "skipped": "runtime status refresh in progress"},
        "ollama": {"ready": False, "skipped": "runtime status refresh in progress"},
        "contest_target": "NemoHermes + OpenClaw + NemoClaw",
        "current_truth": "Runtime status is refreshing; chat generation uses the direct OpenClaw route.",
    }


def _configured_openclaw_status() -> dict[str, Any]:
    receipt = nemoclaw.last_receipt()
    ready = bool(receipt and receipt.get("ok"))
    installed = bool(shutil.which("nemoclaw") or nemoclaw._command_path("nemoclaw"))
    openshell_installed = bool(shutil.which("openshell") or nemoclaw._command_path("openshell"))
    telegram_channel = nemoclaw.channel_status("telegram") if installed else {}
    telegram_ready = bool(telegram_channel.get("registered") and telegram_channel.get("policy_applied"))
    return {
        "name": "NemoHermes / OpenClaw / NemoClaw",
        "installed": installed,
        "openshell_installed": openshell_installed,
        "sandbox": nemoclaw.SANDBOX_NAME,
        "agent": nemoclaw.OPENCLAW_AGENT_ID,
        "model": nemoclaw.OPENCLAW_MODEL,
        "ready": ready,
        "openclaw_ready": ready,
        "provider": (receipt or {}).get("provider"),
        "session_file": (receipt or {}).get("session_file"),
        "last_receipt": receipt,
        "channels": {"telegram": telegram_channel},
        "telegram_registered": bool(telegram_channel.get("registered")),
        "telegram_policy_applied": bool(telegram_channel.get("policy_applied")),
        "channel_ready": telegram_ready,
        "channel_gate": (
            telegram_channel.get("summary")
            if telegram_channel
            else "NemoClaw/OpenClaw channels add/status for Discord or Telegram bot"
        ),
        "blockers": [] if ready else ["OpenClaw worker receipt pending"],
    }


def status() -> dict[str, Any]:
    now = time.time()
    gfl_status = gfl_bridge.status()
    if gfl_status.get("ready"):
        openclaw_status = _configured_openclaw_status()
        return {
            "name": "Trismegistus model runtime",
            "active": "golden-field-lite-hermes-bridge",
            "ready": True,
            "openclaw": openclaw_status,
            "golden_field_lite": gfl_status,
            "hermes": {"ready": False, "skipped": "Golden Field Lite bridge is active"},
            "ollama": {"ready": False, "skipped": "Golden Field Lite bridge is active"},
            "contest_target": "Golden Field Lite Hermes bridge + OpenClaw/NemoClaw worker receipts",
            "current_truth": (
                "Golden Field Lite supplies the known-good research partner bridge. "
                "OpenClaw/NemoClaw is the worker receipt gate."
            ),
        }
    if _STATUS_CACHE and now - _STATUS_CACHE_TS < _STATUS_CACHE_TTL:
        cached = dict(_STATUS_CACHE)
        cached["cached"] = True
        cached["cache_age_ms"] = round((now - _STATUS_CACHE_TS) * 1000)
        return cached
    _ensure_background_refresh()
    if _STATUS_CACHE:
        cached = dict(_STATUS_CACHE)
        cached["cached"] = True
        cached["stale"] = True
        cached["cache_age_ms"] = round((now - _STATUS_CACHE_TS) * 1000)
        return cached
    return _checking_status()


def generate(
    messages: list[dict[str, str]],
    max_tokens: int = 700,
    session_key: str | None = None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    try:
        timeout_seconds = min(timeout_seconds, int(os.environ.get("TRISMEGISTUS_MODEL_TIMEOUT_SECONDS", str(timeout_seconds))))
    except ValueError:
        pass

    gfl = gfl_bridge.generate(messages, max_tokens=max_tokens)
    if gfl.get("ok"):
        gfl["target_runtime"] = "Golden Field Lite Hermes bridge + OpenClaw/NemoClaw worker receipts"
        return gfl

    live_hermes = hermes.generate(messages, max_tokens=max_tokens)
    hermes_result = live_hermes.get("cli") if isinstance(live_hermes.get("cli"), dict) else live_hermes
    if hermes_result.get("ok"):
        hermes_result["runtime_lane"] = "hermes"
        hermes_result["target_runtime"] = "Hermes Agent + NemoClaw/OpenClaw worker receipts"
        return hermes_result

    if os.environ.get("TRISMEGISTUS_ENABLE_OPENCLAW", "1") == "1":
        openclaw = nemoclaw.generate(
            messages,
            max_tokens=max_tokens,
            session_key=session_key,
            timeout_seconds=timeout_seconds,
        )
    else:
        openclaw = {
            "ok": False,
            "source": "nemohermes-openclaw",
            "runtime_lane": "nemohermes-openclaw",
            "error": "OpenClaw/NemoClaw worker route is disabled on the hosted public demo.",
        }
    if openclaw.get("ok"):
        openclaw["runtime_lane"] = "nemohermes-openclaw"
        openclaw["target_runtime"] = "NemoHermes + OpenClaw + NemoClaw"
        openclaw["hermes_error"] = live_hermes.get("error")
        return openclaw

    if os.environ.get("TRISMEGISTUS_ALLOW_OLLAMA_FALLBACK") != "1":
        return {
            "ok": False,
            "source": "model_runtime",
            "runtime_lane": "blocked-no-openclaw",
            "target_runtime": "NemoHermes + OpenClaw + NemoClaw",
            "error": "OpenClaw/NemoHermes did not answer. Ollama fallback is intentionally disabled for the operator route.",
            "openclaw_error": openclaw.get("error"),
            "hermes_error": live_hermes.get("error"),
        }

    live_ollama = local_ollama.generate(messages, max_tokens=max_tokens)
    if live_ollama.get("ok"):
        live_ollama["runtime_lane"] = "ollama-standby"
        live_ollama["target_runtime"] = "NemoHermes + OpenClaw + NemoClaw"
        live_ollama["openclaw_error"] = openclaw.get("error")
        live_ollama["hermes_error"] = live_hermes.get("error")
        return live_ollama

    return {
        "ok": False,
        "source": "model_runtime",
        "runtime_lane": "none",
        "target_runtime": "NemoHermes + OpenClaw + NemoClaw",
        "error": "No configured model runtime answered.",
        "openclaw_error": openclaw.get("error"),
        "hermes_error": live_hermes.get("error"),
        "ollama_error": live_ollama.get("error"),
    }
