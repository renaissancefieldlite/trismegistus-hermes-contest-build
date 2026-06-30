from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

from . import db, project_memory
from .integrations import nemoclaw


OPENCLAW_AGENTS = ("main", nemoclaw.OPENCLAW_AGENT_ID)
SESSION_ROOT = "/sandbox/.openclaw/agents"
SYNC_THREAD_ID = "tris-main"


def _run_sandbox(script: str, timeout: int = 25) -> dict[str, Any]:
    openshell = nemoclaw._command_path("openshell")
    if not openshell:
        return {"ok": False, "error": "openshell command not found", "text": ""}
    command = [
        openshell,
        "sandbox",
        "exec",
        "-n",
        nemoclaw.SANDBOX_NAME,
        "--",
        "sh",
        "-lc",
        " ".join(script.split()),
    ]
    try:
        proc = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
            env=nemoclaw._runtime_env(),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced in sync receipt.
        return {"ok": False, "error": str(exc), "text": ""}
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "text": proc.stdout,
        "error": None if proc.returncode == 0 else proc.stdout[-1000:],
    }


def _session_files(limit: int = 16) -> list[dict[str, Any]]:
    quoted_agents = " ".join(shlex.quote(f"{SESSION_ROOT}/{agent}/sessions") for agent in OPENCLAW_AGENTS)
    script = (
        f"find {quoted_agents} -type f -name '*.jsonl' "
        "! -name '*.trajectory.jsonl' ! -name '._*' "
        "-printf '%T@ %p\\n' 2>/dev/null | sort -rn | head -n "
        f"{int(limit)}"
    )
    result = _run_sandbox(script)
    files: list[dict[str, Any]] = []
    for line in str(result.get("text", "")).splitlines():
        stamp, _, path = line.partition(" ")
        if not path:
            continue
        try:
            mtime = float(stamp)
        except ValueError:
            mtime = 0.0
        files.append({"path": path.strip(), "mtime": mtime})
    return files


def _read_session(path: str) -> list[dict[str, Any]]:
    result = _run_sandbox(f"cat -- {shlex.quote(path)}", timeout=20)
    rows: list[dict[str, Any]] = []
    for line in str(result.get("text", "")).splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _agent_from_path(path: str) -> str:
    parts = Path(path).parts
    try:
        index = parts.index("agents")
        return parts[index + 1]
    except (ValueError, IndexError):
        return "unknown"


def _session_id(path: str, rows: list[dict[str, Any]]) -> str:
    for row in rows:
        if row.get("type") == "session" and row.get("id"):
            return str(row["id"])
    name = Path(path).name
    return name.removesuffix(".jsonl")


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return " ".join(content.split())
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "text" and item.get("text"):
                parts.append(str(item["text"]))
            elif item_type in {"tool_result", "toolResult"} and item.get("text"):
                parts.append(str(item["text"]))
        return " ".join(" ".join(parts).split())
    if isinstance(content, dict) and content.get("text"):
        return " ".join(str(content["text"]).split())
    return ""


def _clean_visible_text(text: str) -> str:
    clean = " ".join(text.split())
    clean = re.sub(r"^\[\[reply_to_current\]\]\s*", "", clean)
    clean = re.sub(r"^\[\[reply_to:[^\]]+\]\]\s*", "", clean)
    return clean


def _is_internal_prompt(text: str) -> bool:
    clean = _clean_visible_text(text)
    if clean.startswith("[assistant turn failed"):
        return True
    if clean.startswith("SYSTEM:"):
        return True
    if re.match(r"^\[[A-Z][a-z]{2} \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\] SYSTEM:", clean):
        return True
    if re.match(r"^\[[A-Z][a-z]{2} \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\]", clean):
        return True
    if " | SYSTEM: " in clean or " | USER: " in clean or " | ASSISTANT: " in clean:
        return True
    if "Request timed out before a response was generated" in clean:
        return True
    return False


def _message_rows(path: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    session_id = _session_id(path, rows)
    agent = _agent_from_path(path)
    messages: list[dict[str, Any]] = []
    seen_visible: set[tuple[str, str]] = set()
    for index, row in enumerate(rows):
        if row.get("type") != "message":
            continue
        message = row.get("message")
        if not isinstance(message, dict):
            continue
        role = str(message.get("role", "")).strip()
        content = _text_from_content(message.get("content"))
        if not content:
            continue
        content = _clean_visible_text(content)
        if _is_internal_prompt(content):
            continue
        if role not in {"user", "assistant"}:
            role = "system"
        signature = (role, content)
        if signature in seen_visible:
            continue
        seen_visible.add(signature)
        source_uid = f"openclaw:{agent}:{session_id}:{row.get('id') or index}"
        messages.append(
            {
                "source_uid": source_uid,
                "source": f"openclaw/{agent}",
                "agent": agent,
                "session_id": session_id,
                "session_file": path,
                "timestamp": row.get("timestamp"),
                "role": role,
                "content": content,
            }
        )
    if not any(message["role"] == "user" for message in messages):
        return []
    return messages


def sync_recent(limit: int = 16) -> dict[str, Any]:
    db.init_db()
    files = _session_files(limit=limit)
    inserted_messages = 0
    inserted_memory = 0
    scanned_messages = 0
    synced_files: list[str] = []
    agents: set[str] = set()

    queued_messages: list[dict[str, Any]] = []
    for item in files:
        path = str(item["path"])
        rows = _read_session(path)
        if not rows:
            continue
        synced_files.append(path)
        queued_messages.extend(_message_rows(path, rows))

    for message in sorted(queued_messages, key=lambda item: str(item.get("timestamp") or "")):
        scanned_messages += 1
        agents.add(str(message["agent"]))
        payload = {
            "source": message["source"],
            "agent": message["agent"],
            "session_id": message["session_id"],
            "session_file": message["session_file"],
            "timestamp": message["timestamp"],
        }
        source_ts = str(message.get("timestamp") or "") or None
        if db.save_external_message(
            SYNC_THREAD_ID,
            str(message["role"]),
            str(message["content"]),
            str(message["source_uid"]),
            str(message["source"]),
            payload,
            ts=source_ts,
        ):
            inserted_messages += 1
            project_memory.append_memory(
                "openclaw_message",
                str(message["content"]),
                {"source_uid": message["source_uid"], **payload},
            )
        if db.save_memory_item(
            "openclaw_message",
            str(message["source_uid"]),
            f"{message['source']} {message['role']}",
            str(message["content"]),
            payload,
        ):
            inserted_memory += 1

    receipt = {
        "ok": True,
        "sandbox": nemoclaw.SANDBOX_NAME,
        "thread_id": SYNC_THREAD_ID,
        "scanned_files": len(files),
        "read_files": len(synced_files),
        "scanned_messages": scanned_messages,
        "inserted_messages": inserted_messages,
        "inserted_memory_items": inserted_memory,
        "agents": sorted(agents),
        "files": synced_files[:8],
        "rag": db.rag_status(),
    }
    db.log_event("openclaw_sync", receipt)
    return receipt
