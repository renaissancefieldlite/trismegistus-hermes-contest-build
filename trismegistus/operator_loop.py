from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db
from .consent_chain import run_consent_chain
from .golden_mark_foundation import stable_state_system_prompt
from .integrations import mac_mail, model_runtime, stripe_skills
from .lead_scout import collect_leads
from .opportunity_filter import rank_leads


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RUN_DIR = DATA_DIR / "runs"
STATE_PATH = DATA_DIR / "agent_state.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {
            "mode": "not-started",
            "autonomy_level": "not-running",
            "autonomy_ready": False,
            "note": "No operator cycle has been saved yet.",
        }
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "mode": "state-error",
            "autonomy_level": "blocked",
            "autonomy_ready": False,
            "note": f"Could not read {STATE_PATH}",
        }


def _forecast(scored: dict[str, Any]) -> dict[str, str]:
    score = float(scored.get("score") or 0)
    status = str(scored.get("status") or "")
    if score >= 5.2 and "ready" in status:
        return {
            "label": "PLAY",
            "plain": "Good first move. Review scope, then prepare the pitch/work packet.",
        }
    if score >= 4.5:
        return {
            "label": "WATCH",
            "plain": "Worth monitoring. Needs one more read before action.",
        }
    return {
        "label": "HOLD",
        "plain": "Low priority until stronger signal appears.",
    }


def _capabilities(runtime: dict[str, Any]) -> dict[str, Any]:
    stripe = stripe_skills.status()
    mail = mac_mail.status()
    return {
        "lead_scan": "local Wild Toads Road import",
        "model_route": runtime.get("active", "none"),
        "nemohermes_model_turn": bool(runtime.get("ready")),
        "nemoclaw_autonomous_worker": False,
        "external_apply": False,
        "mac_mail_quadro_draft_packets": bool(mail.get("ready_for_draft_packets")),
        "quadro_queue_remaining": (mail.get("summary") or {}).get("queued_not_sent"),
        "email_send": False,
        "stripe_charge": bool(stripe.get("ready") and stripe.get("employee_ops", {}).get("live_charge")),
        "stripe_mode": stripe.get("enabled", "draft"),
        "stripe_employee_ops_packets": True,
        "live_money_movement": False,
    }


def run_operator_cycle(query: str = "wild toads road paid technical work", reason: str = "manual") -> dict[str, Any]:
    db.init_db()
    scout = collect_leads(query=query)
    ranked = rank_leads(scout.get("leads", []))
    if not ranked:
        raise RuntimeError("No leads collected from Wild Toads Road or live scan.")

    for item in ranked:
        db.save_lead(item["lead"], item["score"], item["status"])

    selected = ranked[0]
    lead = selected["lead"]
    consent = run_consent_chain(selected)
    forecast = _forecast(selected)
    runtime = model_runtime.status()
    capabilities = _capabilities(runtime)
    stripe_action = stripe_skills.draft_payment_action(lead)

    prompt = [
        {"role": "system", "content": stable_state_system_prompt()},
        {
            "role": "system",
            "content": (
                "You are running one Trismegistus operator-cycle. Be honest about capability: "
                "you can scan local leads, forecast, create Quadro/Mac Mail draft packets, and "
                "create Stripe employee-ops planning packets. You cannot apply, send email, "
                "submit forms, pay bills, or charge Stripe without explicit approval receipts."
            ),
        },
        {
            "role": "user",
            "content": (
                "Read this selected lead and return a concise operator note for the scoreboard. "
                "Use this shape: current read, why it is or is not a play, next action, blocked connectors.\n\n"
                f"Lead: {lead}\n\n"
                f"Score: {selected}\n\n"
                f"Quadro boundary: {consent}\n\n"
                f"Capabilities: {capabilities}"
            ),
        },
    ]
    model_note = model_runtime.generate(prompt, max_tokens=420)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    state = {
        "id": run_id,
        "ts": utc_now(),
        "mode": "watching",
        "reason": reason,
        "autonomy_level": "forecast-only",
        "autonomy_ready": False,
        "query": query,
        "lead_count": len(ranked),
        "selected_lead_id": lead["id"],
        "selected_title": lead["title"],
        "selected_source": lead.get("source"),
        "selected_url": lead.get("url"),
        "selected_budget_usd": lead.get("budget_usd"),
        "score": selected["score"],
        "status": selected["status"],
        "forecast": forecast,
        "quad_review": consent.get("final_decision"),
        "capabilities": capabilities,
        "stripe_action": stripe_action,
        "model_note": {
            "ok": bool(model_note.get("ok")),
            "text": model_note.get("text") or model_note.get("error"),
            "runtime_lane": model_note.get("runtime_lane"),
            "provider": model_note.get("provider"),
            "model": model_note.get("model"),
            "session_file": model_note.get("session_file"),
        },
        "next_gate": (
            "Wire the real NemoClaw worker loop for apply/email actions. Until then, "
            "Trismegistus is a live model-guided scout/forecast board with Quadro/Mac Mail "
            "draft packets and Stripe employee-ops packets, not an autonomous sender or payer."
        ),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    run_path = RUN_DIR / f"operator_cycle_{run_id}.json"
    run_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    db.save_run(f"operator_cycle_{run_id}", lead["id"], state)
    db.log_event(
        "operator_cycle",
        {
            "run_id": run_id,
            "lead_id": lead["id"],
            "forecast": forecast["label"],
            "autonomy_level": state["autonomy_level"],
            "model_ok": bool(model_note.get("ok")),
            "run_path": str(run_path),
        },
    )
    state["run_path"] = str(run_path)
    return state
