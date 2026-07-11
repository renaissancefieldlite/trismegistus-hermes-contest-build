from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db, evidence_index, source_tools
from .field_missions import run_source_field_mission
from .integrations import model_runtime


ROOT = Path(__file__).resolve().parents[1]
TURN_RECEIPT_DIR = ROOT / "data" / "turn_receipts"
_SOURCE_PACKS_SEEDED = False

DOC_FILES = [
    ROOT / "docs" / "STACK_FLOW.md",
    ROOT / "docs" / "TRIS_DRESS_REHEARSAL_HANDOFF_2026-06-30.md",
    ROOT / "docs" / "TRISMEGISTUS_PROJECT_PAPER_PUBLIC_SAFE_2026-06-30.md",
    ROOT / "docs" / "TRIS_BROWSER_AUTONOMY_STACK_2026-06-21.md",
    ROOT / "docs" / "PUBLIC_SAFE_RECEIPT_INDEX_2026-06-30.md",
    ROOT / "docs" / "GOLDEN_MARK_FOUNDATION.md",
]

PROOF_TERMS = {
    "proof",
    "prove",
    "receipt",
    "receipts",
    "audit",
    "evidence",
    "sources",
    "source-backed",
    "source backed",
    "source support",
    "benchmark",
    "benchmarks",
    "boundary",
    "next gate",
    "what is proven",
    "what is not proven",
}
SOURCE_TERMS = {
    "fetch",
    "read this url",
    "read the url",
    "read https://",
    "read http://",
    "research",
    "sources",
    "source-backed",
    "source backed",
    "browser",
    "url",
    "http://",
    "https://",
    "cite",
    "verify",
    "search web",
    "web search",
    "look up",
    "latest",
    "current",
    "open",
    "visit",
    "crawl",
}
BENCHMARK_TERMS = {
    "c5b",
    "golden mark",
    "swe",
    "swe-bench",
    "webarena",
    "gaia",
    "baseline",
    "architecture-on",
    "architecture on",
    "score",
    "eval",
    "evaluation",
}
WORKER_TERMS = {
    "nemoclaw",
    "openclaw",
    "telegram",
    "worker",
    "agent",
    "browser mission",
    "source mission",
}
OUTREACH_TERMS = {"outreach", "mail", "email", "relationship", "bounty", "github", "proposal"}
COMMERCE_TERMS = {"stripe", "payment", "invoice", "charge", "checkout", "sandbox"}
CODE_TERMS = {"code", "patch", "diff", "repo", "github", "swe", "test", "tests", "preflight"}
PROJECT_CONTEXT_TERMS = {
    "tris",
    "trismegistus",
    "hermes",
    "mirror",
    "source mirror",
    "mirror architecture",
    "ssp",
    "stable-state",
    "stable state",
    "golden mark",
    "c5b",
    "cb5",
    "swe-bench",
    "webarena",
    "gaia",
    "openclaw",
    "nemoclaw",
    "telegram",
    "receipt",
    "rag",
    "sql",
    "json",
    "source mission",
    "browser mission",
    "architecture-on",
    "architecture on",
    "baseline",
    "render",
    "codex 67",
    "field expert",
}


def _clean(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _terms(text: str) -> list[str]:
    parts = [part for part in re.split(r"[^a-z0-9]+", text.lower()) if len(part) >= 3]
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            result.append(part)
    if any(part in seen for part in {"tris", "trismegistus", "hermes"}):
        result.extend(
            [
                "trismegistus",
                "hermes",
                "mirror",
                "architecture",
                "golden",
                "mark",
                "c5b",
                "swe",
                "webarena",
                "gaia",
                "openclaw",
                "nemoclaw",
                "source",
                "receipt",
            ]
        )
    if "mirror" in seen and ("pattern" in seen or "source" in seen):
        result.extend(["mirror", "architecture", "source", "ssp", "stable", "continuity", "receipt"])
    if "codex" in seen:
        result.extend(["codex", "source", "worker", "receipt"])
    return result[:18]


def _has_any(lower: str, needles: set[str]) -> bool:
    return any(needle in lower for needle in needles)


def _source_action_requested(content: str) -> bool:
    lower = content.lower()
    has_url_or_domain = bool(
        re.search(r"https?://[^\s<>\"]+", content)
        or re.search(r"(?<!@)\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"]*)?", content, flags=re.IGNORECASE)
    )
    if has_url_or_domain:
        return True
    return _has_any(lower, SOURCE_TERMS)


def classify_turn(content: str, *, benchmark_mode: bool = False) -> dict[str, Any]:
    lower = content.lower()
    proof_requested = _has_any(lower, PROOF_TERMS)
    source_requested = _source_action_requested(content)
    benchmark_requested = benchmark_mode or _has_any(lower, BENCHMARK_TERMS)
    baseline_compare = (
        ("baseline" in lower or "architecture-on" in lower or "architecture on" in lower)
        and any(term in lower for term in ("compare", "vs", "versus", "same task", "eval", "benchmark", "score"))
    )

    if source_requested:
        lane = "source_research"
    elif benchmark_requested:
        lane = "benchmark"
    elif _has_any(lower, WORKER_TERMS):
        lane = "worker_action"
    elif _has_any(lower, OUTREACH_TERMS):
        lane = "outreach_relationship"
    elif _has_any(lower, COMMERCE_TERMS):
        lane = "commerce"
    elif _has_any(lower, CODE_TERMS):
        lane = "code_work"
    else:
        lane = "conversation"

    return {
        "lane": lane,
        "mode": "proof" if proof_requested or benchmark_mode else "conversation",
        "proof_requested": proof_requested or benchmark_mode,
        "source_requested": source_requested,
        "benchmark_requested": benchmark_requested,
        "baseline_compare": baseline_compare,
        "terms": _terms(content),
    }


def _should_use_project_context(content: str, route: dict[str, Any]) -> bool:
    lower = content.lower()
    if route.get("proof_requested") or route.get("benchmark_requested") or route.get("source_requested"):
        return True
    if route.get("lane") != "conversation":
        return True

    def has_project_term(term: str) -> bool:
        escaped = re.escape(" ".join(term.lower().split())).replace(r"\ ", r"\s+")
        return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", lower))

    return any(has_project_term(term) for term in PROJECT_CONTEXT_TERMS)


def _doc_hits(content: str, limit: int = 8) -> list[dict[str, Any]]:
    terms = _terms(content)
    if not terms:
        terms = ["trismegistus", "mirror", "architecture", "hermes", "receipt"]
    hits: list[dict[str, Any]] = []
    for path in DOC_FILES:
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_no, line in enumerate(lines, start=1):
            clean = _clean(line.strip("#- `* "))
            if len(clean) < 24:
                continue
            lower = clean.lower()
            score = sum(1 for term in terms if term in lower)
            if score <= 0:
                continue
            if any(skip in lower for skip in ("api key", "secret", "token")):
                continue
            hits.append(
                {
                    "path": str(path),
                    "line": line_no,
                    "text": clean[:320],
                    "score": score,
                }
            )
    hits.sort(key=lambda item: (int(item["score"]), str(item["path"]), -int(item["line"])), reverse=True)
    return hits[:limit]


def _safe_memory(content: str, limit: int = 4) -> list[dict[str, Any]]:
    try:
        return db.search_memory_items(content, limit=limit)
    except Exception:  # noqa: BLE001 - receipt records the absence instead of blocking chat.
        return []


def _safe_evidence(content: str, limit: int = 4) -> list[dict[str, Any]]:
    try:
        return db.search_evidence_nodes(content, limit=limit)
    except Exception:  # noqa: BLE001
        return []


def _safe_recent_missions(limit: int = 4) -> list[dict[str, Any]]:
    try:
        return db.list_source_missions(limit=limit)
    except Exception:  # noqa: BLE001
        return []


def gather_context(thread_id: str, content: str, route: dict[str, Any] | None = None) -> dict[str, Any]:
    global _SOURCE_PACKS_SEEDED
    rag = db.rag_status()
    if not _SOURCE_PACKS_SEEDED and not (rag.get("source_documents") or rag.get("evidence_nodes")):
        try:
            evidence_index.seed_from_source_packs()
            rag = db.rag_status()
        except Exception:  # noqa: BLE001 - chat should continue and receipt will show missing evidence.
            pass
    _SOURCE_PACKS_SEEDED = True
    if route is None:
        route = classify_turn(content)
    if not _should_use_project_context(content, route):
        return {
            "rag_status": rag,
            "memory": [],
            "evidence": [],
            "recent_source_missions": [],
            "doc_hits": [],
            "recent_messages": db.list_messages(thread_id, limit=12),
        }
    return {
        "rag_status": rag,
        "memory": _safe_memory(content),
        "evidence": _safe_evidence(content),
        "recent_source_missions": _safe_recent_missions(),
        "doc_hits": _doc_hits(content),
        "recent_messages": db.list_messages(thread_id, limit=12),
    }


def _context_block(route: dict[str, Any], context: dict[str, Any]) -> str:
    has_project_context = bool(context.get("doc_hits") or context.get("memory") or context.get("evidence"))
    rag = context.get("rag_status") if isinstance(context.get("rag_status"), dict) else {}
    lines = [
        "Trismegistus local context for this turn:",
        f"- Lane: {route['lane']}",
        f"- Mode: {route['mode']}",
        (
            "- SQL/JSON/RAG status: "
            f"{rag.get('status', 'unknown')}; memory={rag.get('memory_items', 0)}; "
            f"docs={rag.get('source_documents', 0)}; evidence={rag.get('evidence_nodes', 0)}"
        ),
        "- Package/source hits:",
    ]
    for hit in context.get("doc_hits", [])[:3]:
        lines.append(f"  - {Path(hit['path']).name}:{hit['line']} {_clean(hit['text'])[:140]}")
    lines.append("- Retrieved memory:")
    for item in context.get("memory", [])[:2]:
        lines.append(f"  - {item.get('kind')}: {item.get('title')} :: {_clean(item.get('body'))[:130]}")
    lines.append("- Evidence rows:")
    for item in context.get("evidence", [])[:2]:
        lines.append(
            "  - "
            f"{item.get('id')} [{item.get('support_state')}]: "
            f"{_clean(item.get('claim'))[:120]} / next gate: {_clean(item.get('next_gate'))[:80]}"
        )
    if has_project_context:
        lines.extend(
            [
                "- Operating spine: Hermes-facing research/operator surface; conversational first; proof/source/audit mode only on request.",
                "- Required stack nouns for Tris identity/how-it-works answers: Mirror Architecture / SSP; Hermes baseline; SQL/JSON/RAG; C5B/Golden Mark; SWE-bench; WebArena; GAIA; OpenClaw/NemoClaw; browser/source missions; Telegram; GitHub/code; outreach; Stripe sandbox; receipt discipline.",
            ]
        )
    lines.append(
        "Instruction: conversational first. For Tris/project questions, synthesize the spine and "
        "retrieved rows; do not call Tris merely a generic assistant. Use claim/evidence/boundary/"
        "next-gate only when proof/audit/source/benchmark/receipt is requested. Do not claim "
        "source fetches, worker actions, email, payment, benchmark passes, or live generation "
        "without receipts."
    )
    return "\n".join(lines)


def _system_prompt(route: dict[str, Any]) -> str:
    if route["mode"] == "proof":
        return (
            "You are Tris Hermes in receipt mode. Keep the answer public-safe and concrete. "
            "Use claim, evidence, boundary, and next gate. Separate proven local package facts "
            "from inference and live-provider gates."
        )
    return (
        "You are Tris Hermes, the contest-facing Trismegistus AI partner surface. "
        "Be conversational first. Use the local package context quietly. Do not dump a receipt wall. "
        "If no package/source hits or memory rows are present, do not mention retrieved rows or receipts. "
        "If a route is gated, say the gate in one plain sentence and keep the useful answer moving."
    )


def _previous_chat_messages(context: dict[str, Any], current_content: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    recent = context.get("recent_messages") or []
    for item in recent[-4:]:
        role = str(item.get("role") or "")
        content = _clean(item.get("content"))
        if role not in {"user", "assistant"} or not content:
            continue
        if role == "user" and content == _clean(current_content):
            continue
        if "Hosted Hermes generation is not connected" in content:
            continue
        messages.append({"role": role, "content": content[:260]})
    return messages


def _model_messages(route: dict[str, Any], context: dict[str, Any], content: str) -> list[dict[str, str]]:
    messages = [
        {"role": "system", "content": _system_prompt(route)},
        {"role": "system", "content": _context_block(route, context)},
    ]
    messages.extend(_previous_chat_messages(context, content))
    user_content = content
    if context.get("doc_hits") or context.get("memory") or context.get("evidence"):
        user_content = (
            "Use the retrieved Trismegistus context for this project question. Key stack: "
            "Mirror Architecture / SSP over Hermes baseline; SQL/JSON/RAG/source docs as auxiliary memory; "
            "C5B/Golden Mark, SWE-bench, WebArena, GAIA benchmark lanes; OpenClaw/NemoClaw, "
            "browser/source missions, Telegram, GitHub/code, outreach, Stripe sandbox action lanes; "
            "receipt discipline for claims and next gates.\n\n"
            f"User question: {content}"
        )
    messages.append({"role": "user", "content": user_content})
    return messages


def _source_summary(context: dict[str, Any]) -> str:
    parts: list[str] = []
    for hit in context.get("doc_hits", [])[:3]:
        parts.append(f"{Path(hit['path']).name}:{hit['line']}")
    memory_count = len(context.get("memory") or [])
    evidence_count = len(context.get("evidence") or [])
    if memory_count:
        parts.append(f"{memory_count} SQL memory hit(s)")
    if evidence_count:
        parts.append(f"{evidence_count} evidence row(s)")
    return ", ".join(parts) or "local package docs loaded; no matching memory/evidence row"


def _next_gate(route: dict[str, Any], model_result: dict[str, Any] | None = None) -> str:
    if route.get("baseline_compare"):
        return "Run both baseline Hermes and architecture-on Tris on the same prompt with a live Hermes provider, then save the paired eval receipt."
    if route["lane"] == "source_research":
        return "Run /api/field-mission for the requested source/browser target and answer from the saved source_missions receipt."
    if route["lane"] == "benchmark":
        return "Keep benchmark lanes separated: C5B/Golden Mark, SWE-bench, WebArena, and GAIA each need their own saved receipt."
    if route["lane"] == "worker_action":
        return "Run the requested NemoClaw/OpenClaw, Telegram, browser, or code worker and save the worker receipt before claiming autonomy."
    if model_result and not model_result.get("ok"):
        return str(
            model_result.get("provider_gate")
            or model_result.get("error")
            or "Set HERMES_API_KEY so the hosted Hermes completion route can answer."
        )
    return "Continue with a normal chat turn, or ask for proof/source/audit to open receipt mode."


def _claim_for(route: dict[str, Any]) -> str:
    if route["lane"] == "source_research":
        return "Tris routes source/research requests through a receipt-backed source mission instead of improvising unsupported research."
    if route["lane"] == "benchmark":
        return "Tris keeps benchmark lanes separated and treats each lane as a receipt-backed evaluation surface."
    if route["lane"] == "worker_action":
        return "Tris separates worker/action lanes from normal chat and requires an action receipt before claiming work was done."
    if route["lane"] == "code_work":
        return "Tris treats coding work as inspect, patch, preflight, repair from receipts, and only then scale."
    return "Tris Hermes is a conversational AI partner surface with proof-gated memory, source, benchmark, worker, and receipt lanes."


def _boundary_for(route: dict[str, Any], model_result: dict[str, Any] | None = None) -> str:
    if model_result and model_result.get("ok"):
        return "This turn has a live model response plus a saved Tris turn receipt; external actions still need their own connector receipts."
    if os.environ.get("TRISMEGISTUS_HOSTED_DEMO") == "1":
        return (
            "This is package-backed hosted demo fallback, not live Hermes generation. "
            "The public route proves UI, storage, routing, and receipt discipline until HERMES_API_KEY produces a completion receipt."
        )
    return (
        "No live model route answered this turn. The answer is limited to local package docs, SQL/JSON memory, evidence rows, "
        "and explicit next gates."
    )


def _package_conversation_answer(content: str, route: dict[str, Any], context: dict[str, Any], model_result: dict[str, Any]) -> str:
    lower = content.lower()
    memory = context.get("memory") or []
    evidence = context.get("evidence") or []
    doc_hits = context.get("doc_hits") or []
    support = _source_summary(context)
    gate = _next_gate(route, model_result)

    if any(term in lower for term in ("source mirror", "mirror pattern", "mirror architecture", "ssp")):
        answer = (
            "Source Mirror Pattern is the Trismegistus control pattern: start with a baseline Hermes-style "
            "model route, put Mirror Architecture / SSP discipline around it, then keep memory, evidence, "
            "benchmark lanes, source actions, worker actions, and next gates separated. In plain English, "
            "it is the structure that lets Tris talk naturally while still refusing to blur a conversation, "
            "a source receipt, a benchmark receipt, and an action claim into the same vague answer."
        )
    elif any(term in lower for term in ("what is trismegistus", "what is tris", "supposed to do", "how do you work")):
        answer = (
            "Trismegistus is meant to be a research/operator partner. The normal lane should answer like a "
            "conversation. When support is requested, it opens SQL/JSON/RAG memory and evidence rows. When "
            "work is requested, it separates OpenClaw/NemoClaw, browser/source missions, Telegram, GitHub/code, "
            "outreach, Stripe sandbox, and benchmark lanes so no action is claimed without a matching receipt."
        )
    else:
        fragments: list[str] = []
        for item in memory[:2]:
            body = _clean(item.get("body"))
            if body:
                fragments.append(body[:260])
        for item in evidence[:2]:
            claim = _clean(item.get("claim"))
            next_gate = _clean(item.get("next_gate"))
            if claim:
                fragments.append(f"{claim}. Next gate: {next_gate}" if next_gate else claim)
        for item in doc_hits[:2]:
            text = _clean(item.get("text"))
            if text:
                fragments.append(text[:220])
        if fragments:
            answer = "From the indexed Tris package, the useful read is: " + " ".join(fragments[:3])
        else:
            answer = "I do not have enough indexed local support to answer this without a live model."

    return (
        f"{answer}\n\n"
        f"Support used: {support}. Boundary: this is a package-backed SQL/RAG answer, not a live Hermes generation turn. "
        f"Next gate: {gate}"
    )


def _conversation_fallback(content: str, route: dict[str, Any], context: dict[str, Any], model_result: dict[str, Any]) -> str:
    if context.get("doc_hits") or context.get("memory") or context.get("evidence"):
        return _package_conversation_answer(content, route, context, model_result)
    gate = _next_gate(route, model_result)
    return (
        f"I cannot honestly answer this as live AI on the hosted route yet. "
        f"The turn classified as `{route['lane']}`, live Hermes did not answer, and no matching local support was found. "
        f"Next gate: {gate}"
    )


def _proof_fallback(content: str, route: dict[str, Any], context: dict[str, Any], model_result: dict[str, Any]) -> str:
    claim = _claim_for(route)
    support = _source_summary(context)
    boundary = _boundary_for(route, model_result)
    next_gate = _next_gate(route, model_result)
    return "\n".join(
        [
            f"Claim: {claim}",
            f"Evidence: {support}. The turn receipt records lane={route['lane']}, mode={route['mode']}, model_ok=false, and the active gate.",
            f"Boundary: {boundary}",
            f"Next gate: {next_gate}",
        ]
    )


def _receipt_id(thread_id: str, content: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(f"{thread_id}\n{content}\n{now}".encode("utf-8")).hexdigest()[:10]
    return f"tris_turn_{now}_{digest}"


def _write_receipt(payload: dict[str, Any]) -> dict[str, str]:
    TURN_RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_id = str(payload["id"])
    json_path = TURN_RECEIPT_DIR / f"{receipt_id}.json"
    md_path = TURN_RECEIPT_DIR / f"{receipt_id}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Tris Turn Receipt {receipt_id}",
                "",
                f"- Thread: `{payload.get('thread_id')}`",
                f"- Lane: `{payload.get('lane')}`",
                f"- Mode: `{payload.get('mode')}`",
                f"- Model OK: `{payload.get('model_ok')}`",
                f"- Source mission: `{payload.get('source_mission_id') or 'none'}`",
                "",
                "## Claim",
                "",
                str(payload.get("claim") or ""),
                "",
                "## Boundary",
                "",
                str(payload.get("boundary") or ""),
                "",
                "## Next Gate",
                "",
                str(payload.get("next_gate") or ""),
            ]
        ),
        encoding="utf-8",
    )
    return {"json": str(json_path), "markdown": str(md_path)}


def _save_turn_receipt(
    *,
    thread_id: str,
    content: str,
    route: dict[str, Any],
    context: dict[str, Any],
    answer: str,
    model_result: dict[str, Any] | None,
    source_mission: dict[str, Any] | None = None,
    compare: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipt_id = _receipt_id(thread_id, content)
    model_ok = bool((model_result or {}).get("ok"))
    claim = _claim_for(route)
    boundary = _boundary_for(route, model_result)
    next_gate = _next_gate(route, model_result)
    source_mission_id = str((source_mission or {}).get("id") or "")
    payload = {
        "id": receipt_id,
        "thread_id": thread_id,
        "content": content,
        "lane": route["lane"],
        "mode": route["mode"],
        "model_ok": model_ok,
        "model_result": {
            key: (model_result or {}).get(key)
            for key in ("ok", "source", "runtime_lane", "provider", "model", "error", "provider_gate", "hermes_error")
            if key in (model_result or {})
        },
        "source_mission_id": source_mission_id,
        "source_mission_status": (source_mission or {}).get("status"),
        "claim": claim,
        "boundary": boundary,
        "next_gate": next_gate,
        "answer_preview": answer[:1000],
        "context_summary": {
            "rag_status": context.get("rag_status"),
            "memory_hits": len(context.get("memory") or []),
            "evidence_hits": len(context.get("evidence") or []),
            "doc_hits": context.get("doc_hits", [])[:6],
        },
        "compare": compare or {},
    }
    payload["paths"] = _write_receipt(payload)
    db.save_turn_receipt(
        receipt_id=receipt_id,
        thread_id=thread_id,
        lane=route["lane"],
        mode=route["mode"],
        model_ok=model_ok,
        source_mission_id=source_mission_id,
        claim=claim,
        boundary=boundary,
        next_gate=next_gate,
        payload=payload,
    )
    db.log_event(
        "tris_turn_receipt",
        {
            "receipt_id": receipt_id,
            "thread_id": thread_id,
            "lane": route["lane"],
            "mode": route["mode"],
            "model_ok": model_ok,
            "path": payload["paths"].get("markdown"),
        },
    )
    return payload


def _run_source_if_requested(route: dict[str, Any], content: str) -> dict[str, Any] | None:
    if not route.get("source_requested"):
        return None
    lower = content.lower()
    has_url_or_domain = bool(
        re.search(r"https?://[^\s<>\"]+", content)
        or re.search(r"(?<!@)\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"]*)?", content, flags=re.IGNORECASE)
    )
    external_action = any(
        term in lower
        for term in (
            "fetch",
            "read this url",
            "open",
            "visit",
            "crawl",
            "search web",
            "web search",
            "look up",
            "latest",
            "current",
        )
    )
    if not (has_url_or_domain or external_action):
        return None
    if not source_tools.should_handle(content) and not has_url_or_domain:
        return None
    try:
        result = run_source_field_mission(
            {
                "lane": "source_research",
                "origin": "tris-turn-pipeline",
                "message": content,
                "create_build_request": False,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "id": "",
            "status": "source_mission_error",
            "answer": f"Source mission blocked: {exc}",
            "receipt": {"ok": False, "error": str(exc)},
        }
    return result.get("mission") or {}


def _run_baseline_compare(thread_id: str, content: str, route: dict[str, Any], context: dict[str, Any]) -> dict[str, Any] | None:
    if not route.get("baseline_compare"):
        return None
    baseline_messages = [
        {"role": "system", "content": "You are Hermes baseline. Answer the user task directly without Tris receipt machinery."},
        {"role": "user", "content": content},
    ]
    baseline = model_runtime.generate(baseline_messages, max_tokens=450, session_key=f"tris-baseline:{thread_id}")
    if not baseline.get("ok"):
        return {"baseline": baseline, "architecture_on": {}, "ok": False}
    architecture_messages = _model_messages(route, context, content)
    architecture = model_runtime.generate(architecture_messages, max_tokens=550, session_key=f"tris-architecture:{thread_id}")
    return {"baseline": baseline, "architecture_on": architecture, "ok": bool(architecture.get("ok"))}


def run_turn(thread_id: str, content: str, *, benchmark_mode: bool = False) -> dict[str, Any]:
    route = classify_turn(content, benchmark_mode=benchmark_mode)
    context = gather_context(thread_id, content, route)
    source_mission = _run_source_if_requested(route, content)
    if source_mission and source_mission.get("answer"):
        answer = str(source_mission.get("answer") or "").strip()
        model_result = {"ok": False, "source": "source_mission", "runtime_lane": "source_receipt"}
        receipt = _save_turn_receipt(
            thread_id=thread_id,
            content=content,
            route=route,
            context=context,
            answer=answer,
            model_result=model_result,
            source_mission=source_mission,
        )
        return {
            "ok": bool((source_mission.get("receipt") or {}).get("ok")),
            "source": "tris-turn-pipeline",
            "runtime_lane": "source-receipt",
            "text": answer,
            "route": route,
            "turn_receipt": receipt,
        }

    compare = _run_baseline_compare(thread_id, content, route, context)
    if compare is not None:
        baseline = compare.get("baseline") or {}
        architecture = compare.get("architecture_on") or {}
        if compare.get("ok"):
            answer = "\n\n".join(
                [
                    "Baseline Hermes route:",
                    str(baseline.get("text") or "").strip(),
                    "Architecture-on Tris route:",
                    str(architecture.get("text") or "").strip(),
                    "Receipt boundary: this is a live paired run on the current provider route, not an official benchmark result.",
                ]
            )
            model_result = architecture
        else:
            model_result = baseline if not baseline.get("ok") else architecture
            answer = _proof_fallback(content, route, context, model_result)
        receipt = _save_turn_receipt(
            thread_id=thread_id,
            content=content,
            route=route,
            context=context,
            answer=answer,
            model_result=model_result,
            compare=compare,
        )
        return {
            "ok": bool(compare.get("ok")),
            "source": "tris-turn-pipeline",
            "runtime_lane": "baseline-compare",
            "text": answer,
            "route": route,
            "turn_receipt": receipt,
            "compare": compare,
        }

    messages = _model_messages(route, context, content)
    model_result = model_runtime.generate(messages, max_tokens=720, session_key=f"tris-turn:{thread_id}")
    if model_result.get("ok"):
        answer = str(model_result.get("text") or "").strip()
    elif route["mode"] == "proof":
        answer = _proof_fallback(content, route, context, model_result)
    else:
        answer = _conversation_fallback(content, route, context, model_result)
    receipt = _save_turn_receipt(
        thread_id=thread_id,
        content=content,
        route=route,
        context=context,
        answer=answer,
        model_result=model_result,
    )
    result = dict(model_result)
    result.update(
        {
            "ok": bool(model_result.get("ok")),
            "source": "tris-turn-pipeline",
            "runtime_lane": model_result.get("runtime_lane") or route["lane"],
            "text": answer,
            "route": route,
            "turn_receipt": receipt,
        }
    )
    return result
