from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db, project_memory, source_tools


ROOT = Path(__file__).resolve().parents[1]
MISSION_DIR = ROOT / "data" / "field_missions"


def _run_id(prefix: str) -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ%f')}"


def _clean(text: Any, fallback: str = "") -> str:
    return " ".join(str(text or fallback).split()).strip()


def _status_for_receipt(receipt: dict[str, Any]) -> str:
    if receipt.get("ok"):
        return "source_receipt_ready"
    if receipt.get("partial_ok"):
        return "partial_source_receipt_ready"
    return "needs_codex_or_tool_upgrade"


_BROWSER_SOURCE_TERMS = (
    "live site",
    "live sites",
    "live source",
    "source sequence",
    "browser sequence",
    "browser mission",
    "browser stack",
    "playwright",
    "cdp",
    "nvidia quantum",
    "quantum partner",
    "quantum partners",
    "quantum companies",
    "quantum research",
    "nous careers",
    "nous research careers",
    "renaissance field lite",
    "rfl public",
    "webarena baseline",
    "webarena map",
)

_BROWSER_ACTION_TERMS = (
    "run",
    "fetch",
    "read",
    "source",
    "research",
    "sweep",
    "go",
    "open",
    "visit",
    "check",
    "verify",
    "mission",
    "sequence",
    "crawl",
    "test",
)


def _wants_browser_source_sequence(request: str) -> bool:
    lower = request.lower()
    return any(term in lower for term in _BROWSER_SOURCE_TERMS) and any(
        term in lower for term in _BROWSER_ACTION_TERMS
    )


def _wants_saved_source_rows(request: str) -> bool:
    lower = request.lower()
    row_terms = (
        "source entity",
        "source entities",
        "company row",
        "company rows",
        "companies loaded",
        "partner row",
        "partner rows",
        "relationship draft",
        "relationship drafts",
        "margin row",
        "margin rows",
        "margin score",
        "margin scores",
        "margin scoring",
    )
    return any(term in lower for term in row_terms)


def _first_stdout_value(stdout: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.+)$", stdout, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _browser_sequence_receipt(result: dict[str, Any], request: str) -> dict[str, Any]:
    stdout = str(result.get("stdout") or "")
    paths = result.get("paths") or {}
    return {
        "ok": bool(result.get("ok")),
        "partial_ok": bool(result.get("partial_ok")),
        "source": "tris-live-site-sequence",
        "kind": "browser-live-source-sequence",
        "request": request,
        "loaded": result.get("loaded") or _first_stdout_value(stdout, "Loaded"),
        "sequence_ok": result.get("sequence_ok"),
        "results": result.get("results") or [],
        "paths": paths,
        "returncode": result.get("returncode"),
        "latency_ms": result.get("latency_ms"),
        "stderr": str(result.get("stderr") or "")[:1200],
        "stdout_preview": stdout[:1600],
        "boundary": (
            "This is a browser/source intake mission with saved Playwright receipts. "
            "It is not outreach, a partner claim, a payment, or an application."
        ),
        "next_gate": (
            "Promote the read pages into Tris source/evidence tables, then run "
            "review-gated relationship draft missions."
        ),
    }


def _browser_sequence_answer(receipt: dict[str, Any]) -> str:
    paths = receipt.get("paths") or {}
    loaded = receipt.get("loaded") or "see saved receipt"
    request = str(receipt.get("request") or "").lower()
    results = receipt.get("results") or []
    labels = [str(item.get("label") or item.get("id") or "").strip() for item in results if item.get("ok")]
    nous = next((item for item in results if item.get("lane") == "nous_research_roles"), None)
    if not receipt.get("ok") and not receipt.get("partial_ok"):
        return "\n".join(
            [
                "I tried to run the live browser source sequence, but the browser worker did not complete.",
                "",
                f"Read: {loaded}",
                f"Error: {receipt.get('stderr') or 'No stderr captured.'}",
                f"Next gate: {receipt.get('next_gate')}",
            ]
        )
    if nous and ("role" in request or "career" in request or "fit" in request):
        lines = [
            "Clean read:",
            "For this build, the strongest immediate Nous fit is Forward Deployed Engineer: it maps to deploying and adapting Hermes-style agent infrastructure inside real environments.",
            "",
            "Research Scientist is the deeper arc because Tris is built around Mirror Architecture, Golden Mark/CB5 evidence, benchmark receipts, and cross-field research loops.",
            "Full Stack Engineer and Machine Learning Engineer are also adjacent build lanes, but FDE + Research Scientist best describe the contest narrative.",
            "",
            "Evidence:",
            f"Nous careers page loaded with status {nous.get('status')} and title {nous.get('title')}.",
        ]
        matched = []
        for check in nous.get("objective_checks", []):
            matched.extend(check.get("matched_terms") or [])
        if matched:
            lines.append(f"Matched terms: {', '.join(dict.fromkeys(matched))}.")
        if paths.get("markdown"):
            lines.append(f"Receipt: {paths.get('markdown')}")
        if paths.get("trace"):
            lines.append(f"Trace: {paths.get('trace')}")
        lines.extend(
            [
                "",
                "Boundary: source intake only. No application, outreach, or claim of fit was sent.",
                f"Next gate: {receipt.get('next_gate')}",
            ]
        )
        return "\n".join(lines)
    if receipt.get("partial_ok"):
        lines = [
            "Clean read:",
            "I ran the live browser source sequence through the Tris Playwright/CDP worker. One or more targets needs review, but the sequence produced a saved receipt.",
            "",
            f"Loaded: {loaded}",
        ]
    else:
        lines = [
            "Clean read:",
            "I ran the live browser source sequence through the Tris Playwright/CDP worker and saved the receipt.",
            "",
            f"Loaded: {loaded}",
        ]
    if labels:
        lines.extend(["", f"Sources checked: {', '.join(labels[:8])}."])
    if paths.get("markdown"):
        lines.append(f"Receipt: {paths.get('markdown')}")
    if paths.get("trace"):
        lines.append(f"Trace: {paths.get('trace')}")
    if paths.get("screenshot_dir"):
        lines.append(f"Screenshots: {paths.get('screenshot_dir')}")
    lines.extend(
        [
            "",
            "Boundary: source intake only. No outreach, partner claim, spend, or application happened.",
            f"Next gate: {receipt.get('next_gate')}",
        ]
    )
    return "\n".join(lines)


def create_codex_build_request(
    *,
    mission_id: str,
    title: str,
    evidence: str,
    requested_change: str,
    expected_tests: str,
    approval_state: str = "draft",
    implementation_receipt: str = "",
    memory_ingestion_status: str = "queued",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = _run_id("codex_build")
    packet = {
        "id": request_id,
        "mission_id": mission_id,
        "title": title,
        "evidence": evidence,
        "requested_change": requested_change,
        "expected_tests": expected_tests,
        "approval_state": approval_state,
        "implementation_receipt": implementation_receipt,
        "memory_ingestion_status": memory_ingestion_status,
        "payload": payload or {},
        "truth_boundary": (
            "This is a queued build request. Codex has not implemented it until "
            "an implementation receipt and passing test receipt are saved."
        ),
    }
    db.save_codex_build_request(
        request_id=request_id,
        mission_id=mission_id,
        title=title,
        evidence=evidence,
        requested_change=requested_change,
        expected_tests=expected_tests,
        approval_state=approval_state,
        implementation_receipt=implementation_receipt,
        memory_ingestion_status=memory_ingestion_status,
        payload=packet,
    )
    db.save_memory_item(
        "codex_build_request",
        f"codex_build_request:{request_id}",
        title,
        f"{evidence}\n\nRequested change:\n{requested_change}\n\nExpected tests:\n{expected_tests}",
        packet,
    )
    project_memory.append_memory(
        "codex_build_request",
        f"{title}\n\n{requested_change}",
        packet,
    )
    db.log_event(
        "codex_build_request_queued",
        {
            "request_id": request_id,
            "mission_id": mission_id,
            "approval_state": approval_state,
            "memory_ingestion_status": memory_ingestion_status,
        },
    )
    return packet


def run_source_field_mission(body: dict[str, Any]) -> dict[str, Any]:
    request = _clean(body.get("message") or body.get("query") or body.get("request"))
    if not request:
        raise ValueError("Missing field mission request.")
    lane = _clean(body.get("lane"), "source_research")
    origin = _clean(body.get("origin"), "tris-local")
    create_build_gap = bool(body.get("create_build_request"))
    mission_id = _run_id("field_mission")

    if _wants_saved_source_rows(request):
        receipt = source_tools.run(request)
        answer = source_tools.answer(receipt, request=request)
    elif _wants_browser_source_sequence(request):
        from .browser_missions import run_live_site_sequence

        receipt = _browser_sequence_receipt(run_live_site_sequence({}), request)
        answer = _browser_sequence_answer(receipt)
    else:
        receipt = source_tools.run(request)
        answer = source_tools.answer(receipt, request=request)
    status = _status_for_receipt(receipt)
    mission = {
        "id": mission_id,
        "lane": lane,
        "origin": origin,
        "request": request,
        "status": status,
        "answer": answer,
        "receipt": receipt,
        "codex_end_loop": "Codex is the helper-builder end loop after Tris finds a verified gap.",
    }
    MISSION_DIR.mkdir(parents=True, exist_ok=True)
    json_path = MISSION_DIR / f"{mission_id}.json"
    md_path = MISSION_DIR / f"{mission_id}.md"
    json_path.write_text(json.dumps(mission, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Field Mission {mission_id}",
                "",
                f"- Lane: `{lane}`",
                f"- Origin: `{origin}`",
                f"- Status: `{status}`",
                "",
                "## Request",
                "",
                request,
                "",
                "## Answer",
                "",
                answer,
                "",
                "## Truth Boundary",
                "",
                "This mission is a source/tool receipt. It is not an outbound action, application, payment, or public claim by itself.",
            ]
        ),
        encoding="utf-8",
    )
    mission["paths"] = {"json": str(json_path), "markdown": str(md_path)}

    db.save_source_mission(mission_id, lane, origin, request, status, mission)
    db.save_memory_item(
        "field_mission_receipt",
        f"field_mission:{mission_id}",
        f"{lane}: {request[:90]}",
        f"{request}\n\n{answer}",
        mission,
    )
    project_memory.append_memory("field_mission_receipt", f"{request}\n\n{answer}", mission)

    build_request = None
    if create_build_gap or (not receipt.get("ok") and not receipt.get("partial_ok")):
        build_request = create_codex_build_request(
            mission_id=mission_id,
            title=f"Upgrade field mission route: {lane}",
            evidence=(
                f"Field mission `{mission_id}` returned status `{status}` for request: {request}\n"
                f"Receipt ok: {bool(receipt.get('ok'))}\n"
                f"Receipt kind: {receipt.get('kind') or 'none'}"
            ),
            requested_change=(
                "Improve Trismegistus source/tool routing so this lane returns a "
                "receipt-backed answer from the correct source path without loose "
                "model improvisation."
            ),
            expected_tests=(
                "1. POST /api/field-mission with the same request returns ok=true "
                "or a specific source error.\n"
                "2. The mission is saved in source_missions.\n"
                "3. The mission is saved into memory_items and JSON memory.\n"
                "4. If routed through OpenClaw/Telegram, the reply answers from the receipt."
            ),
            payload={"mission": mission},
        )
    db.log_event(
        "field_mission",
        {
            "mission_id": mission_id,
            "lane": lane,
            "origin": origin,
            "status": status,
            "ok": bool(receipt.get("ok")),
            "build_request_id": (build_request or {}).get("id"),
        },
    )
    return {
        "ok": bool(receipt.get("ok")),
        "mission": mission,
        "build_request": build_request,
        "rag": db.rag_status(),
        "next_gate": "Route OpenClaw/Telegram research requests through /api/field-mission and answer from saved receipts.",
    }
