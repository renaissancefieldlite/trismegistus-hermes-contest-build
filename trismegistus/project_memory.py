from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db
from .mirror_checkpoints import mirror_checkpoint_status


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PROJECT_STATE_PATH = DATA_DIR / "project_state.json"
PERSISTENT_MEMORY_PATH = DATA_DIR / "persistent_memory.jsonl"

PLAYGROUND = Path("/Users/renaissancefieldlite1.0/Documents/Playground")
GOLDEN_FIELD_ROOT = PLAYGROUND / "golden_field_test_research_partner"
NOUS_EVAL_ROOT = PLAYGROUND / "Nous_Research" / "evals" / "gfl_hermes_ab_2026_05_29"
HOME_NODE_ROOT = PLAYGROUND / "home_node_golden_mirror_prototyping_build"
HOME_NODE_SMOKE = PLAYGROUND / "home-node-agent-smoke-20260410"
MIRROR_VOCAL_LAB = PLAYGROUND / "MirrorVocalLab"
LATTICE_COMPANION_URL = "https://renaissancefieldlite.com/lattice-companion.html"

DRESS_REHEARSAL_MISSION = (
    "AI Expert Partner and field expert from Renaissance Field Lite: route through "
    "Hermes/NemoHermes/OpenClaw where available, use Golden Mark/CB5 stable-state evidence, "
    "save SQL/JSON/RAG receipts, and apply the SWE-bench recursive repair discipline across "
    "research, coding, browser, and paid-work lanes as review-gated action."
)
DRESS_REHEARSAL_PRIORITY = (
    "Dress rehearsal first: coherent AI expert behavior, Telegram/source missions through the "
    "Tris bridge, NemoClaw/OpenClaw worker receipt as the next autonomy gate, and no fake "
    "external action claims."
)
DRESS_REHEARSAL_NEXT_GATE = (
    "Run the first live Telegram/OpenClaw phone mission through the field-mission bridge, "
    "save the source receipt, then demonstrate chat coherence, benchmark foundation, and "
    "relationship draft mode without sending or spending."
)
RECURSIVE_OPERATING_DISCIPLINE = (
    "Use the SWE-bench-proven recursive loop as task discipline: read the exact source, "
    "state the smallest next action, separate evidence from inference, preflight before "
    "claiming, repair failures from receipts, save JSON/Markdown traces, then scale only "
    "after the clean gate passes."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _safe_read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def append_memory(kind: str, content: str, payload: dict[str, Any] | None = None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": utc_now(),
        "kind": kind,
        "content": content,
        "payload": payload or {},
    }
    with PERSISTENT_MEMORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _default_project_state() -> dict[str, Any]:
    return {
        "name": "Trismegistus",
        "mission": DRESS_REHEARSAL_MISSION,
        "priority": DRESS_REHEARSAL_PRIORITY,
        "next_gate": DRESS_REHEARSAL_NEXT_GATE,
        "lanes": [
            {
                "id": "runtime",
                "name": "NemoHermes / OpenClaw runtime",
                "status": "next-autonomy-gate",
                "detail": "Telegram is live and model/bridge routes exist; the contest gate is a fresh NemoClaw/OpenClaw worker receipt.",
            },
            {
                "id": "golden_mark_cb5",
                "name": "Golden Mark / CB5 foundation",
                "status": "source-located",
                "detail": "Use C5B/late-band evidence and adapter gates as the stable-state reasoning foundation.",
            },
            {
                "id": "memory",
                "name": "Persistent memory",
                "status": "wired",
                "detail": "SQLite plus JSONL memory records hold runs, messages, events, project state, and next gates.",
            },
            {
                "id": "nest_lattice",
                "name": "Nest / Lattice curriculum",
                "status": "not-ingested",
                "detail": "Next RAG/SQL import lane: Lattice Companion / Universal Data Pattern field map.",
            },
            {
                "id": "jobs",
                "name": "Skill-to-paid-work lane",
                "status": "scout-live",
                "detail": "Wild Toads job scout stays as one proof lane for finding work the agent can complete.",
            },
            {
                "id": "agent_factory",
                "name": "Helper-agent factory",
                "status": "planned",
                "detail": "Trismegistus should propose scout, evaluator, proposal, code-fix, research, and memory agents.",
            },
            {
                "id": "benchmark_foundation",
                "name": "Benchmark foundation",
                "status": "swe-parked-webarena-ready",
                "detail": "SWE-bench local official selected-test foundation is parked pending hosted/maintainer response; its recursive inspect-preflight-repair-receipt loop is now promoted as Tris task discipline. WebArena hard receipt is public-ready with documented final-row boundaries; GAIA remains HF-gated.",
            },
            {
                "id": "recursive_repair_discipline",
                "name": "Recursive repair discipline",
                "status": "active-operating-spine",
                "detail": RECURSIVE_OPERATING_DISCIPLINE,
            },
            {
                "id": "voice",
                "name": "Voice / vocal chain",
                "status": "talkback-wired",
                "detail": "Browser mic input and macOS Samantha talkback are wired; full Home Node Whisper loop remains a next gate.",
            },
        ],
    }


def _upsert_lane(state: dict[str, Any], lane: dict[str, Any]) -> bool:
    lanes = state.setdefault("lanes", [])
    for index, existing in enumerate(lanes):
        if existing.get("id") == lane.get("id"):
            if existing != lane:
                lanes[index] = lane
                return True
            return False
    lanes.append(lane)
    return True


def ensure_project_state() -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state = _safe_read_json(PROJECT_STATE_PATH)
    if state:
        changed = False
        for key, value in (
            ("mission", DRESS_REHEARSAL_MISSION),
            ("priority", DRESS_REHEARSAL_PRIORITY),
            ("next_gate", DRESS_REHEARSAL_NEXT_GATE),
        ):
            if state.get(key) != value:
                state[key] = value
                changed = True
        changed = _upsert_lane(
            state,
            {
                "id": "runtime",
                "name": "NemoHermes / OpenClaw runtime",
                "status": "next-autonomy-gate",
                "detail": "Telegram is live and model/bridge routes exist; the contest gate is a fresh NemoClaw/OpenClaw worker receipt.",
            },
        ) or changed
        changed = _upsert_lane(
            state,
            {
                "id": "benchmark_foundation",
                "name": "Benchmark foundation",
                "status": "swe-parked-webarena-ready",
                "detail": "SWE-bench local official selected-test foundation is parked pending hosted/maintainer response; its recursive inspect-preflight-repair-receipt loop is now promoted as Tris task discipline. WebArena hard receipt is public-ready with documented final-row boundaries; GAIA remains HF-gated.",
            },
        ) or changed
        changed = _upsert_lane(
            state,
            {
                "id": "recursive_repair_discipline",
                "name": "Recursive repair discipline",
                "status": "active-operating-spine",
                "detail": RECURSIVE_OPERATING_DISCIPLINE,
            },
        ) or changed
        voice_detail = "Browser mic input and macOS Samantha talkback are wired; full Home Node Whisper loop remains a next gate."
        for lane in state.get("lanes", []):
            if lane.get("id") == "voice" and lane.get("detail") != voice_detail:
                lane["status"] = "talkback-wired"
                lane["detail"] = voice_detail
                changed = True
        if changed:
            state["updated_at"] = utc_now()
            PROJECT_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
        return state
    state = _default_project_state()
    state["created_at"] = utc_now()
    state["updated_at"] = state["created_at"]
    PROJECT_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    append_memory("project_state_initialized", "Trismegistus project spine initialized.", {"state_path": str(PROJECT_STATE_PATH)})
    return state


def golden_mark_status() -> dict[str, Any]:
    adapter_runs = list((GOLDEN_FIELD_ROOT / "runs" / "mlx").glob("*/adapter_config.json")) if GOLDEN_FIELD_ROOT.exists() else []
    result_cards = list((NOUS_EVAL_ROOT / "result_cards").glob("*.md")) if NOUS_EVAL_ROOT.exists() else []
    lateband = list((GOLDEN_FIELD_ROOT / "runs" / "mlx").glob("gm_lateband_lora_ablation_20260612_late2_iter30/*")) if GOLDEN_FIELD_ROOT.exists() else []
    return {
        "root": str(GOLDEN_FIELD_ROOT),
        "eval_root": str(NOUS_EVAL_ROOT),
        "source_found": GOLDEN_FIELD_ROOT.exists(),
        "evals_found": NOUS_EVAL_ROOT.exists(),
        "adapter_run_count": len(adapter_runs),
        "result_card_count": len(result_cards),
        "lateband_gate_found": bool(lateband),
        "active_gate": "GM-L31L32-MLP / GM-L31L32-MLP-O adapter-control ladder",
        "truth": "CB5/Golden Mark evidence is located; Trismegistus imports it as a foundation lane, not a completed self-training worker.",
    }


def voice_chain_status() -> dict[str, Any]:
    say_path = shutil.which("say")
    browser_lane = "ui-wired"
    talkback_status = "wired" if say_path else "missing-say"
    return {
        "home_node_root": str(HOME_NODE_ROOT),
        "home_node_smoke": str(HOME_NODE_SMOKE),
        "mirror_vocal_lab": str(MIRROR_VOCAL_LAB),
        "home_node_notes_found": HOME_NODE_ROOT.exists(),
        "home_node_smoke_found": HOME_NODE_SMOKE.exists(),
        "mirror_vocal_lab_found": MIRROR_VOCAL_LAB.exists(),
        "pyttsx3_available": _module_available("pyttsx3"),
        "speech_recognition_available": _module_available("speech_recognition"),
        "macos_say_path": say_path,
        "macos_say_talkback": talkback_status,
        "browser_voice_runtime": browser_lane,
        "truth": (
            "Home Node voice sources are located. Trismegistus now has browser mic input and "
            "macOS Samantha talkback; full Home Node Whisper/Gradio voice loop is still a next gate."
        ),
    }


def memory_status() -> dict[str, Any]:
    db.init_db()
    project = ensure_project_state()
    return {
        "project": project,
        "project_state_path": str(PROJECT_STATE_PATH),
        "json_memory_path": str(PERSISTENT_MEMORY_PATH),
        "json_memory_exists": PERSISTENT_MEMORY_PATH.exists(),
        "json_memory_entries": _count_jsonl(PERSISTENT_MEMORY_PATH),
        "sqlite_path": str(db.DB_PATH),
        "sqlite_exists": db.DB_PATH.exists(),
        "langchain_available": _module_available("langchain"),
        "langgraph_available": _module_available("langgraph"),
        "rag_status": db.rag_status(),
        "lattice_companion_url": LATTICE_COMPANION_URL,
        "golden_mark": golden_mark_status(),
        "mirror_checkpoints": mirror_checkpoint_status(),
        "voice_chain": voice_chain_status(),
    }
