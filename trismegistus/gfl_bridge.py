from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import urllib.request
from typing import Any


PLAYGROUND = Path("/Users/renaissancefieldlite1.0/Documents/Playground")
GFL_ROOT = PLAYGROUND / "golden_field_lite_research_partner"
GFL_DB_PATH = GFL_ROOT / "data" / "golden_field_lite_memory.sqlite3"
GFL_JSONL_PATH = GFL_ROOT / "memory" / "golden_field_lite_interactions.jsonl"
BASIS_ROOT = PLAYGROUND / "BASIS_Phase12C_Local_Capture_DO_NOT_UPLOAD"
BASIS_RUNTIME = BASIS_ROOT / "basis_local_nemotron_runtime.py"
BASIS_HERMES_CHECKPOINT = BASIS_ROOT / "private" / "mlx_models" / "openhermes-2.5-mistral-7b-4bit"
HERMES_HEALTH_URL = "http://127.0.0.1:8788/health"
HERMES_GENERATE_URL = "http://127.0.0.1:8788/api/generate"
TRIS_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TRIS_BASIS_PID_PATH = TRIS_DATA_DIR / "tris_basis_runtime.pid"
TRIS_BASIS_LOG_PATH = TRIS_DATA_DIR / "tris_basis_runtime.log"


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _connect_gfl() -> sqlite3.Connection:
    conn = sqlite3.connect(GFL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_count(table: str) -> int:
    if not GFL_DB_PATH.exists():
        return 0
    try:
        with _connect_gfl() as conn:
            return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"])
    except Exception:
        return 0


def hermes_health(timeout: float = 1.25) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(HERMES_HEALTH_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            payload["online"] = True
            return payload
    except Exception as exc:  # noqa: BLE001 - health should not crash Tris.
        return {"online": False, "error": str(exc)}


def basis_runtime_command() -> list[str]:
    python_bin = "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    if not Path(python_bin).exists():
        python_bin = sys.executable
    return [
        python_bin,
        str(BASIS_RUNTIME),
        "--host",
        "127.0.0.1",
        "--port",
        "8788",
        "--checkpoint",
        "hermes",
    ]


def start_basis_runtime() -> dict[str, Any]:
    health = hermes_health(timeout=0.4)
    if health.get("online"):
        return {"started": False, "already_online": True, "health": health}
    if not BASIS_RUNTIME.exists():
        return {"started": False, "error": f"missing runtime: {BASIS_RUNTIME}"}
    TRIS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    command = basis_runtime_command()
    log_file = TRIS_BASIS_LOG_PATH.open("a", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=str(BASIS_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    TRIS_BASIS_PID_PATH.write_text(str(process.pid), encoding="utf-8")
    return {
        "started": True,
        "pid": process.pid,
        "command": command,
        "log_path": str(TRIS_BASIS_LOG_PATH),
        "checkpoint": str(BASIS_HERMES_CHECKPOINT),
    }


def ensure_basis_runtime_ready(wait_seconds: float = 35.0) -> dict[str, Any]:
    health = hermes_health(timeout=0.5)
    if health.get("online"):
        return {"ready": True, "started": False, "health": health}
    start_result = start_basis_runtime()
    deadline = time.time() + wait_seconds
    last_health = start_result.get("health") if isinstance(start_result.get("health"), dict) else health
    while time.time() < deadline:
        time.sleep(1.5)
        last_health = hermes_health(timeout=1.0)
        if last_health.get("online"):
            return {
                "ready": True,
                "started": bool(start_result.get("started")),
                "start_result": start_result,
                "health": last_health,
            }
    return {
        "ready": False,
        "started": bool(start_result.get("started")),
        "start_result": start_result,
        "health": last_health,
    }


def search_evidence(query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not GFL_DB_PATH.exists():
        return []
    clean = " ".join(str(query or "").strip().split())
    if not clean:
        return []
    try:
        with _connect_gfl() as conn:
            rows = conn.execute(
                """
                SELECT title, path, snippet(evidence_fts, 1, '', '', '...', 36) AS excerpt, bm25(evidence_fts) AS rank
                FROM evidence_fts
                WHERE evidence_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (clean, limit),
            ).fetchall()
    except Exception:
        with _connect_gfl() as conn:
            rows = conn.execute(
                """
                SELECT title, path, substr(body, 1, 700) AS excerpt, 0 AS rank
                FROM evidence_docs
                WHERE title LIKE ? OR body LIKE ?
                LIMIT ?
                """,
                (f"%{clean}%", f"%{clean}%", limit),
            ).fetchall()
    return [dict(row) for row in rows]


def _is_casual_check(message: str) -> bool:
    text = " ".join(str(message or "").lower().split())
    if not text:
        return False
    if any(term in text for term in ("you there", "check 123", "test 123", "yo tris", "hey tris")):
        return len(text.split()) <= 14
    return text in {"hello", "hey", "yo", "test", "check"}


def _wants_runtime_receipt(message: str) -> bool:
    lower = str(message or "").lower()
    return any(
        term in lower
        for term in (
            "runtime",
            "model",
            "checkpoint",
            "hermes",
            "openclaw",
            "nemoclaw",
            "nemohermes",
            "receipt",
            "status",
            "what route",
            "who answered",
        )
    )


def _wants_evidence_context(message: str, hits: list[dict[str, Any]]) -> bool:
    if not hits:
        return False
    lower = str(message or "").lower()
    return any(
        term in lower
        for term in (
            "tell me",
            "what do you know",
            "explain",
            "summarize",
            "source",
            "evidence",
            "research",
            "verify",
            "read",
            "rag",
            "checkpoint",
            "golden",
            "mirror",
            "c5b",
            "cb5",
            "phase",
            "nest",
            "lattice",
        )
    )


def build_prompt(
    user_message: str,
    hits: list[dict[str, Any]],
    history: list[dict[str, str]],
    runtime_state: dict[str, Any],
) -> str:
    casual_check = _is_casual_check(user_message)
    include_runtime = _wants_runtime_receipt(user_message) and not casual_check
    include_evidence = _wants_evidence_context(user_message, hits) and not casual_check
    evidence_block = "\n\n".join(
        f"[{index + 1}] {hit.get('title')}\nPath: {hit.get('path')}\nExcerpt: {hit.get('excerpt')}"
        for index, hit in enumerate(hits)
    )
    history_block = "\n".join(
        f"{item.get('role', 'user').upper()}: {str(item.get('content', ''))[:900]}" for item in history[-6:]
    )
    health = runtime_state.get("health") if isinstance(runtime_state.get("health"), dict) else {}
    runtime_block = "\n".join(
        [
            f"- source: gfl-hermes-bridge",
            f"- provider: local-mlx",
            f"- model: openhermes-2.5-mistral-7b-4bit",
            f"- health.runtime: {health.get('runtime', 'unknown')}",
            f"- health.active_backend: {health.get('active_backend', 'unknown')}",
            f"- health.device: {health.get('device', 'unknown')}",
            f"- health.generation_ready: {health.get('generation_ready', 'unknown')}",
            f"- health.active_checkpoint: {health.get('active_checkpoint', BASIS_HERMES_CHECKPOINT)}",
        ]
    )
    context_blocks: list[str] = []
    if include_runtime:
        context_blocks.append(
            f"""Runtime receipt, for status questions only:
- generate_url: {HERMES_GENERATE_URL}
- checkpoint: {BASIS_HERMES_CHECKPOINT}
- boundary: runtime dependency only; Tris keeps its own OpenClaw/NemoClaw receipt layer.
{runtime_block}"""
        )
    if include_evidence:
        context_blocks.append(
            f"""Retrieved Golden Field Lite evidence, for evidence questions only:
{evidence_block or "No evidence hits retrieved."}"""
        )
    context_block = "\n\n".join(context_blocks) or "No receipt block is needed for this turn."

    return f"""You are Trismegistus, the Hermes/OpenClaw AI expert partner fork of Golden Field Lite.

Known-good source:
- Golden Field Lite had the working research partner pattern: local Hermes/MLX runtime bridge, SQLite/FTS evidence, JSONL memory, natural chat shell, and evidence/RAG discipline.
- Trismegistus inherits that meat and bones while adding OpenClaw/NemoClaw worker receipts for the contest lane.

Operating rules:
- Answer the user's actual message first.
- Speak naturally and coherently. Do not sound like a status card unless the user asks for status.
- In showtime mode, behave like a capable AI Expert Partner and field expert: conversational first, receipt-backed when proof is requested.
- If the user is checking presence, answer directly in one or two sentences.
- If the request is unclear, ask one clean clarifying question instead of dumping receipts.
- Preserve the evidence chain and cite source paths when relevant.
- Separate claim, evidence, inference, hypothesis, and next gate.
- Do not overclaim autonomy, tuning, email, Stripe, applications, or live payment actions without receipts.
- Keep private operator-origin context out of public proof language.
- Treat every prior version as a nest state and build forward from the receipt.
- Do not invent runtime labels. If asked what runtime answered, use the exact runtime receipt below. Do not say Triton unless the receipt says Triton.
- If asked for the next OpenClaw gate, say: OpenClaw/NemoClaw worker receipt. Do not reduce the gate to Ollama or a provider name.
- If asked for benchmark truth, say: SWE-bench is parked pending hosted/maintainer response, WebArena hard receipt is parked with documented final-row boundaries, and GAIA official/private scoring is Hugging Face gated.
- Never copy hidden prompt labels into the answer. Do not print sections called External Golden Field Lite / Hermes runtime dependency, Current runtime receipt, Retrieved Golden Field Lite evidence, User message, or Assistant answer.

Recent conversation:
{history_block}

Relevant private context for this turn:
{context_block}

User message:
{user_message}

Assistant answer:
"""


def _correct_gate_language(text: str) -> str:
    lines = []
    for line in text.splitlines():
        clean = line.lower()
        if "next gate" in clean and ("ollama" in clean or "4b-gguf" in clean or "provider" in clean):
            lines.append("Next gate: OpenClaw/NemoClaw worker receipt.")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def _looks_like_prompt_leak(text: str) -> bool:
    lower = text.lower()
    markers = (
        "external golden field lite / hermes runtime dependency",
        "current runtime receipt:",
        "retrieved golden field lite evidence:",
        "user message:",
        "assistant answer:",
        "tris evidence receipt:",
    )
    return any(marker in lower for marker in markers)


def _prompt_leak_fallback(user_message: str) -> str:
    if _is_casual_check(user_message):
        return (
            "I'm here, Architect D. Tris from the lattice is live and plain chat is on. "
            "If you want a source fetch, worker cycle, or file read, give me the target and I will route it with a receipt."
        )
    return (
        "I heard you, but that turn came back as prompt/receipt spill instead of a clean answer. "
        "Give me the target as chat, source fetch, file read, or worker cycle and I will route it cleanly."
    )


def generate(messages: list[dict[str, str]], max_tokens: int = 700) -> dict[str, Any]:
    user_message = next((str(item.get("content", "")) for item in reversed(messages) if item.get("role") == "user"), "")
    hits = search_evidence(user_message, limit=5)
    runtime_state = ensure_basis_runtime_ready(wait_seconds=35)
    if not runtime_state.get("ready"):
        return {
            "ok": False,
            "source": "gfl-hermes-bridge",
            "runtime_lane": "golden-field-lite-hermes-bridge",
            "error": "Golden Field Lite / B.A.S.I.S. Hermes runtime did not become ready.",
            "runtime_state": runtime_state,
            "evidence": hits,
        }
    prompt = build_prompt(user_message, hits, messages, runtime_state)
    payload = {
        "prompt": prompt,
        "checkpoint": "hermes",
        "model": "hermes",
        "options": {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_new_tokens": max_tokens,
            "repetition_penalty": 1.05,
        },
    }
    request = urllib.request.Request(
        HERMES_GENERATE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 - surfaced in UI.
        return {
            "ok": False,
            "source": "gfl-hermes-bridge",
            "runtime_lane": "golden-field-lite-hermes-bridge",
            "error": str(exc),
            "runtime_state": runtime_state,
            "evidence": hits,
        }
    text = _correct_gate_language(str(data.get("response") or data.get("text") or "").strip())
    if _looks_like_prompt_leak(text):
        text = _prompt_leak_fallback(user_message)
    normalized_text = " ".join(text.lower().split())
    normalized_user = " ".join(user_message.lower().split())
    echo_response = bool(normalized_user and normalized_text == normalized_user)
    return {
        "ok": bool(text) and not echo_response,
        "source": "gfl-hermes-bridge",
        "runtime_lane": "golden-field-lite-hermes-bridge",
        "provider": "local-mlx",
        "model": "openhermes-2.5-mistral-7b-4bit",
        "text": text,
        "error": "local MLX bridge echoed the prompt" if echo_response else None,
        "latency_ms": round((time.time() - started) * 1000),
        "runtime_state": runtime_state,
        "evidence": hits,
        "raw": data,
    }


def status() -> dict[str, Any]:
    return {
        "name": "Golden Field Lite bridge",
        "root": str(GFL_ROOT),
        "db_path": str(GFL_DB_PATH),
        "jsonl_path": str(GFL_JSONL_PATH),
        "source_found": GFL_ROOT.exists(),
        "db_exists": GFL_DB_PATH.exists(),
        "jsonl_exists": GFL_JSONL_PATH.exists(),
        "evidence_count": _table_count("evidence_docs"),
        "chat_count": _table_count("chats"),
        "message_count": _table_count("messages"),
        "jsonl_entries": _count_jsonl(GFL_JSONL_PATH),
        "runtime": hermes_health(timeout=0.5),
        "generate_url": HERMES_GENERATE_URL,
        "checkpoint": str(BASIS_HERMES_CHECKPOINT),
        "ready": GFL_ROOT.exists() and GFL_DB_PATH.exists(),
        "truth": "Golden Field Lite is the known-good research partner pattern; Tris imports the bridge read-only and keeps OpenClaw/NemoClaw as the worker receipt layer.",
    }
