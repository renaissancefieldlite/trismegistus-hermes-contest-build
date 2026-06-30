from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHAIN_PATH = ROOT / "data" / "consent_chain.json"


def load_chain() -> dict[str, Any]:
    return json.loads(CHAIN_PATH.read_text(encoding="utf-8"))


def run_consent_chain(scored_lead: dict[str, Any]) -> dict[str, Any]:
    lead = scored_lead["lead"]
    blockers = list(scored_lead.get("blockers", []))
    needs_more = scored_lead["score"] < 5.5

    qci = {
        "agent": "QCI",
        "decision": "captured",
        "notes": [
            f"Request: {lead.get('title', '')}",
            f"Source: {lead.get('source', 'unknown')}",
            "Owner and payment terms must be confirmed before external action.",
        ],
    }
    qes = {
        "agent": "QES",
        "decision": "evidence-check",
        "notes": [
            "Scope is small enough for a first-pass technical deliverable.",
            "Any client repo, credentials, or private data stays blocked until consent is explicit.",
        ],
    }
    qpr = {
        "agent": "QPR",
        "decision": "blocked" if blockers else "clear-with-boundaries",
        "notes": blockers
        or [
            "No sensitive-data term detected in lead text.",
            "No live purchase, charge, or account action in draft mode.",
        ],
    }
    qdp_decision = "need-more-info" if blockers or needs_more else "approve"
    qdp = {
        "agent": "QDP",
        "decision": qdp_decision,
        "notes": [
            "Approve only for scoped proposal and draft deliverable."
            if qdp_decision == "approve"
            else "Ask for clearer scope before work execution."
        ],
    }
    return {
        "chain": load_chain(),
        "steps": [qci, qes, qpr, qdp],
        "final_decision": qdp_decision,
    }
