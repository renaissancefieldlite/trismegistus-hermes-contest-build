from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trismegistus import db

BROWSER_DIR = ROOT / "data" / "browser_autonomy"
OUT_DIR = ROOT / "data" / "source_entities"


QUANTUM_OFFER = (
    "RFL/Tris source-backed research brief, AI/quantum partner map, "
    "and review-gated technical outreach packet"
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _latest_live_sequence() -> Path:
    candidates = sorted(BROWSER_DIR.glob("tris_live_site_sequence_*.json"), key=lambda path: path.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No live site sequence JSON found in {BROWSER_DIR}")
    return candidates[-1]


def _clean(text: str, limit: int = 520) -> str:
    return " ".join(str(text or "").split())[:limit]


def _scores(result: dict[str, Any]) -> tuple[float, float, str, str]:
    lane = str(result.get("lane") or "")
    result_id = str(result.get("id") or "")
    preview = str(result.get("body_preview") or "").lower()
    if lane == "nvidia_quantum_partner_candidate":
        fit = 0.84
        margin = 0.78
        if any(term in preview for term in ("partner", "enterprise", "hpc", "cloud", "developer", "sdk")):
            fit += 0.05
        if any(term in preview for term in ("request a demo", "contact", "consultation", "enterprise")):
            margin += 0.04
        return (
            min(fit, 0.94),
            min(margin, 0.88),
            QUANTUM_OFFER,
            "Quantum/AI partner candidate for source-backed RFL research and technical outreach.",
        )
    if result_id == "nous_careers":
        return (
            0.92,
            0.72,
            "Researcher/FDE positioning packet and Hermes Agent contribution map",
            "Nous careers and Hermes Agent role source for the Tris/NemoClaw contest arc.",
        )
    if result_id == "rfl_public_stack":
        return (
            0.96,
            0.64,
            "Public evidence-stack proof surface for Tris source answers",
            "RFL source-of-truth surface; not an external relationship target.",
        )
    return (0.65, 0.50, "source review", "Loaded source target requiring extraction.")


def _entity_type(result: dict[str, Any]) -> str:
    lane = str(result.get("lane") or "")
    if lane == "nvidia_quantum_partner_candidate":
        return "company"
    if str(result.get("id") or "") == "nous_careers":
        return "role_source"
    if str(result.get("id") or "") == "rfl_public_stack":
        return "self_source"
    return "source"


def _support_state(result: dict[str, Any]) -> str:
    if not result.get("ok"):
        return "source_failed"
    if _entity_type(result) == "company":
        return "source_loaded_needs_company_extraction"
    if _entity_type(result) == "role_source":
        return "source_loaded_needs_role_extraction"
    if _entity_type(result) == "self_source":
        return "source_loaded_self_evidence_surface"
    return "source_loaded_needs_review"


def promote(sequence_path: Path) -> dict[str, Any]:
    receipt = json.loads(sequence_path.read_text())
    run_id = str(receipt.get("id") or sequence_path.stem)
    stamp = _utc_stamp()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    entities: list[dict[str, Any]] = []
    drafts: list[dict[str, Any]] = []

    for result in receipt.get("results", []):
        result_id = str(result.get("id") or f"source_{len(entities) + 1}")
        name = str(result.get("label") or result_id).strip()
        entity_id = f"{run_id}:{result_id}"
        fit_score, margin_score, offer_lane, fit_label = _scores(result)
        boundary = (
            "Source-loaded row only. This is not outreach, a partnership, an endorsement, "
            "a payment action, or a validated benchmark result."
        )
        next_gate = (
            "Extract specific role/company facts, label support state, score fit and margin, "
            "then create a review-gated relationship draft."
        )
        entity = {
            "id": entity_id,
            "source_mission_id": run_id,
            "entity_type": _entity_type(result),
            "name": name,
            "lane": str(result.get("lane") or "source_research"),
            "url": str(result.get("final_url") or result.get("url") or ""),
            "title": str(result.get("title") or ""),
            "support_state": _support_state(result),
            "fit_label": fit_label,
            "margin_hypothesis": (
                "Internal triage only. Margin estimate depends on actual scoped offer, "
                "hours, approval, delivery risk, and outbound response."
            ),
            "boundary": boundary,
            "next_gate": next_gate,
            "source_basis": str(result.get("source_basis") or ""),
            "body_preview": _clean(str(result.get("body_preview") or ""), 900),
            "screenshot": str(result.get("screenshot") or ""),
        }
        db.save_source_entity(
            entity_id=entity["id"],
            source_mission_id=entity["source_mission_id"],
            entity_type=entity["entity_type"],
            name=entity["name"],
            lane=entity["lane"],
            url=entity["url"],
            title=entity["title"],
            support_state=entity["support_state"],
            fit_label=entity["fit_label"],
            margin_hypothesis=entity["margin_hypothesis"],
            boundary=entity["boundary"],
            next_gate=entity["next_gate"],
            payload=entity,
        )
        entities.append(entity)

        if entity["entity_type"] in {"company", "role_source"}:
            draft_id = f"{entity_id}:relationship_draft"
            draft_summary = (
                f"Draft-only lane for {name}: {offer_lane}. "
                "Tris should cite the saved source, explain RFL/Mirror Architecture fit, "
                "propose a small first artifact, estimate effort and margin, and wait for approval."
            )
            draft = {
                "id": draft_id,
                "source_entity_id": entity_id,
                "status": "draft_not_sent",
                "fit_score": round(fit_score, 3),
                "margin_score": round(margin_score, 3),
                "offer_lane": offer_lane,
                "draft_summary": draft_summary,
                "boundary": "Draft mode only. No message, spend, application, or claim of relationship has happened.",
                "next_gate": "Generate a review-gated relationship draft with source citations and a margin estimate.",
            }
            db.save_relationship_draft(
                draft_id=draft["id"],
                source_entity_id=draft["source_entity_id"],
                status=draft["status"],
                fit_score=draft["fit_score"],
                margin_score=draft["margin_score"],
                offer_lane=draft["offer_lane"],
                draft_summary=draft["draft_summary"],
                boundary=draft["boundary"],
                next_gate=draft["next_gate"],
                payload={**draft, "entity": entity},
            )
            drafts.append(draft)

    output = {
        "id": f"live_source_entities_{stamp}",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_sequence": str(sequence_path),
        "source_sequence_id": run_id,
        "entity_count": len(entities),
        "draft_count": len(drafts),
        "entities": entities,
        "relationship_drafts": drafts,
        "boundary": "Normalized source/margin rows are internal triage receipts, not external action.",
        "next_gate": "Run visible relationship-draft missions and compare baseline Hermes versus Tris architecture-on behavior.",
    }
    json_path = OUT_DIR / f"{output['id']}.json"
    md_path = OUT_DIR / f"{output['id']}.md"
    json_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")

    lines = [
        f"# {output['id']}",
        "",
        f"- Source sequence: `{sequence_path}`",
        f"- Entities: `{len(entities)}`",
        f"- Relationship drafts: `{len(drafts)}`",
        f"- Boundary: {output['boundary']}",
        f"- Next gate: {output['next_gate']}",
        "",
        "## Entities",
    ]
    for entity in entities:
        lines.extend(
            [
                "",
                f"### {entity['name']}",
                f"- Type: `{entity['entity_type']}`",
                f"- Lane: `{entity['lane']}`",
                f"- Support: `{entity['support_state']}`",
                f"- URL: {entity['url']}",
                f"- Fit: {entity['fit_label']}",
                f"- Boundary: {entity['boundary']}",
                f"- Next gate: {entity['next_gate']}",
            ]
        )
    lines.extend(["", "## Relationship Drafts"])
    for draft in drafts:
        lines.extend(
            [
                "",
                f"### {draft['id']}",
                f"- Status: `{draft['status']}`",
                f"- Fit score: `{draft['fit_score']}`",
                f"- Margin score: `{draft['margin_score']}`",
                f"- Offer lane: {draft['offer_lane']}",
                f"- Summary: {draft['draft_summary']}",
                f"- Boundary: {draft['boundary']}",
                f"- Next gate: {draft['next_gate']}",
            ]
        )
    md_path.write_text("\n".join(lines) + "\n")
    output["json_path"] = str(json_path)
    output["markdown_path"] = str(md_path)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote latest Tris live browser sources into source entity rows.")
    parser.add_argument("--sequence", type=Path, default=None, help="Specific tris_live_site_sequence JSON path.")
    args = parser.parse_args()
    sequence = args.sequence or _latest_live_sequence()
    result = promote(sequence)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
