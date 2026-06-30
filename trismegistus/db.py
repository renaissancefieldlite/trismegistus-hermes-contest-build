from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "trismegistus.sqlite3"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                payload TEXT NOT NULL,
                score REAL NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                selected_lead_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                lead_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS external_message_map (
                source_uid TEXT PRIMARY KEY,
                message_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                ts TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                kind TEXT NOT NULL,
                source_uid TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chat_threads (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                title TEXT NOT NULL,
                deleted_at TEXT
            );
            CREATE TABLE IF NOT EXISTS source_missions (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                lane TEXT NOT NULL,
                origin TEXT NOT NULL,
                request TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS codex_build_requests (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                title TEXT NOT NULL,
                evidence TEXT NOT NULL,
                requested_change TEXT NOT NULL,
                expected_tests TEXT NOT NULL,
                approval_state TEXT NOT NULL,
                implementation_receipt TEXT NOT NULL,
                memory_ingestion_status TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS discipline_lanes (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                current_support TEXT NOT NULL,
                next_gate TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_documents (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                source_pack TEXT NOT NULL,
                title TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_url TEXT NOT NULL,
                support_state TEXT NOT NULL,
                release_boundary TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence_nodes (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                lane_id TEXT NOT NULL,
                source_document_id TEXT NOT NULL,
                support_state TEXT NOT NULL,
                claim TEXT NOT NULL,
                evidence TEXT NOT NULL,
                release_boundary TEXT NOT NULL,
                next_gate TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS source_entities (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                source_mission_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                lane TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT NOT NULL,
                support_state TEXT NOT NULL,
                fit_label TEXT NOT NULL,
                margin_hypothesis TEXT NOT NULL,
                boundary TEXT NOT NULL,
                next_gate TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS relationship_drafts (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                source_entity_id TEXT NOT NULL,
                status TEXT NOT NULL,
                fit_score REAL NOT NULL,
                margin_score REAL NOT NULL,
                offer_lane TEXT NOT NULL,
                draft_summary TEXT NOT NULL,
                boundary TEXT NOT NULL,
                next_gate TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(title, body, kind, content='memory_items', content_rowid='id')
                """
            )
        except sqlite3.OperationalError:
            # Some SQLite builds omit FTS5. The SQL/JSON memory still works and
            # status will expose the RAG lane as unavailable.
            pass
        conn.execute(
            """
            INSERT OR IGNORE INTO chat_threads (id, ts, updated_at, title, deleted_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            ("tris-main", utc_now(), utc_now(), "Trismegistus")
        )


def log_event(kind: str, payload: dict[str, Any]) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT INTO events (ts, kind, payload) VALUES (?, ?, ?)",
            (utc_now(), kind, json.dumps(payload, indent=2, sort_keys=True)),
        )


def save_lead(lead: dict[str, Any], score: float, status: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO leads (id, ts, source, title, payload, score, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead["id"],
                utc_now(),
                lead.get("source", "unknown"),
                lead.get("title", ""),
                json.dumps(lead, indent=2, sort_keys=True),
                score,
                status,
            ),
        )


def get_lead(lead_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        return None
    payload = json.loads(row["payload"])
    payload["_score"] = row["score"]
    payload["_status"] = row["status"]
    payload["_saved_at"] = row["ts"]
    return payload


def list_leads(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    leads: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row["payload"])
        payload["_score"] = row["score"]
        payload["_status"] = row["status"]
        payload["_saved_at"] = row["ts"]
        leads.append(payload)
    return leads


def save_run(run_id: str, selected_lead_id: str, payload: dict[str, Any]) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO runs (id, ts, selected_lead_id, payload) VALUES (?, ?, ?, ?)",
            (run_id, utc_now(), selected_lead_id, json.dumps(payload, indent=2, sort_keys=True)),
        )


def save_message(lead_id: str, role: str, content: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (ts, lead_id, role, content) VALUES (?, ?, ?, ?)",
            (utc_now(), lead_id, role, content),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (utc_now(), lead_id),
        )


def save_external_message(
    lead_id: str,
    role: str,
    content: str,
    source_uid: str,
    source: str,
    payload: dict[str, Any] | None = None,
    ts: str | None = None,
) -> bool:
    init_db()
    now = ts or utc_now()
    with connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM external_message_map WHERE source_uid = ?",
            (source_uid,),
        ).fetchone()
        if exists:
            return False
        cursor = conn.execute(
            "INSERT INTO messages (ts, lead_id, role, content) VALUES (?, ?, ?, ?)",
            (now, lead_id, role, content),
        )
        message_id = int(cursor.lastrowid)
        conn.execute(
            """
            INSERT INTO external_message_map (source_uid, message_id, source, ts, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                source_uid,
                message_id,
                source,
                now,
                json.dumps(payload or {}, indent=2, sort_keys=True),
            ),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
            (now, lead_id),
        )
    return True


def list_messages(lead_id: str, limit: int = 40) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT ts, role, content
            FROM messages
            WHERE lead_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (lead_id, limit),
        ).fetchall()
    messages = []
    for row in rows:
        content = row["content"]
        if content.startswith("Model runtime blocked:"):
            continue
        if "OpenClaw/NemoHermes runtime is currently non" in content:
            continue
        if "provider unknown" in content:
            continue
        messages.append({"ts": row["ts"], "role": row["role"], "content": content})
    messages.reverse()
    return messages


def save_memory_item(
    kind: str,
    source_uid: str,
    title: str,
    body: str,
    payload: dict[str, Any] | None = None,
) -> bool:
    init_db()
    now = utc_now()
    with connect() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO memory_items (ts, kind, source_uid, title, body, payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    kind,
                    source_uid,
                    title,
                    body,
                    json.dumps(payload or {}, indent=2, sort_keys=True),
                ),
            )
        except sqlite3.IntegrityError:
            return False
        rowid = int(cursor.lastrowid)
        try:
            conn.execute(
                "INSERT INTO memory_fts(rowid, title, body, kind) VALUES (?, ?, ?, ?)",
                (rowid, title, body, kind),
            )
        except sqlite3.OperationalError:
            pass
    return True


def rag_status() -> dict[str, Any]:
    init_db()
    with connect() as conn:
        memory_count = conn.execute("SELECT COUNT(*) AS count FROM memory_items").fetchone()["count"]
        external_count = conn.execute("SELECT COUNT(*) AS count FROM external_message_map").fetchone()["count"]
        discipline_count = conn.execute("SELECT COUNT(*) AS count FROM discipline_lanes").fetchone()["count"]
        evidence_count = conn.execute("SELECT COUNT(*) AS count FROM evidence_nodes").fetchone()["count"]
        source_doc_count = conn.execute("SELECT COUNT(*) AS count FROM source_documents").fetchone()["count"]
        try:
            fts_count = conn.execute("SELECT COUNT(*) AS count FROM memory_fts").fetchone()["count"]
            fts_available = True
        except sqlite3.OperationalError:
            fts_count = 0
            fts_available = False
    return {
        "status": "active" if fts_available else "sql-json-only",
        "fts_available": fts_available,
        "memory_items": memory_count,
        "fts_items": fts_count,
        "external_messages": external_count,
        "discipline_lanes": discipline_count,
        "source_documents": source_doc_count,
        "evidence_nodes": evidence_count,
    }


def recent_events(limit: int = 12) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT ts, kind, payload FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"raw": row["payload"]}
        events.append({"ts": row["ts"], "kind": row["kind"], "payload": payload})
    return events


def search_memory_items(query: str, limit: int = 5) -> list[dict[str, Any]]:
    init_db()
    clean = " ".join(str(query or "").split()).strip()
    if not clean:
        return []
    rows = []
    with connect() as conn:
        try:
            rows = conn.execute(
                """
                SELECT m.ts, m.kind, m.source_uid, m.title,
                       snippet(memory_fts, 1, '', '', '...', 40) AS body,
                       bm25(memory_fts) AS rank
                FROM memory_fts
                JOIN memory_items m ON m.id = memory_fts.rowid
                WHERE memory_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (clean, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            terms = [term for term in re_split_query(clean) if len(term) >= 3][:6]
            if not terms:
                return []
            where = " OR ".join(["lower(title || ' ' || body || ' ' || kind) LIKE ?"] * len(terms))
            params = [f"%{term}%" for term in terms]
            rows = conn.execute(
                f"""
                SELECT ts, kind, source_uid, title, substr(body, 1, 700) AS body, 0 AS rank
                FROM memory_items
                WHERE {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
    return [dict(row) for row in rows]


def recent_cross_thread_messages(exclude_lead_id: str, limit: int = 8) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT ts, lead_id, role, content
            FROM messages
            WHERE lead_id != ?
              AND role IN ('user', 'assistant')
              AND content NOT LIKE 'Model runtime blocked:%'
            ORDER BY id DESC
            LIMIT ?
            """,
            (exclude_lead_id, limit),
        ).fetchall()
    messages: list[dict[str, Any]] = []
    for row in rows:
        content = str(row["content"])
        lowered = content.lower()
        if "external golden field lite / hermes runtime dependency" in lowered:
            continue
        if "current runtime receipt:" in lowered:
            continue
        messages.append(
            {
                "ts": row["ts"],
                "lead_id": row["lead_id"],
                "role": row["role"],
                "content": content,
            }
        )
    return messages


def save_source_mission(
    mission_id: str,
    lane: str,
    origin: str,
    request: str,
    status: str,
    payload: dict[str, Any],
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO source_missions
            (id, ts, lane, origin, request, status, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mission_id,
                utc_now(),
                lane,
                origin,
                request,
                status,
                json.dumps(payload, indent=2, sort_keys=True),
            ),
        )


def list_source_missions(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, ts, lane, origin, request, status, payload
            FROM source_missions
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    missions: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"raw": row["payload"]}
        missions.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "lane": row["lane"],
                "origin": row["origin"],
                "request": row["request"],
                "status": row["status"],
                "payload": payload,
            }
        )
    return missions


def save_discipline_lane(
    lane_id: str,
    name: str,
    status: str,
    current_support: str,
    next_gate: str,
    payload: dict[str, Any],
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO discipline_lanes
            (id, ts, name, status, current_support, next_gate, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lane_id,
                utc_now(),
                name,
                status,
                current_support,
                next_gate,
                json.dumps(payload, indent=2, sort_keys=True),
            ),
        )


def save_source_document(
    document_id: str,
    source_pack: str,
    title: str,
    source_path: str,
    source_url: str,
    support_state: str,
    release_boundary: str,
    payload: dict[str, Any],
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO source_documents
            (id, ts, source_pack, title, source_path, source_url, support_state,
             release_boundary, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                utc_now(),
                source_pack,
                title,
                source_path,
                source_url,
                support_state,
                release_boundary,
                json.dumps(payload, indent=2, sort_keys=True),
            ),
        )


def save_evidence_node(
    node_id: str,
    lane_id: str,
    source_document_id: str,
    support_state: str,
    claim: str,
    evidence: str,
    release_boundary: str,
    next_gate: str,
    payload: dict[str, Any],
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO evidence_nodes
            (id, ts, lane_id, source_document_id, support_state, claim, evidence,
             release_boundary, next_gate, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                node_id,
                utc_now(),
                lane_id,
                source_document_id,
                support_state,
                claim,
                evidence,
                release_boundary,
                next_gate,
                json.dumps(payload, indent=2, sort_keys=True),
            ),
        )


def list_evidence_lanes(limit: int = 100) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        lanes = conn.execute(
            """
            SELECT id, ts, name, status, current_support, next_gate, payload
            FROM discipline_lanes
            ORDER BY id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        nodes = conn.execute(
            """
            SELECT id, ts, lane_id, source_document_id, support_state, claim,
                   evidence, release_boundary, next_gate, payload
            FROM evidence_nodes
            ORDER BY lane_id, id
            LIMIT ?
            """,
            (limit * 6,),
        ).fetchall()
        documents = conn.execute(
            """
            SELECT id, ts, source_pack, title, source_path, source_url,
                   support_state, release_boundary, payload
            FROM source_documents
            ORDER BY source_pack, source_path
            LIMIT ?
            """,
            (limit * 8,),
        ).fetchall()

    def _payload(row: sqlite3.Row) -> dict[str, Any]:
        try:
            return json.loads(row["payload"])
        except json.JSONDecodeError:
            return {"raw": row["payload"]}

    return {
        "lanes": [
            {
                "id": row["id"],
                "ts": row["ts"],
                "name": row["name"],
                "status": row["status"],
                "current_support": row["current_support"],
                "next_gate": row["next_gate"],
                "payload": _payload(row),
            }
            for row in lanes
        ],
        "evidence_nodes": [
            {
                "id": row["id"],
                "ts": row["ts"],
                "lane_id": row["lane_id"],
                "source_document_id": row["source_document_id"],
                "support_state": row["support_state"],
                "claim": row["claim"],
                "evidence": row["evidence"],
                "release_boundary": row["release_boundary"],
                "next_gate": row["next_gate"],
                "payload": _payload(row),
            }
            for row in nodes
        ],
        "source_documents": [
            {
                "id": row["id"],
                "ts": row["ts"],
                "source_pack": row["source_pack"],
                "title": row["title"],
                "source_path": row["source_path"],
                "source_url": row["source_url"],
                "support_state": row["support_state"],
                "release_boundary": row["release_boundary"],
                "payload": _payload(row),
            }
            for row in documents
        ],
    }


def search_evidence_nodes(query: str, limit: int = 8) -> list[dict[str, Any]]:
    init_db()
    terms = [term for term in re_split_query(query) if len(term) >= 3][:8]
    if not terms:
        return []
    where_parts = []
    params: list[str] = []
    for term in terms:
        pattern = f"%{term}%"
        where_parts.append(
            """
            lower(e.id || ' ' || e.lane_id || ' ' || coalesce(l.name, '') || ' ' ||
                  e.claim || ' ' || e.evidence || ' ' || e.next_gate || ' ' ||
                  e.support_state || ' ' || d.title || ' ' || d.source_path) LIKE ?
            """
        )
        params.append(pattern.lower())
    sql = f"""
        SELECT e.id, e.ts, e.lane_id, e.source_document_id, e.support_state,
               e.claim, e.evidence, e.release_boundary, e.next_gate, e.payload,
               d.title AS source_title, d.source_path, d.source_url,
               l.name AS lane_name
        FROM evidence_nodes e
        LEFT JOIN source_documents d ON d.id = e.source_document_id
        LEFT JOIN discipline_lanes l ON l.id = e.lane_id
        WHERE {' OR '.join(where_parts)}
        ORDER BY e.ts DESC
        LIMIT ?
    """
    params.append(max(limit * 8, limit))
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"raw": row["payload"]}
        results.append(
            {
                "id": row["id"],
                "lane_id": row["lane_id"],
                "source_document_id": row["source_document_id"],
                "source_title": row["source_title"],
                "source_path": row["source_path"],
                "source_url": row["source_url"],
                "support_state": row["support_state"],
                "claim": row["claim"],
                "evidence": row["evidence"],
                "release_boundary": row["release_boundary"],
                "next_gate": row["next_gate"],
                "lane_name": row["lane_name"],
                "payload": payload,
            }
        )

    def _score(result: dict[str, Any]) -> int:
        buckets = {
            "id": str(result.get("id") or "").lower(),
            "lane": " ".join(
                [
                    str(result.get("lane_id") or ""),
                    str(result.get("lane_name") or ""),
                ]
            ).lower(),
            "source": " ".join(
                [
                    str(result.get("source_document_id") or ""),
                    str(result.get("source_title") or ""),
                    str(result.get("source_path") or ""),
                    str(result.get("source_url") or ""),
                ]
            ).lower(),
            "claim": str(result.get("claim") or "").lower(),
            "evidence": " ".join(
                [
                    str(result.get("evidence") or ""),
                    str(result.get("next_gate") or ""),
                    str(result.get("support_state") or ""),
                ]
            ).lower(),
        }
        score = 0
        for term in terms:
            if term in buckets["id"]:
                score += 60
            if term in buckets["lane"]:
                score += 40
            if term in buckets["source"]:
                score += 36
            if term in buckets["claim"]:
                score += 28
            if term in buckets["evidence"]:
                score += 18
        if buckets["id"].startswith("live_source_browser_mission"):
            score += 12
        return score

    results.sort(key=lambda item: (_score(item), str(item.get("ts") or "")), reverse=True)
    return results[:limit]


def re_split_query(query: str) -> list[str]:
    text = query.lower()
    return [part for part in re.split(r"[^a-z0-9]+", text) if part]


def save_codex_build_request(
    request_id: str,
    mission_id: str,
    title: str,
    evidence: str,
    requested_change: str,
    expected_tests: str,
    approval_state: str,
    implementation_receipt: str,
    memory_ingestion_status: str,
    payload: dict[str, Any],
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO codex_build_requests
            (id, ts, mission_id, title, evidence, requested_change, expected_tests,
             approval_state, implementation_receipt, memory_ingestion_status, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                utc_now(),
                mission_id,
                title,
                evidence,
                requested_change,
                expected_tests,
                approval_state,
                implementation_receipt,
                memory_ingestion_status,
                json.dumps(payload, indent=2, sort_keys=True),
            ),
        )


def list_codex_build_requests(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, ts, mission_id, title, evidence, requested_change,
                   expected_tests, approval_state, implementation_receipt,
                   memory_ingestion_status, payload
            FROM codex_build_requests
            ORDER BY ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    requests: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"raw": row["payload"]}
        requests.append(
            {
                "id": row["id"],
                "ts": row["ts"],
                "mission_id": row["mission_id"],
                "title": row["title"],
                "evidence": row["evidence"],
                "requested_change": row["requested_change"],
                "expected_tests": row["expected_tests"],
                "approval_state": row["approval_state"],
                "implementation_receipt": row["implementation_receipt"],
                "memory_ingestion_status": row["memory_ingestion_status"],
                "payload": payload,
            }
        )
    return requests


def update_codex_build_request_receipt(
    request_id: str,
    *,
    implementation_receipt: str,
    approval_state: str | None = None,
    memory_ingestion_status: str | None = None,
    receipt_payload: dict[str, Any] | None = None,
) -> bool:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT approval_state, memory_ingestion_status, payload
            FROM codex_build_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
        if not row:
            return False
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            payload = {"raw": row["payload"]}
        payload["implementation_receipt"] = implementation_receipt
        if receipt_payload is not None:
            payload["latest_receipt"] = receipt_payload
        next_approval_state = approval_state or row["approval_state"]
        next_memory_status = memory_ingestion_status or row["memory_ingestion_status"]
        payload["approval_state"] = next_approval_state
        payload["memory_ingestion_status"] = next_memory_status
        conn.execute(
            """
            UPDATE codex_build_requests
            SET implementation_receipt = ?,
                approval_state = ?,
                memory_ingestion_status = ?,
                payload = ?
            WHERE id = ?
            """,
            (
                implementation_receipt,
                next_approval_state,
                next_memory_status,
                json.dumps(payload, indent=2, sort_keys=True),
                request_id,
            ),
        )
    return True


def save_source_entity(
    entity_id: str,
    source_mission_id: str,
    entity_type: str,
    name: str,
    lane: str,
    url: str,
    title: str,
    support_state: str,
    fit_label: str,
    margin_hypothesis: str,
    boundary: str,
    next_gate: str,
    payload: dict[str, Any],
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO source_entities
            (id, ts, source_mission_id, entity_type, name, lane, url, title,
             support_state, fit_label, margin_hypothesis, boundary, next_gate, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                utc_now(),
                source_mission_id,
                entity_type,
                name,
                lane,
                url,
                title,
                support_state,
                fit_label,
                margin_hypothesis,
                boundary,
                next_gate,
                json.dumps(payload, indent=2, sort_keys=True),
            ),
        )


def save_relationship_draft(
    draft_id: str,
    source_entity_id: str,
    status: str,
    fit_score: float,
    margin_score: float,
    offer_lane: str,
    draft_summary: str,
    boundary: str,
    next_gate: str,
    payload: dict[str, Any],
) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO relationship_drafts
            (id, ts, source_entity_id, status, fit_score, margin_score, offer_lane,
             draft_summary, boundary, next_gate, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                utc_now(),
                source_entity_id,
                status,
                fit_score,
                margin_score,
                offer_lane,
                draft_summary,
                boundary,
                next_gate,
                json.dumps(payload, indent=2, sort_keys=True),
            ),
        )


def list_source_entities(limit: int = 50) -> dict[str, Any]:
    init_db()
    with connect() as conn:
        entities = conn.execute(
            """
            SELECT id, ts, source_mission_id, entity_type, name, lane, url, title,
                   support_state, fit_label, margin_hypothesis, boundary, next_gate, payload
            FROM source_entities
            ORDER BY ts DESC, id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        drafts = conn.execute(
            """
            SELECT id, ts, source_entity_id, status, fit_score, margin_score, offer_lane,
                   draft_summary, boundary, next_gate, payload
            FROM relationship_drafts
            ORDER BY margin_score DESC, fit_score DESC, ts DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    def _payload(row: sqlite3.Row) -> dict[str, Any]:
        try:
            return json.loads(row["payload"])
        except json.JSONDecodeError:
            return {"raw": row["payload"]}

    return {
        "source_entities": [
            {
                "id": row["id"],
                "ts": row["ts"],
                "source_mission_id": row["source_mission_id"],
                "entity_type": row["entity_type"],
                "name": row["name"],
                "lane": row["lane"],
                "url": row["url"],
                "title": row["title"],
                "support_state": row["support_state"],
                "fit_label": row["fit_label"],
                "margin_hypothesis": row["margin_hypothesis"],
                "boundary": row["boundary"],
                "next_gate": row["next_gate"],
                "payload": _payload(row),
            }
            for row in entities
        ],
        "relationship_drafts": [
            {
                "id": row["id"],
                "ts": row["ts"],
                "source_entity_id": row["source_entity_id"],
                "status": row["status"],
                "fit_score": row["fit_score"],
                "margin_score": row["margin_score"],
                "offer_lane": row["offer_lane"],
                "draft_summary": row["draft_summary"],
                "boundary": row["boundary"],
                "next_gate": row["next_gate"],
                "payload": _payload(row),
            }
            for row in drafts
        ],
    }


def create_thread(title: str | None = None) -> dict[str, Any]:
    init_db()
    thread_id = f"thread-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ%f')}"
    clean_title = (title or "New Trismegistus thread").strip()[:90] or "New Trismegistus thread"
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_threads (id, ts, updated_at, title, deleted_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (thread_id, now, now, clean_title),
        )
    return {"id": thread_id, "title": clean_title, "ts": now, "updated_at": now}


def list_threads(limit: int = 40) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT t.id, t.ts, t.updated_at, t.title, COUNT(m.id) AS message_count
            FROM chat_threads t
            LEFT JOIN messages m ON m.lead_id = t.id
            WHERE t.deleted_at IS NULL
            GROUP BY t.id
            ORDER BY t.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "ts": row["ts"],
            "updated_at": row["updated_at"],
            "message_count": row["message_count"],
        }
        for row in rows
    ]


def get_thread(thread_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, ts, updated_at, title
            FROM chat_threads
            WHERE id = ? AND deleted_at IS NULL
            """,
            (thread_id,),
        ).fetchone()
    if not row:
        return None
    return {"id": row["id"], "title": row["title"], "ts": row["ts"], "updated_at": row["updated_at"]}


def delete_thread(thread_id: str) -> None:
    init_db()
    if thread_id == "tris-main":
        with connect() as conn:
            conn.execute("DELETE FROM messages WHERE lead_id = ?", (thread_id,))
            conn.execute(
                "UPDATE chat_threads SET updated_at = ?, title = ? WHERE id = ?",
                (utc_now(), "Trismegistus", thread_id),
            )
        return
    with connect() as conn:
        conn.execute(
            "UPDATE chat_threads SET deleted_at = ?, updated_at = ? WHERE id = ?",
            (utc_now(), utc_now(), thread_id),
        )
