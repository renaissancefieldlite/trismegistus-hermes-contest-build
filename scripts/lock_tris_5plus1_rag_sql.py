#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAYGROUND = ROOT.parent
DATA_DIR = ROOT / "data"
SOURCE_PACK_DIR = DATA_DIR / "source_packs"
RECEIPT_DIR = DATA_DIR / "rag_sql_locks"
PROJECT_STATE_PATH = DATA_DIR / "project_state.json"
PERSISTENT_MEMORY_PATH = DATA_DIR / "persistent_memory.jsonl"
QUADRO_OUTREACH_DIR = PLAYGROUND / "band_of_agents_quadro" / "outreach" / "quadro_company_outreach_2026-06-22"
PITCHED_LIST_PATH = QUADRO_OUTREACH_DIR / "PITCHED_LIST.md"
QUEUE_PATH = QUADRO_OUTREACH_DIR / "GENERATED_EMAIL_QUEUE_100.psv"

sys.path.insert(0, str(ROOT))

from trismegistus import db, evidence_index, project_memory  # noqa: E402


FIELD_LANES: list[dict[str, str]] = [
    {
        "id": "ai_agent_architecture",
        "name": "AI / Agent Architecture",
        "support": "source_pack_indexed_and_receipt_bridge_live",
        "claim": "Tris tracks NemoClaw, OpenClaw, Hermes, RAG, helper agents, model routes, worker receipts, and benchmark repair discipline as one AI expert discipline.",
        "evidence": "Source pack lane exists; Telegram/OpenClaw bridge, SQL/JSON/RAG, SWE/WebArena/GAIA staging, and mail/Stripe action receipts are present.",
        "next_gate": "Run matched eval rows for source accuracy, memory recall, browser action, and worker receipts.",
    },
    {
        "id": "quantum_computing_circuits_mathematics",
        "name": "Quantum Computing / Circuits and Mathematics",
        "support": "source_pack_indexed_next_docs_needed",
        "claim": "Tris should learn quantum computing, quantum circuits, PennyLane/Qiskit/Cirq workflows, and the supporting mathematics lane that includes companion-lattice, M23/Hadamard, and small Diophantine context.",
        "evidence": "Source pack lane exists with quantum computing, circuit, and mathematics source pointers; full child docs still need support labels.",
        "next_gate": "Attach the circuit, lattice, Hadamard, and Diophantine docs as child evidence cards and run source missions against quantum partner targets.",
    },
    {
        "id": "structured_matter_physical_systems",
        "name": "Structured Matter / Physical Systems",
        "support": "source_pack_indexed_next_docs_needed",
        "claim": "Tris should cover materials, chemistry, water, energy, oscillator, spectral, electrochemical, and physical control systems as one discipline lane.",
        "evidence": "Source pack lane exists with structured matter and cross-substrate continuity pointers.",
        "next_gate": "Index Nest 2/Nest 3 support reads with exact source paths and support labels.",
    },
    {
        "id": "life_sciences_medical_research",
        "name": "Life Sciences / Medical Research",
        "support": "public_artifact_pointer_indexed",
        "claim": "Tris should read HRV, Muse/EEG, Phase 12B/12C, human-performance, and medical-adjacent source review as research support, not diagnosis or treatment.",
        "evidence": "Source pack lane exists with Phase 12B/12C and public artifact pointers.",
        "next_gate": "Attach waveform QA, same-clock HRV+Muse receipts, and source-review eval rows before stronger public claims.",
    },
    {
        "id": "mirror_architecture_golden_mark_evidence",
        "name": "Mirror Architecture / Golden Mark Evidence",
        "support": "source_pack_indexed_and_receipts_present",
        "claim": "Tris treats SSP, CB5, Golden Mark, architecture-on/off comparisons, evidence cards, support labels, and next-gate tables as its central evidence-method discipline.",
        "evidence": "Mirror source pack, Golden Mark lane pack, scorecard language, and benchmark discipline are already indexed.",
        "next_gate": "Run matched baseline-vs-Tris eval rows across the five field disciplines and promote each result into evidence_nodes.",
    },
]

OPS_LANE = {
    "id": "relationship_paid_work_field_ops",
    "name": "Relationship / Paid-Work Field Operations",
    "support": "live_receipt_action_lane_approval_gated",
    "claim": "The +1 lane handles communication, sales, outreach, bids, contracts, gig selection, margin checks, Apple Mail sends, Stripe sandbox receipts, and networking follow-up.",
    "evidence": "On 2026-06-29, Tris sent six approved Quadro follow-up emails through Apple Mail in roughly two seconds with one receipt per send; Stripe sandbox Payment Link receipt is also present.",
    "next_gate": "Add reply triage, portal submission packets, margin scoring, and approval-gated relationship mission queue.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def update_project_state() -> dict[str, Any]:
    state = project_memory.ensure_project_state()
    state["field_expert_structure"] = {
        "label": "5+1 AI expert partner curriculum",
        "field_expert_disciplines": [lane["id"] for lane in FIELD_LANES],
        "operations_lane": OPS_LANE["id"],
        "public_safe_positioning": "Five field-expert disciplines plus one relationship, paid-work, sales, and networking operations lane.",
        "truth_boundary": "Operational curriculum and retrieval spine; public proof requires source-backed eval rows and saved receipts.",
        "updated_at": utc_now(),
    }
    lanes_by_id = {lane.get("id"): lane for lane in state.get("lanes", []) if isinstance(lane, dict)}
    for lane in FIELD_LANES + [OPS_LANE]:
        lanes_by_id[lane["id"]] = {
            "id": lane["id"],
            "name": lane["name"],
            "status": lane["support"],
            "detail": lane["claim"],
            "next_gate": lane["next_gate"],
        }
    state["lanes"] = list(lanes_by_id.values())
    state["updated_at"] = utc_now()
    write_json(PROJECT_STATE_PATH, state)
    return state


def update_source_pack() -> dict[str, Any]:
    path = SOURCE_PACK_DIR / "golden_mark_multifield_discipline_partner_lanes_20260621.json"
    pack = read_json(path)
    if not pack:
        raise SystemExit(f"missing source pack: {path}")
    pack["field_expert_structure"] = {
        "label": "5+1",
        "field_expert_disciplines": [lane["id"] for lane in FIELD_LANES],
        "operations_lane": OPS_LANE["id"],
        "language": "five field-expert disciplines plus one relationship/paid-work operations lane",
        "locked_at": utc_now(),
    }
    pack["purpose"] = (
        "Adapt Golden Mark / CB5 / Mirror Companion evidence into five Tris field-expert "
        "discipline lanes plus one relationship and paid-work field operations lane."
    )
    pack["next_system_gate"] = (
        "Promote 5+1 lanes into Tris-native source/evidence tables, then run matched "
        "baseline-vs-Tris eval rows and keep relationship operations approval-gated."
    )
    write_json(path, pack)
    md_path = path.with_suffix(".md")
    lines = [
        "# Golden Mark Multifield Discipline Partner Lanes",
        "",
        f"Locked: {utc_now()}",
        "",
        "Structure: 5 field-expert disciplines + 1 relationship / paid-work operations lane.",
        "",
        "## Field-Expert Disciplines",
    ]
    for lane in FIELD_LANES:
        lines.extend(["", f"### {lane['name']}", "", f"- Lane id: `{lane['id']}`", f"- Support: `{lane['support']}`", f"- Claim: {lane['claim']}", f"- Evidence: {lane['evidence']}", f"- Next gate: {lane['next_gate']}"])
    lines.extend(["", "## +1 Operations Lane", "", f"### {OPS_LANE['name']}", "", f"- Lane id: `{OPS_LANE['id']}`", f"- Support: `{OPS_LANE['support']}`", f"- Claim: {OPS_LANE['claim']}", f"- Evidence: {OPS_LANE['evidence']}", f"- Next gate: {OPS_LANE['next_gate']}"])
    lines.extend(["", "## Boundary", "", "This is an operational curriculum and RAG/SQL retrieval spine. Public proof language still depends on source-backed lane evals and saved receipts."])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(path), "markdown": str(md_path)}


def latest_receipts() -> dict[str, Any]:
    mail_root = DATA_DIR / "rfl_mail_actions"
    mail_receipts = sorted(mail_root.glob("rfl_mail_20260629T18332*/rfl_mail_action.json"))
    mail_payloads: list[dict[str, Any]] = []
    for path in mail_receipts:
        payload = read_json(path)
        payload["_path"] = str(path)
        if payload.get("live_email_sent") is True:
            mail_payloads.append(payload)
    stripe_receipts = sorted((DATA_DIR / "stripe_employee_ops").glob("stripe_payment_link_*.json"))
    stripe_payload = read_json(stripe_receipts[-1]) if stripe_receipts else {}
    if stripe_payload and stripe_receipts:
        stripe_payload["_path"] = str(stripe_receipts[-1])
    return {"mail": mail_payloads, "stripe": stripe_payload}


def save_sql_rag(receipts: dict[str, Any]) -> dict[str, Any]:
    db.init_db()
    evidence_index.seed_from_source_packs()
    source_pack = "tris_5plus1_lock_20260629"
    all_lanes = FIELD_LANES + [OPS_LANE]
    for lane in all_lanes:
        db.save_discipline_lane(
            lane["id"],
            lane["name"],
            "locked",
            lane["support"],
            lane["next_gate"],
            {
                "source_pack": source_pack,
                "structure": "5+1" if lane["id"] == OPS_LANE["id"] else "field_expert_discipline",
                "claim": lane["claim"],
                "evidence": lane["evidence"],
                "truth_boundary": "Operational curriculum and retrieval spine; public proof requires source-backed eval rows.",
            },
        )
        doc_id = f"{source_pack}:{lane['id']}:lock"
        db.save_source_document(
            doc_id,
            source_pack,
            f"{lane['name']} lock receipt",
            str(SOURCE_PACK_DIR / "golden_mark_multifield_discipline_partner_lanes_20260621.json"),
            "",
            lane["support"],
            "public_safe_with_receipt_boundary",
            {"lane": lane},
        )
        db.save_evidence_node(
            f"{source_pack}:{lane['id']}",
            lane["id"],
            doc_id,
            lane["support"],
            lane["claim"],
            lane["evidence"],
            "Public proof still depends on source-backed eval rows and saved receipts.",
            lane["next_gate"],
            {"lane": lane, "receipts": receipts if lane["id"] == OPS_LANE["id"] else {}},
        )
        db.save_memory_item(
            "tris_5plus1_lane_lock",
            f"{source_pack}:{lane['id']}",
            f"{lane['name']} locked into Tris RAG/SQL",
            "\n".join([lane["claim"], f"Evidence: {lane['evidence']}", f"Next gate: {lane['next_gate']}"]),
            {"lane": lane, "source_pack": source_pack},
        )
    mail_sent = receipts.get("mail") or []
    if mail_sent:
        body = "\n".join(
            [
                "Tris can rapidly execute approved direct-address outreach through Apple Mail while saving receipts.",
                f"Batch size: {len(mail_sent)} live follow-up emails.",
                "Recipients: " + ", ".join(str(item.get("recipient")) for item in mail_sent),
                "Boundary: direct addresses only; portal routes remain portal/form tasks.",
            ]
        )
        db.save_memory_item(
            "tris_employee_ops_capability",
            "tris_employee_ops:apple_mail_batch_20260629T183322Z",
            "Apple Mail approved batch send capability locked",
            body,
            {"receipts": mail_sent},
        )
    stripe = receipts.get("stripe") or {}
    if stripe:
        db.save_memory_item(
            "tris_employee_ops_capability",
            "tris_employee_ops:stripe_payment_link_20260629",
            "Stripe sandbox Payment Link capability locked",
            (
                "Stripe sandbox Payment Link route is wired with no live money movement. "
                f"Receipt: {stripe.get('_path', '')}"
            ),
            {"receipt": stripe},
        )
    db.log_event(
        "tris_5plus1_rag_sql_locked",
        {
            "lanes": [lane["id"] for lane in all_lanes],
            "mail_live_sends": len(mail_sent),
            "stripe_payment_link_ready": bool(stripe),
            "rag": db.rag_status(),
        },
    )
    return db.rag_status()


def update_quadro_tracker(receipts: dict[str, Any]) -> None:
    mail_sent = receipts.get("mail") or []
    if not mail_sent or not PITCHED_LIST_PATH.exists():
        return
    text = PITCHED_LIST_PATH.read_text(encoding="utf-8")
    marker = "## 2026-06-29 Tris Apple Mail Follow-Up Batch"
    if marker in text:
        return
    lines = [
        "",
        marker,
        "",
        "Architect D approved a live-fire Quadro follow-up batch through the Tris RFL Apple Mail bridge.",
        "",
        "| Company / Route | Recipient | Status | Receipt |",
        "| --- | --- | --- | --- |",
    ]
    for item in mail_sent:
        subject = str(item.get("subject") or "")
        company = subject.replace("Following up: ", "").split(" for ")[-1] if " for " in subject else subject
        lines.append(
            f"| {company or 'Quadro follow-up'} | `{item.get('recipient')}` | live email sent 2026-06-29 | `{item.get('_path')}` |"
        )
    lines.extend(
        [
            "",
            "Capability note: six approved direct-address follow-ups were sent in roughly two seconds. "
            "This proves rapid approved Apple Mail execution with one receipt per send; portal-only routes still require form/portal handling and are not counted as emails.",
        ]
    )
    PITCHED_LIST_PATH.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def append_operator_memory(receipts: dict[str, Any], rag: dict[str, Any], source_paths: dict[str, str]) -> dict[str, Any]:
    record = {
        "ts": utc_now(),
        "kind": "tris_5plus1_rag_sql_lock",
        "content": "Locked Tris 5+1 field-expert curriculum into JSONL memory, SQL discipline lanes, source documents, evidence nodes, and memory_items.",
        "payload": {
            "field_expert_disciplines": [lane["id"] for lane in FIELD_LANES],
            "operations_lane": OPS_LANE["id"],
            "mail_live_sends": len(receipts.get("mail") or []),
            "stripe_payment_link_receipt": (receipts.get("stripe") or {}).get("_path"),
            "source_paths": source_paths,
            "rag": rag,
        },
    }
    append_jsonl(PERSISTENT_MEMORY_PATH, record)
    return record


def main() -> None:
    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    state = update_project_state()
    source_paths = update_source_pack()
    receipts = latest_receipts()
    rag = save_sql_rag(receipts)
    update_quadro_tracker(receipts)
    memory_record = append_operator_memory(receipts, rag, source_paths)
    receipt = {
        "ok": True,
        "ts": utc_now(),
        "action": "tris_5plus1_rag_sql_lock",
        "project_state": str(PROJECT_STATE_PATH),
        "source_pack_paths": source_paths,
        "persistent_memory": str(PERSISTENT_MEMORY_PATH),
        "sqlite": str(db.DB_PATH),
        "field_expert_disciplines": [lane["id"] for lane in FIELD_LANES],
        "operations_lane": OPS_LANE["id"],
        "mail_live_sends": len(receipts.get("mail") or []),
        "mail_receipts": [item.get("_path") for item in receipts.get("mail") or []],
        "stripe_payment_link_receipt": (receipts.get("stripe") or {}).get("_path"),
        "rag": rag,
        "state_field_expert_structure": state.get("field_expert_structure"),
        "memory_record": memory_record,
    }
    out = RECEIPT_DIR / f"tris_5plus1_rag_sql_lock_{utc_now().replace(':', '').replace('-', '')}.json"
    write_json(out, receipt)
    print(json.dumps({**receipt, "receipt_path": str(out)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
