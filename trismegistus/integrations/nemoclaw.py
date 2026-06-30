from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
LAST_RECEIPT_PATH = DATA_DIR / "openclaw_last_receipt.json"
VENDOR = ROOT / "vendor" / "NemoClaw"
SANDBOX_NAME = os.environ.get("TRISMEGISTUS_NEMOCLAW_SANDBOX", "trismegistus-openclaw")
OPENCLAW_AGENT_ID = os.environ.get("TRISMEGISTUS_OPENCLAW_AGENT", "trismegistus")
OPENCLAW_MODEL = os.environ.get(
    "TRISMEGISTUS_OPENCLAW_MODEL",
    "ollama-direct/hf.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M",
)
OPENCLAW_SESSION_KEY = os.environ.get(
    "TRISMEGISTUS_OPENCLAW_SESSION_KEY",
    f"agent:{OPENCLAW_AGENT_ID}:tris-ui-live",
)

COLIMA_SOCKET_CANDIDATES = (
    Path.home() / ".colima" / "tris" / "docker.sock",
    Path("/tmp/c990/tris/docker.sock"),
)


def _command_path(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    candidate = VENDOR / "bin" / f"{name}.js"
    return str(candidate) if candidate.exists() else None


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{Path.home() / '.local' / 'bin'}:/opt/homebrew/bin:{VENDOR / 'bin'}:{env.get('PATH', '')}"
    if "DOCKER_HOST" not in env:
        socket = next((candidate for candidate in COLIMA_SOCKET_CANDIDATES if candidate.exists()), COLIMA_SOCKET_CANDIDATES[0])
        env["DOCKER_HOST"] = f"unix://{socket}"
    if "COLIMA_HOME" not in env and COLIMA_SOCKET_CANDIDATES[1].exists():
        env["COLIMA_HOME"] = "/tmp/c990"
    env.setdefault("NEMOCLAW_IGNORE_RUNTIME_RESOURCES", "1")
    return env


def _extract_json(text: str) -> dict[str, Any] | None:
    payload = _extract_json_value(text)
    return payload if isinstance(payload, dict) else None


def _extract_json_value(text: str) -> Any | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
            return payload
        except json.JSONDecodeError:
            continue
    return None


def _run(command: list[str], timeout: int = 12) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            env=_runtime_env(),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {"ok": False, "command": command, "error": str(exc)}
    return {
        "ok": proc.returncode == 0,
        "command": command,
        "returncode": proc.returncode,
        "text": proc.stdout[-12000:],
    }


def _json_check(command: list[str], timeout: int = 20) -> tuple[dict[str, Any], Any]:
    result = _run(command, timeout=timeout)
    return result, _extract_json_value(str(result.get("text", "")))


def _doctor_summary(checks: list[Any]) -> dict[str, Any]:
    live_sandbox = False
    inference_route = False
    provider_health = False
    warning_details: list[str] = []
    for item in checks:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", ""))
        status = str(item.get("status", ""))
        detail = str(item.get("detail", ""))
        if label == "Live sandbox" and status == "ok" and "Ready" in detail:
            live_sandbox = True
        if label == "Route" and status == "ok":
            inference_route = True
        if label.startswith("Provider health") and status == "ok":
            provider_health = True
        if status == "warn":
            warning_details.append(f"{label}: {detail}")
    return {
        "live_sandbox": live_sandbox,
        "inference_route": inference_route,
        "provider_health": provider_health,
        "warnings": warning_details,
    }


def _sandbox_phase_from_list(text: str, name: str) -> str | None:
    clean = re.sub(r"\x1b\[[0-9;]*m", "", text)
    for line in clean.splitlines():
        parts = line.split()
        if parts and parts[0] == name and len(parts) >= 4:
            return parts[-1]
    return None


def _agents_from_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def channel_status(channel: str = "telegram") -> dict[str, Any]:
    nemoclaw = _command_path("nemoclaw")
    if not nemoclaw:
        return {
            "channel": channel,
            "registered": False,
            "policy_applied": False,
            "ok": False,
            "summary": f"{channel} status unavailable; nemoclaw CLI missing",
        }

    result, payload = _json_check(
        [nemoclaw, SANDBOX_NAME, "channels", "status", "--channel", channel, "--json"],
        timeout=12,
    )
    signals = payload.get("signals", []) if isinstance(payload, dict) else []

    def detail_for(label: str) -> str:
        for signal in signals:
            if isinstance(signal, dict) and signal.get("label") == label:
                return str(signal.get("detail", ""))
        return ""

    registration = detail_for("Channel registration")
    policy = detail_for("Policy coverage")
    registered = "registered" in registration and "not registered" not in registration
    policy_applied = "applied" in policy and "not applied" not in policy
    summary = (
        f"{channel} registered / policy applied"
        if registered and policy_applied
        else f"{channel} registration={registration or 'unknown'}; policy={policy or 'unknown'}"
    )
    return {
        "channel": channel,
        "ok": bool(result.get("ok")),
        "registered": registered,
        "policy_applied": policy_applied,
        "verdict": payload.get("verdict") if isinstance(payload, dict) else None,
        "signals": signals,
        "summary": summary,
    }


def status() -> dict[str, Any]:
    nemohermes = _command_path("nemohermes")
    nemoclaw = _command_path("nemoclaw")
    openshell = _command_path("openshell")
    cli_paths = {
        "nemohermes": nemohermes,
        "nemoclaw": nemoclaw,
        "openshell": openshell,
        "docker": shutil.which("docker"),
        "colima": shutil.which("colima"),
    }

    command_checks: dict[str, Any] = {}
    nemohermes_data: dict[str, Any] = {}
    nemoclaw_data: dict[str, Any] = {}
    doctor_data: dict[str, Any] = {}
    inference_data: dict[str, Any] = {}
    telegram_channel: dict[str, Any] = {}
    openclaw_agents: list[dict[str, Any]] = []

    if nemohermes:
        command_checks["nemohermes_status"], payload = _json_check([nemohermes, "status", "--json"], timeout=12)
        if isinstance(payload, dict):
            nemohermes_data = payload
        command_checks["nemohermes_inference"], payload = _json_check([nemohermes, "inference", "get", "--json"], timeout=12)
        if isinstance(payload, dict):
            inference_data = payload
        command_checks["nemohermes_doctor"], payload = _json_check(
            [nemohermes, SANDBOX_NAME, "doctor", "--json"],
            timeout=25,
        )
        if isinstance(payload, dict):
            doctor_data = payload
    if nemoclaw:
        command_checks["nemoclaw_status"], payload = _json_check([nemoclaw, SANDBOX_NAME, "status", "--json"], timeout=12)
        if isinstance(payload, dict):
            nemoclaw_data = payload
        telegram_channel = channel_status("telegram")
    if openshell:
        command_checks["openshell_sandboxes"] = _run([openshell, "sandbox", "list"], timeout=12)
        command_checks["openclaw_agents"], payload = _json_check(
            [
                openshell,
                "sandbox",
                "exec",
                "-n",
                SANDBOX_NAME,
                "--",
                "openclaw",
                "agents",
                "list",
                "--json",
            ],
            timeout=25,
        )
        openclaw_agents = _agents_from_payload(payload)

    sandboxes: list[Any] = nemohermes_data.get("sandboxes", [])
    doctor_checks = doctor_data.get("checks", []) if isinstance(doctor_data.get("checks"), list) else []
    doctor = _doctor_summary(doctor_checks)

    blockers: list[str] = []
    if not nemohermes:
        blockers.append("nemohermes CLI missing")
    if not nemoclaw:
        blockers.append("nemoclaw CLI missing")
    if not openshell:
        blockers.append("openshell CLI missing")
    if not cli_paths["docker"] and not cli_paths["colima"]:
        blockers.append("Docker/Colima container runtime missing")

    gateway_health = nemohermes_data.get("gatewayHealth")
    gateway_ready = bool(isinstance(gateway_health, dict) and gateway_health.get("healthy"))
    gateway_ready = gateway_ready or bool(doctor_data.get("status") in {"ok", "warn"})
    openshell_phase = _sandbox_phase_from_list(str(command_checks.get("openshell_sandboxes", {}).get("text", "")), SANDBOX_NAME)
    sandbox_phase = str(nemoclaw_data.get("phase") or openshell_phase or "missing")
    sandbox_ready = bool(
        nemoclaw_data.get("phase") == "Ready"
        or doctor.get("live_sandbox")
        or openshell_phase == "Ready"
    )
    inference_health = nemoclaw_data.get("inferenceHealth")
    inference_ready = bool(isinstance(inference_health, dict) and inference_health.get("ok"))
    inference_ready = inference_ready or bool(nemohermes_data.get("liveInference"))
    inference_ready = inference_ready or bool(doctor.get("inference_route") and doctor.get("provider_health"))
    inference_ready = inference_ready or bool(inference_data.get("provider") and inference_data.get("model"))
    agent_ready = any(item.get("id") == OPENCLAW_AGENT_ID for item in openclaw_agents)
    if not sandbox_ready:
        blockers.append(f"NemoClaw sandbox not ready: {SANDBOX_NAME} ({sandbox_phase})")
    if not gateway_ready:
        blockers.append("OpenShell/OpenClaw gateway not ready")
    if not inference_ready:
        blockers.append("NemoHermes inference route not ready")
    if not agent_ready:
        blockers.append(f"OpenClaw agent not configured: {OPENCLAW_AGENT_ID}")

    openclaw_ready = bool(nemohermes and nemoclaw and openshell and sandbox_ready and gateway_ready and inference_ready and agent_ready)

    return {
        "name": "NemoHermes / OpenClaw / NemoClaw",
        "cli_paths": cli_paths,
        "command_checks": command_checks,
        "installed": bool(nemohermes and nemoclaw),
        "sandboxes": sandboxes,
        "sandbox": SANDBOX_NAME,
        "sandbox_phase": sandbox_phase,
        "agent": OPENCLAW_AGENT_ID,
        "agents": openclaw_agents,
        "doctor": doctor_data,
        "doctor_summary": doctor,
        "inference": inference_data,
        "nemohermes_status": nemohermes_data,
        "nemoclaw_status": nemoclaw_data,
        "channels": {"telegram": telegram_channel},
        "telegram_registered": bool(telegram_channel.get("registered")),
        "telegram_policy_applied": bool(telegram_channel.get("policy_applied")),
        "channel_gate": telegram_channel.get("summary")
        or "NemoClaw/OpenClaw channels add/status for Discord or Telegram bot",
        "gateway_ready": gateway_ready,
        "sandbox_ready": sandbox_ready,
        "inference_ready": inference_ready,
        "agent_ready": agent_ready,
        "model": OPENCLAW_MODEL,
        "blockers": blockers,
        "openclaw_ready": openclaw_ready,
        "ready": openclaw_ready,
        "next_command_when_ready": (
            f"openshell sandbox exec -n {SANDBOX_NAME} -- openclaw agent "
            f"--agent {OPENCLAW_AGENT_ID} --model {OPENCLAW_MODEL}"
        ),
    }


def _prompt_from_messages(messages: list[dict[str, str]]) -> str:
    prompt_parts: list[str] = []
    for message in messages:
        role = message.get("role", "user").strip().upper()
        content = " ".join(message.get("content", "").strip().split())
        if content:
            prompt_parts.append(f"{role}: {content}")
    # OpenShell sandbox exec rejects command arguments containing newlines.
    # Keep the transcript single-line so browser chat history can reach OpenClaw.
    return " | ".join(prompt_parts)


def _agent_payload(raw: str) -> dict[str, Any] | None:
    payload = _extract_json(raw)
    if not isinstance(payload, dict):
        return None
    if "payloads" in payload:
        return payload
    result = payload.get("result")
    if isinstance(result, dict) and "payloads" in result:
        result = dict(result)
        result["_run"] = {
            "runId": payload.get("runId"),
            "status": payload.get("status"),
            "summary": payload.get("summary"),
        }
        return result
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def last_receipt() -> dict[str, Any] | None:
    if not LAST_RECEIPT_PATH.exists():
        return None
    try:
        return json.loads(LAST_RECEIPT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_last_receipt(result: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "ts": _utc_now(),
        "ok": bool(result.get("ok")),
        "source": result.get("source"),
        "runtime_lane": result.get("runtime_lane"),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "sandbox": result.get("sandbox"),
        "agent": result.get("agent"),
        "session_file": result.get("session_file"),
        "latency_ms": result.get("latency_ms"),
    }
    LAST_RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _format_agent_result(payload: dict[str, Any], started: float, source: str) -> dict[str, Any]:
    payloads = payload.get("payloads") or []
    text = str(payloads[0].get("text") or "") if payloads and isinstance(payloads[0], dict) else ""
    meta = payload.get("meta") or {}
    agent_meta = meta.get("agentMeta") or {}
    trace = meta.get("executionTrace") or {}
    result = {
        "ok": bool(text),
        "source": source,
        "runtime_lane": "nemohermes-openclaw",
        "text": text.strip(),
        "model": agent_meta.get("model") or trace.get("winnerModel") or OPENCLAW_MODEL,
        "provider": agent_meta.get("provider") or trace.get("winnerProvider"),
        "sandbox": SANDBOX_NAME,
        "agent": OPENCLAW_AGENT_ID,
        "session_file": agent_meta.get("sessionFile"),
        "session_id": agent_meta.get("sessionId"),
        "usage": agent_meta.get("usage"),
        "latency_ms": round((time.time() - started) * 1000),
        "raw": payload,
    }
    if result["ok"]:
        _write_last_receipt(result)
    return result


def _run_openclaw_direct(
    prompt: str,
    started: float,
    session_key: str | None = None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    openshell = _command_path("openshell")
    if not openshell:
        return {"ok": False, "source": "openclaw-openshell", "error": "openshell command not found"}
    command = [
        openshell,
        "sandbox",
        "exec",
        "-n",
        SANDBOX_NAME,
        "--",
        "openclaw",
        "agent",
        "--session-key",
        session_key or OPENCLAW_SESSION_KEY,
        "--agent",
        OPENCLAW_AGENT_ID,
        "--model",
        OPENCLAW_MODEL,
        "--message",
        prompt,
        "--json",
        "--timeout",
        str(timeout_seconds),
    ]
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds + 40,
            check=False,
            env=_runtime_env(),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {
            "ok": False,
            "source": "openclaw-openshell",
            "runtime_lane": "nemohermes-openclaw",
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }

    raw = proc.stdout[-30000:]
    payload = _agent_payload(raw)
    if proc.returncode != 0 or not payload:
        return {
            "ok": False,
            "source": "openclaw-openshell",
            "runtime_lane": "nemohermes-openclaw",
            "returncode": proc.returncode,
            "error": "OpenShell/OpenClaw agent command failed or returned no JSON.",
            "raw": raw,
            "latency_ms": round((time.time() - started) * 1000),
        }
    return _format_agent_result(payload, started, "openclaw-openshell")


def _run_nemohermes_wrapper(
    prompt: str,
    started: float,
    session_key: str | None = None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    nemohermes = _command_path("nemohermes")
    if not nemohermes:
        return {"ok": False, "source": "nemohermes-openclaw", "error": "nemohermes command not found"}

    command = [
        nemohermes,
        SANDBOX_NAME,
        "agent",
        "--session-key",
        session_key or OPENCLAW_SESSION_KEY,
        "--agent",
        OPENCLAW_AGENT_ID,
        "--model",
        OPENCLAW_MODEL,
        "--message",
        prompt,
        "--json",
        "--timeout",
        str(timeout_seconds),
    ]
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds + 30,
            check=False,
            env=_runtime_env(),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {
            "ok": False,
            "source": "nemohermes-openclaw",
            "runtime_lane": "nemohermes-openclaw",
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }

    raw = proc.stdout[-24000:]
    payload = _agent_payload(raw)
    if proc.returncode != 0 or not payload:
        return {
            "ok": False,
            "source": "nemohermes-openclaw",
            "runtime_lane": "nemohermes-openclaw",
            "returncode": proc.returncode,
            "error": "OpenClaw agent command failed or returned no JSON.",
            "raw": raw,
            "latency_ms": round((time.time() - started) * 1000),
        }
    return _format_agent_result(payload, started, "nemohermes-openclaw")


def generate(
    messages: list[dict[str, str]],
    max_tokens: int = 700,
    session_key: str | None = None,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    prompt = _prompt_from_messages(messages)
    started = time.time()
    direct = _run_openclaw_direct(prompt, started, session_key=session_key, timeout_seconds=timeout_seconds)
    if direct.get("ok"):
        return direct
    wrapper = _run_nemohermes_wrapper(prompt, started, session_key=session_key, timeout_seconds=timeout_seconds)
    if wrapper.get("ok"):
        wrapper["direct_error"] = direct.get("error")
        return wrapper
    return {
        "ok": False,
        "source": "nemohermes-openclaw",
        "runtime_lane": "nemohermes-openclaw",
        "target_runtime": "NemoHermes + OpenClaw + NemoClaw",
        "error": wrapper.get("error") or direct.get("error") or "OpenClaw route failed.",
        "direct_error": direct.get("error"),
        "wrapper_error": wrapper.get("error"),
        "direct_raw": direct.get("raw"),
        "wrapper_raw": wrapper.get("raw"),
        "latency_ms": round((time.time() - started) * 1000),
    }
