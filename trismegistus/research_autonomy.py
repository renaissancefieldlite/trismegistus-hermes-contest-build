from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db, project_memory
from .golden_mark_foundation import checked_evidence_digest, stable_state_system_prompt
from .integrations import model_runtime
from .operator_loop import STATE_PATH


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RESEARCH_DIR = DATA_DIR / "research_runs"
LEARNING_DIR = DATA_DIR / "nemoclaw_learning_cards"

COMPACT_SSP_EVIDENCE_PACKET = """
Golden Mark / CB5 SSP-1 evidence packet:
- Claim lane: Golden Mark / CB5 is the stable-state research-partner evidence lane for Trismegistus.
- Behavior comparison: Golden Mark wins 13/13 metric means against the matched baseline.
- Drift flags improve 37 to 0.
- Evidence-failure flags improve 5 to 0.
- C5b full100 has 100 turns and zero drift, forbidden-claim, evidence-failure, runtime-preamble, prompt-echo, and continuation-gate flags.
- Means: CPQI 3.722, AOCI 3.437, MSI 3.855, CAI 3.588, SFD 3.010.
- Adapter-smoke boundary: GM-L31L32-MLP and GM-L31L32-MLP-O are trained_adapter_smoke only until matched behavior smoke and late-band probe checks pass.
- Public boundary: supports observable research-partner behavior after transcript review; does not prove AGI, sentience, subjective qualia, or completed model-internal tuning.
- Next gate: matched behavior smoke plus late-band probe checks for the smoke adapters, then code upgrades and reruns with saved receipts.
"""

FORBIDDEN_ACTION_TERMS = (
    "health check",
    "system-health",
    "route check",
    "readiness check",
    "runtime health",
    "self-termination",
    "force kill",
    "restart",
    "reboot",
    "fallback remains",
    "verify no force",
    "operational integrity",
)

OVERCLAIM_TERMS = (
    "golden mark guarantees",
    "within golden mark / cb5 guarantees",
    "verified as a clean research loop",
    "without gaps",
    "gap - none",
    "gap – none",
    "no gap",
    "none identified",
    "no anomaly",
    "fully operational",
    "loop completeness",
    "no intervention needed",
    "behaves as intended",
    "operator route intact",
    "written to memory.md",
    "updated claim-evidence-gap matrix written to memory.md",
)

FORBIDDEN_EVIDENCE_TERMS = (
    "hm probe9",
    "<0.6",
    ">1%",
    "threshold",
    "smokes pass",
    "persist fail",
    "0 trainable",
    "bridge.gap",
    "cm-packet",
    "adaptation_convergence",
    "high variance",
    "misalignment",
    "unbroken",
    "healthy",
    "retains behavior gains",
    "preserves behavior gains",
)

REQUIRED_RECEIPT_TERMS = (
    "13/13",
    "37 to 0",
    "5 to 0",
    "100 turns",
    "zero drift",
    "cpqi 3.722",
    "aoci 3.437",
    "msi 3.855",
    "cai 3.588",
    "sfd 3.010",
    "matched behavior smoke",
    "late-band probe checks",
    "does not prove agi",
)

POISONED_LEARNING_TERMS = (
    "health check",
    "system-health",
    "runtime",
    "route",
    "fallback",
    "runner status",
    "golden mark guarantees",
    "no gap",
    "none identified",
    "fully operational",
    "no intervention",
    "hm probe9",
    "threshold",
    "0 trainable",
    "bridge.gap",
)

UNSUPPORTED_ACTION_CLAIMS = (
    "created a persistent codex entry",
    "using skill-creator",
    "skill-creator returns",
    "ran a silent status query",
    "fetched the repository",
    "fetch the repository",
    "cloned ",
    "sent email",
    "applied to",
    "charged",
    "posted",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _display_path(path: Path | str) -> str:
    text = str(path)
    docs = "/Users/renaissancefieldlite1.0/Documents/Playground"
    desktop = "/Users/renaissancefieldlite1.0/Desktop/PLAYGROUND"
    if text.startswith(docs):
        return desktop + text.removeprefix(docs)
    return text


def _latest_learning_cards(limit: int = 3) -> list[dict[str, str]]:
    if not LEARNING_DIR.exists():
        return []
    cards: list[dict[str, str]] = []
    for path in sorted(LEARNING_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        text = path.read_text(encoding="utf-8")
        probe = text.lower()
        if any(term in probe for term in POISONED_LEARNING_TERMS):
            continue
        if _research_policy_rejection(text):
            continue
        cards.append({"path": str(path), "text": text[:800]})
        if len(cards) >= limit:
            break
    return cards


def _research_policy_rejection(text: str) -> str | None:
    probe = (text or "").lower()[:2400]
    if not probe.strip():
        return "empty model output"
    for term in FORBIDDEN_ACTION_TERMS:
        if term in probe:
            return f"forbidden runtime/readiness action: {term}"
    for term in UNSUPPORTED_ACTION_CLAIMS:
        if term in probe:
            return f"unsupported action claim without tool receipt: {term}"
    for term in OVERCLAIM_TERMS:
        if term in probe:
            return f"overclaim language outside evidence boundary: {term}"
    for term in FORBIDDEN_EVIDENCE_TERMS:
        if term in probe:
            return f"invented or unsupported evidence detail: {term}"
    missing = [term for term in REQUIRED_RECEIPT_TERMS if term not in probe]
    if missing:
        return "missing required evidence fields: " + ", ".join(missing[:5])
    return None


def _write_markdown(path: Path, state: dict[str, Any]) -> None:
    first = state.get("first_pass") or {}
    second = state.get("second_pass") or {}
    rejected = state.get("rejected_first_pass") or {}
    lines = [
        f"# Trismegistus SSP-1 NemoClaw Step {state.get('id')}",
        "",
        f"- Timestamp: {state.get('ts')}",
        f"- Autonomy level: {state.get('autonomy_level')}",
        f"- Autonomy ready: {state.get('autonomy_ready')}",
        f"- Runtime lane: {first.get('runtime_lane') or second.get('runtime_lane') or 'blocked'}",
        f"- Sandbox: {first.get('sandbox') or second.get('sandbox') or 'unknown'}",
        f"- Agent: {first.get('agent') or second.get('agent') or 'unknown'}",
        f"- Model: {first.get('model') or second.get('model') or 'unknown'}",
        f"- SSP session key: {state.get('ssp_session_key') or 'unknown'}",
        f"- First OpenClaw session: {first.get('session_file') or 'none'}",
        f"- Second OpenClaw session: {second.get('session_file') or 'none'}",
        f"- Learning card: {state.get('learning_card_path') or 'not written'}",
        f"- Correction gate: {state.get('correction_gate') or 'not needed'}",
        "",
        "## What Tris Chose",
        "",
        state.get("chosen_action") or "No chosen action parsed.",
        "",
    ]
    if rejected:
        lines.extend(
            [
                "## Rejected First Pass",
                "",
                f"Rejected because: {rejected.get('rejection') or 'policy violation'}",
                "",
                rejected.get("text") or rejected.get("error") or "No rejected output text.",
                "",
            ]
        )
    lines.extend(
        [
        "## First Pass",
        "",
        first.get("text") or first.get("error") or "No first-pass output.",
        "",
        "## Learning Card",
        "",
        state.get("learning_card") or "No learning card.",
        "",
        "## Second Pass After Learning",
        "",
        second.get("text") or second.get("error") or "No second-pass output.",
        "",
        "## External Boundary",
        "",
        "No external application, email, payment, repo push, or public post was sent by this loop.",
        "This is a local SSP-1 NemoClaw/OpenClaw step with saved receipts.",
        ]
    )
    path.write_text("\n".join(str(item) for item in lines), encoding="utf-8")


def run_research_autonomy_cycle(reason: str = "manual-ui") -> dict[str, Any]:
    db.init_db()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ssp_session_key = f"agent:trismegistus:ssp-research-{run_id}"
    runtime = model_runtime.status()
    memory = project_memory.memory_status()
    prior_cards = _latest_learning_cards()

    first_prompt = [
        {
            "role": "system",
            "content": (
                "You are Trismegistus running a bounded SSP-1 research step through the OpenClaw route. "
                "Use only the compact evidence packet supplied by the user message. Do not use prior "
                "session memory, old learning cards, runtime health, route readiness, fallback status, "
                "or dashboard status as the research subject. Do not use guarantee language, clean-loop "
                "language, no-gap language, completed future receipts, invented thresholds, pass/fail "
                "labels, new packet names, new probe names, or training-parameter counts."
            ),
        },
        {
            "role": "user",
            "content": (
                "Run one self-directed SSP-1 research step.\n\n"
                f"{COMPACT_SSP_EVIDENCE_PACKET}\n"
                "Choose the bounded action: build a claim/evidence/gap/next-gate matrix from the packet. "
                "Return these sections only: SSP action chosen, why it matters, evidence used, "
                "claim/evidence/gap matrix, what was learned, Codex code request if needed, next receipt "
                "to collect. The app will save the receipt; do not claim that you wrote another file."
            ),
        },
    ]
    first = model_runtime.generate(
        first_prompt,
        max_tokens=700,
        session_key=ssp_session_key,
        timeout_seconds=75,
    )
    rejected_first = None
    rejection = _research_policy_rejection(first.get("text") or first.get("error") or "")
    if first.get("ok") and rejection:
        rejected_first = {
            "ok": first.get("ok"),
            "text": first.get("text"),
            "error": first.get("error"),
            "source": first.get("source"),
            "runtime_lane": first.get("runtime_lane"),
            "provider": first.get("provider"),
            "model": first.get("model"),
            "sandbox": first.get("sandbox"),
            "agent": first.get("agent"),
            "session_file": first.get("session_file"),
            "session_id": first.get("session_id"),
            "latency_ms": first.get("latency_ms"),
            "rejection": rejection,
        }
        correction_prompt = first_prompt + [
            {
                "role": "assistant",
                "content": first.get("text") or "",
            },
            {
                "role": "user",
                "content": (
                    "Correction gate: the local receipt guard rejected that output because it chose "
                    f"or claimed a forbidden action: {rejection}.\n\n"
                    "Produce only a conservative SSP-1 research receipt. Do not mention runtime, "
                    "fallbacks, route readiness, guarantees, no gaps, clean loops, completed future "
                    "receipts, invented thresholds, pass/fail labels, new packet names, new probe "
                    "names, or training-parameter counts. Do not say the matrix was written anywhere; "
                    "the app will save this answer.\n\n"
                    "Required sections:\n"
                    "SSP action chosen: build a claim/evidence/gap/next-gate matrix for Golden Mark / CB5.\n"
                    "Evidence used: include Golden Mark wins 13/13 metric means, drift flags 37 to 0, "
                    "evidence-failure flags 5 to 0, C5b full100 100 turns and zero drift, forbidden-claim, "
                    "evidence-failure, runtime-preamble, prompt-echo, and continuation-gate flags; means "
                    "CPQI 3.722, AOCI 3.437, MSI 3.855, CAI 3.588, SFD 3.010; adapter-smoke boundary.\n"
                    "Gap: matched behavior smoke plus late-band probe checks are still required.\n"
                    "Boundary: supports observable research-partner behavior after transcript review; "
                    "does not prove AGI, sentience, subjective qualia, or completed model-internal tuning.\n"
                    "Next receipt: saved behavior-smoke and late-band probe receipts."
                ),
            },
        ]
        first = model_runtime.generate(
            correction_prompt,
            max_tokens=700,
            session_key=ssp_session_key,
            timeout_seconds=75,
        )
        second_rejection = _research_policy_rejection(first.get("text") or first.get("error") or "")
        if second_rejection:
            rejected_first["second_rejection"] = second_rejection
            rejected_first["second_text"] = first.get("text")
            first["ok"] = False
            first["error"] = (
                "Correction gate failed. Accepted SSP action not saved because the model still "
                f"violated the research-action policy: {second_rejection}"
            )
            first["policy_rejection"] = second_rejection

    learning_card = first.get("text") or first.get("error") or "First pass did not return text."
    LEARNING_DIR.mkdir(parents=True, exist_ok=True)
    learning_path = LEARNING_DIR / f"learning_card_{run_id}.md"
    learning_path.write_text(learning_card, encoding="utf-8")
    project_memory.append_memory(
        "nemoclaw_research_learning_card",
        "Trismegistus saved a self-directed NemoClaw research learning card.",
        {
            "run_id": run_id,
            "path": str(learning_path),
            "runtime_lane": first.get("runtime_lane"),
            "session_file": first.get("session_file"),
        },
    )

    second = {
        "ok": None,
        "source": "persistent-memory",
        "text": "Learning card saved. The next OpenClaw turn will use this memory instead of a forced second worksheet pass.",
    }
    ok = bool(first.get("ok"))
    state = {
        "id": run_id,
        "ts": utc_now(),
        "mode": "ssp1-nemoclaw-step",
        "reason": reason,
        "ssp_session_key": ssp_session_key,
        "autonomy_level": "ssp1-nemoclaw-step" if ok else "blocked-ssp1-step",
        "autonomy_ready": ok,
        "selected_title": "SSP-1 / Golden Mark stable-state path",
        "chosen_action": (first.get("text") or "").split("LEARNING CARD", 1)[0].strip()[:1800],
        "runtime": runtime,
        "correction_gate": (
            "rejected first pass and reran once" if rejected_first else "not needed"
        ),
        "rejected_first_pass": rejected_first,
        "first_pass": {
            "ok": first.get("ok"),
            "text": first.get("text"),
            "error": first.get("error"),
            "policy_rejection": first.get("policy_rejection"),
            "source": first.get("source"),
            "runtime_lane": first.get("runtime_lane"),
            "provider": first.get("provider"),
            "model": first.get("model"),
            "sandbox": first.get("sandbox"),
            "agent": first.get("agent"),
            "session_file": first.get("session_file"),
            "session_id": first.get("session_id"),
            "latency_ms": first.get("latency_ms"),
        },
        "learning_card": learning_card,
        "learning_card_path": str(learning_path),
        "second_pass": {
            "ok": second.get("ok"),
            "text": second.get("text"),
            "error": second.get("error"),
            "source": second.get("source"),
            "runtime_lane": second.get("runtime_lane"),
            "provider": second.get("provider"),
            "model": second.get("model"),
            "sandbox": second.get("sandbox"),
            "agent": second.get("agent"),
            "session_file": second.get("session_file"),
            "session_id": second.get("session_id"),
            "latency_ms": second.get("latency_ms"),
        },
        "external_actions": {
            "applied": False,
            "email_sent": False,
            "stripe_live_charge": False,
            "public_post": False,
            "gate": "local research learning only; external connectors require separate receipts",
        },
        "next_gate": "Use the saved SSP-1 receipt to patch the next research-worker capability, then rerun and compare receipts.",
    }

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    json_path = RESEARCH_DIR / f"research_autonomy_{run_id}.json"
    md_path = RESEARCH_DIR / f"research_autonomy_{run_id}.md"
    state["trace_paths"] = {"json": str(json_path), "markdown": str(md_path)}
    json_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(md_path, state)
    db.save_run(f"research_autonomy_{run_id}", "golden_mark_cb5", state)
    db.log_event(
        "research_autonomy_cycle",
        {
            "run_id": run_id,
            "ok": ok,
            "runtime_lane": first.get("runtime_lane") or second.get("runtime_lane"),
            "first_session": first.get("session_file"),
            "second_session": second.get("session_file"),
            "learning_card": str(learning_path),
            "json_path": str(json_path),
            "markdown_path": str(md_path),
        },
    )

    state_for_app = dict(state)
    state_for_app["learning_card_path"] = _display_path(learning_path)
    state_for_app["trace_paths"] = {
        "json": _display_path(json_path),
        "markdown": _display_path(md_path),
    }
    STATE_PATH.write_text(json.dumps(state_for_app, indent=2, sort_keys=True), encoding="utf-8")
    return state_for_app
