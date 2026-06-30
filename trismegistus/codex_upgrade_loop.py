from __future__ import annotations

from typing import Any


def next_upgrade_notes(run: dict[str, Any]) -> list[str]:
    selected = run.get("selected", {})
    consent = run.get("consent", {})
    source = run.get("deliverable", {}).get("source")
    notes = [
        "Persist accepted/rejected lead outcomes so the scout gets better.",
        "Add real source connectors one at a time: Reddit, HN, Upwork-style boards, grant/task boards.",
        "Keep Quadro approval in front of any external message, payment, or account action.",
    ]
    if source == "local_golden_mark_fallback":
        notes.append("Hermes/NemoClaw not live yet: wire local gateway before submission recording.")
    if consent.get("final_decision") != "approve":
        notes.append("Improve intake questions for leads that need more info before execution.")
    if selected.get("score", 0) < 7:
        notes.append("Tighten the low-hanging-fruit filter so weak leads do not waste agent cycles.")
    notes.append("Next Codex pass: inspect this run JSON and patch the weakest loop stage.")
    return notes
