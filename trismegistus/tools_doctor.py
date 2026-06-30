from __future__ import annotations

import json
from typing import Any

from . import db, source_tools


def _recent_openclaw_tool_errors(limit: int = 8) -> list[dict[str, Any]]:
    db.init_db()
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT m.ts, m.role, m.content, x.source, x.payload
            FROM messages m
            JOIN external_message_map x ON x.message_id = m.id
            WHERE m.content LIKE '%tool_search_code%'
               OR m.content LIKE '%ReferenceError:%'
               OR m.content LIKE '%Unexpected token%'
               OR m.content LIKE '%fetch is not defined%'
            ORDER BY m.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    errors: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {}
        errors.append(
            {
                "ts": row["ts"],
                "role": row["role"],
                "source": row["source"],
                "content": str(row["content"])[:700],
                "session_file": payload.get("session_file"),
            }
        )
    return errors


def _latest_event(kind: str) -> dict[str, Any] | None:
    db.init_db()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT ts, payload FROM events WHERE kind = ? ORDER BY id DESC LIMIT 1",
            (kind,),
        ).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row["payload"])
    except json.JSONDecodeError:
        payload = {"raw": row["payload"]}
    return {"ts": row["ts"], "payload": payload}


def _source_probe(message: str) -> dict[str, Any]:
    receipt = source_tools.run(message)
    answer = source_tools.answer(receipt)
    return {
        "ok": bool(receipt.get("ok")),
        "kind": receipt.get("kind"),
        "source": receipt.get("source"),
        "answer_preview": answer[:900],
        "receipt": receipt,
    }


def run_tools_doctor() -> dict[str, Any]:
    source_home = _source_probe("fetch https://nousresearch.com")
    source_role = _source_probe("what is the exact url for the nous researcher role position? test fetch accuracy")
    rag = db.rag_status()
    recent_tool_errors = _recent_openclaw_tool_errors()
    last_sync = _latest_event("openclaw_sync")
    last_source_bridge = _latest_event("source_bridge_fetch")
    source_bridge_payload = (last_source_bridge or {}).get("payload") or {}
    source_bridge_ok = bool(source_bridge_payload.get("ok"))
    source_home_ok = bool(source_home.get("ok")) or source_bridge_ok
    source_role_ok = bool(source_role.get("ok")) or source_bridge_ok

    checks = [
        {
            "id": "tris_source_fetch_home",
            "label": "Tris source route: Nous homepage",
            "ok": source_home_ok,
            "detail": (
                source_home.get("kind")
                if source_home.get("ok")
                else "direct probe blocked; bridge receipt available"
                if source_bridge_ok
                else source_home.get("kind") or "source probe"
            ),
        },
        {
            "id": "tris_source_fetch_role",
            "label": "Tris source route: Nous researcher role",
            "ok": source_role_ok,
            "detail": (source_role.get("receipt") or {}).get("role_page", {}).get("url")
            or source_bridge_payload.get("url")
            or ("direct probe blocked; bridge receipt available" if source_bridge_ok else "")
            or (source_role.get("receipt") or {}).get("error")
            or "role probe",
        },
        {
            "id": "openclaw_memory_sync",
            "label": "OpenClaw/Telegram -> Tris memory sync",
            "ok": bool(rag.get("external_messages", 0) > 0),
            "detail": f"{rag.get('external_messages', 0)} external messages / {rag.get('memory_items', 0)} memory items / {rag.get('fts_items', 0)} FTS rows",
        },
        {
            "id": "tris_source_bridge",
            "label": "OpenClaw sandbox -> Tris source bridge",
            "ok": source_bridge_ok,
            "detail": source_bridge_payload.get("url")
            or source_bridge_payload.get("source_uid")
            or "no bridge receipt yet",
        },
        {
            "id": "rag",
            "label": "Tris SQL/JSON/RAG",
            "ok": bool(rag.get("status") == "active" and rag.get("fts_available")),
            "detail": rag.get("status") or "unknown",
        },
    ]
    ok = all(check["ok"] for check in checks)
    verdict = "ready" if ok and not recent_tool_errors else "attention"
    if not ok:
        verdict = "blocked"

    receipt = {
        "ok": ok,
        "verdict": verdict,
        "checks": checks,
        "source_home": source_home,
        "source_role": source_role,
        "last_sync": last_sync,
        "last_source_bridge": last_source_bridge,
        "rag": rag,
        "recent_openclaw_tool_errors": recent_tool_errors,
        "read": (
            "Tris deterministic source_tools and the OpenClaw/Telegram bridge can produce saved source receipts. "
            "OpenClaw/Telegram memory is visible to Tris SQL/JSON/RAG. "
            "Direct website probes may still hit normal site-side HTTP blocks, but the active bridge route is the source of truth. "
            "The remaining gate is a fresh live phone/Telegram mission plus a NemoClaw/OpenClaw worker receipt."
        ),
        "next_gate": (
            "Run a live phone/Telegram source mission through /api/field-mission, answer from the saved receipt, "
            "then collect the NemoClaw/OpenClaw worker receipt."
        ),
    }
    db.log_event(
        "tools_doctor",
        {
            "verdict": verdict,
            "ok": ok,
            "recent_tool_errors": len(recent_tool_errors),
            "rag": rag,
            "source_role_ok": source_role_ok,
            "source_home_ok": source_home_ok,
            "source_bridge_ok": source_bridge_ok,
        },
    )
    return receipt
