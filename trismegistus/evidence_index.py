from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import db


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACK_DIR = ROOT / "data" / "source_packs"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:96] or "source"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _source_url(pack: dict[str, Any], source_path: str) -> str:
    repo_url = str(pack.get("repo_url") or (pack.get("source") or {}).get("url") or "")
    if repo_url and source_path and not source_path.startswith(("http://", "https://")):
        return repo_url.rstrip("/") + "/blob/main/" + source_path.lstrip("/")
    if source_path.startswith(("http://", "https://")):
        return source_path
    return repo_url


def _save_doc(
    *,
    pack: dict[str, Any],
    pack_id: str,
    source_path: str,
    title: str,
    support_state: str,
    release_boundary: str,
    payload: dict[str, Any],
) -> str:
    doc_id = f"{pack_id}:{_slug(source_path or title)}"
    db.save_source_document(
        doc_id,
        pack_id,
        title or source_path or pack_id,
        source_path,
        _source_url(pack, source_path),
        support_state,
        release_boundary,
        payload,
    )
    return doc_id


def _seed_mirror_source_pack(pack: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(pack.get("id") or "mirror_architecture_evidence_stack")
    lane_id = "mirror_architecture_source_pack"
    db.save_discipline_lane(
        lane_id,
        "Mirror Architecture Source Pack",
        "indexed",
        "public_safe_source_pack",
        "Promote public source cards into lane-specific evidence nodes before stronger proof language.",
        {"source_pack": pack_id, "truth_boundary": pack.get("truth_boundary")},
    )
    inserted_nodes = 0
    inserted_docs: set[str] = set()
    for card in pack.get("cards", []):
        if not isinstance(card, dict):
            continue
        card_id = str(card.get("id") or _slug(str(card.get("title") or "card")))
        paths = card.get("source_paths") or pack.get("source_files") or []
        if not isinstance(paths, list):
            paths = [str(paths)]
        first_doc_id = ""
        for source_path in paths:
            source_path = str(source_path)
            doc_id = _save_doc(
                pack=pack,
                pack_id=pack_id,
                source_path=source_path,
                title=source_path,
                support_state=str(card.get("support_state") or "public_safe_source_pack"),
                release_boundary=str(card.get("boundary") or pack.get("truth_boundary") or ""),
                payload={"source_pack": pack_id, "card_id": card_id, "card": card},
            )
            inserted_docs.add(doc_id)
            first_doc_id = first_doc_id or doc_id
        db.save_evidence_node(
            f"{pack_id}:{card_id}",
            lane_id,
            first_doc_id or f"{pack_id}:document",
            str(card.get("support_state") or "public_safe_source_pack"),
            str(card.get("claim") or card.get("title") or ""),
            str(card.get("evidence") or ""),
            str(card.get("boundary") or pack.get("truth_boundary") or ""),
            str(card.get("next_gate") or ""),
            {"source_pack": pack_id, "card": card},
        )
        inserted_nodes += 1
    return {"pack_id": pack_id, "documents": len(inserted_docs), "evidence_nodes": inserted_nodes}


def _seed_discipline_partner_pack(pack: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(pack.get("id") or "golden_mark_multifield_discipline_partner_lanes")
    inserted_nodes = 0
    inserted_docs: set[str] = set()
    for lane in pack.get("lanes", []):
        if not isinstance(lane, dict):
            continue
        lane_id = str(lane.get("id") or _slug(str(lane.get("name") or "lane")))
        support = str(lane.get("current_support") or "source_pack_indexed")
        boundary = str(pack.get("truth_boundary") or "")
        next_gate = str(lane.get("next_gate") or "")
        db.save_discipline_lane(
            lane_id,
            str(lane.get("name") or lane_id),
            support,
            support,
            next_gate,
            {"source_pack": pack_id, "lane": lane, "truth_boundary": boundary},
        )
        sources = lane.get("evidence_sources") or []
        if not isinstance(sources, list):
            sources = [str(sources)]
        first_doc_id = ""
        for source in sources:
            source_path = str(source)
            doc_id = _save_doc(
                pack=pack,
                pack_id=pack_id,
                source_path=source_path,
                title=source_path,
                support_state=support,
                release_boundary=boundary,
                payload={"source_pack": pack_id, "lane_id": lane_id, "lane": lane},
            )
            inserted_docs.add(doc_id)
            first_doc_id = first_doc_id or doc_id
        db.save_evidence_node(
            f"{pack_id}:{lane_id}",
            lane_id,
            first_doc_id or f"{pack_id}:document",
            support,
            str(lane.get("public_positioning") or lane.get("name") or ""),
            str(lane.get("golden_mark_adaptation") or ""),
            boundary,
            next_gate,
            {"source_pack": pack_id, "lane": lane},
        )
        inserted_nodes += 1
    return {"pack_id": pack_id, "documents": len(inserted_docs), "evidence_nodes": inserted_nodes}


def _seed_live_source_pack(pack: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(pack.get("id") or "live_source_browser_mission")
    default_lane_id = str(pack.get("lane_id") or "live_source_browser_mission")
    db.save_discipline_lane(
        default_lane_id,
        str(pack.get("lane_name") or "Live Source Browser Mission"),
        "indexed",
        str(pack.get("current_support") or "source_action_receipt_supported"),
        str(pack.get("next_system_gate") or ""),
        {"source_pack": pack_id, "source": pack.get("source"), "truth_boundary": pack.get("truth_boundary")},
    )
    inserted_nodes = 0
    inserted_docs: set[str] = set()
    for card in pack.get("cards", []):
        if not isinstance(card, dict):
            continue
        card_id = str(card.get("id") or _slug(str(card.get("title") or "card")))
        lane_id = str(card.get("lane_id") or default_lane_id)
        if lane_id != default_lane_id:
            db.save_discipline_lane(
                lane_id,
                lane_id.replace("_", " ").title(),
                "indexed",
                str(card.get("support_state") or pack.get("current_support") or "source_loaded"),
                str(card.get("next_gate") or ""),
                {"source_pack": pack_id, "card_id": card_id, "truth_boundary": card.get("boundary")},
            )
        paths = card.get("source_paths") or []
        if not isinstance(paths, list):
            paths = [str(paths)]
        first_doc_id = ""
        for source_path in paths:
            source_path = str(source_path)
            doc_id = _save_doc(
                pack=pack,
                pack_id=pack_id,
                source_path=source_path,
                title=str(card.get("title") or source_path),
                support_state=str(card.get("support_state") or pack.get("current_support") or "source_loaded"),
                release_boundary=str(card.get("boundary") or pack.get("truth_boundary") or ""),
                payload={"source_pack": pack_id, "card_id": card_id, "card": card},
            )
            inserted_docs.add(doc_id)
            first_doc_id = first_doc_id or doc_id
        db.save_evidence_node(
            f"{pack_id}:{card_id}",
            lane_id,
            first_doc_id or f"{pack_id}:document",
            str(card.get("support_state") or pack.get("current_support") or "source_loaded"),
            str(card.get("claim") or card.get("title") or ""),
            str(card.get("evidence") or ""),
            str(card.get("boundary") or pack.get("truth_boundary") or ""),
            str(card.get("next_gate") or pack.get("next_system_gate") or ""),
            {"source_pack": pack_id, "card": card},
        )
        inserted_nodes += 1
    return {"pack_id": pack_id, "documents": len(inserted_docs), "evidence_nodes": inserted_nodes}


def _seed_quantum_hrv_willow_pack(pack: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(pack.get("source_pack_id") or "tris_quantum_hrv_willow_nesting_lanes_20260629")
    inserted_nodes = 0
    inserted_docs: set[str] = set()
    for card in pack.get("cards", []):
        if not isinstance(card, dict):
            continue
        card_id = str(card.get("id") or _slug(str(card.get("title") or "card")))
        lanes = card.get("lanes") or ["quantum_computing_circuits_mathematics"]
        if not isinstance(lanes, list):
            lanes = [str(lanes)]
        sources = card.get("sources") or []
        if not isinstance(sources, list):
            sources = [sources]
        source_paths = [
            str(source.get("path") or source.get("relative_path") or "")
            for source in sources
            if isinstance(source, dict)
        ]
        source_urls = [
            str(source.get("source_url") or "")
            for source in sources
            if isinstance(source, dict) and source.get("source_url")
        ]
        doc_id = f"{pack_id}:{card_id}"
        db.save_source_document(
            doc_id,
            pack_id,
            str(card.get("title") or card_id),
            "; ".join(source_paths),
            "; ".join(source_urls),
            str(card.get("support_state") or "source_pack_indexed"),
            str(card.get("release_boundary") or ""),
            {"source_pack": pack_id, "card": card},
        )
        inserted_docs.add(doc_id)
        for lane_id in lanes:
            db.save_evidence_node(
                f"{doc_id}:{lane_id}",
                str(lane_id),
                doc_id,
                str(card.get("support_state") or "source_pack_indexed"),
                str(card.get("claim") or card.get("title") or ""),
                str(card.get("evidence") or ""),
                str(card.get("release_boundary") or ""),
                str(card.get("next_gate") or ""),
                {"source_pack": pack_id, "card": card, "primary_lane": lane_id},
            )
            inserted_nodes += 1
    return {"pack_id": pack_id, "documents": len(inserted_docs), "evidence_nodes": inserted_nodes}


def seed_from_source_packs() -> dict[str, Any]:
    SOURCE_PACK_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    mirror_pack = _load_json(SOURCE_PACK_DIR / "mirror_architecture_evidence_stack_20260621.json")
    if mirror_pack:
        results.append(_seed_mirror_source_pack(mirror_pack))
    discipline_pack = _load_json(SOURCE_PACK_DIR / "golden_mark_multifield_discipline_partner_lanes_20260621.json")
    if discipline_pack:
        results.append(_seed_discipline_partner_pack(discipline_pack))
    live_pack = _load_json(SOURCE_PACK_DIR / "live_source_browser_mission_20260621.json")
    if live_pack:
        results.append(_seed_live_source_pack(live_pack))
    quantum_hrv_willow_pack = _load_json(SOURCE_PACK_DIR / "quantum_hrv_willow_nesting_lanes_20260629.json")
    if quantum_hrv_willow_pack:
        results.append(_seed_quantum_hrv_willow_pack(quantum_hrv_willow_pack))
    db.log_event("evidence_index_seeded", {"results": results, "rag": db.rag_status()})
    return {"ok": True, "results": results, "evidence": db.list_evidence_lanes()}


def search(query: str, limit: int = 8) -> dict[str, Any]:
    seed_from_source_packs()
    results = db.search_evidence_nodes(query, limit=limit)
    return {
        "ok": bool(results),
        "source": "tris-evidence-index",
        "kind": "local-evidence-rag",
        "query": query,
        "results": results,
        "rag": db.rag_status(),
    }
