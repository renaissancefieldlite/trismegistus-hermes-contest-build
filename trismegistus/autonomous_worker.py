from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import db
from .consent_chain import run_consent_chain
from .integrations import mac_mail, model_runtime, nemoclaw, stripe_skills
from .lead_scout import collect_leads
from .operator_loop import STATE_PATH
from .opportunity_filter import rank_leads


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WORKER_DIR = DATA_DIR / "worker_runs"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _display_path(path: Path | str) -> str:
    text = str(path)
    docs = "/Users/renaissancefieldlite1.0/Documents/Playground"
    desktop = "/Users/renaissancefieldlite1.0/Desktop/PLAYGROUND"
    if text.startswith(docs):
        return desktop + text.removeprefix(docs)
    return text


def _recursive_discipline() -> dict[str, str]:
    return {
        "source_read": "Read the exact source before naming a repo, command, claim, or next action.",
        "smallest_action": "Choose the smallest review-gated move that can be checked.",
        "preflight": "Check the action against the source and gates before claiming progress.",
        "repair": "If the route fails, repair from the failed receipt instead of hand-waving.",
        "receipt": "Save JSON/Markdown trace evidence and keep raw model output in audit view.",
        "scale": "Only scale the task after the clean receipt passes.",
    }


def _write_markdown(path: Path, state: dict[str, Any]) -> None:
    selected = state.get("selected") or {}
    lead = selected.get("lead") or {}
    worker = state.get("worker_result") or {}
    consent = state.get("consent") or {}
    public_summary = state.get("public_summary") or {}
    external = state.get("external_actions") or {}
    source_attachment = state.get("source_attachment") or {}
    recursive = state.get("recursive_discipline") or {}
    mail_outreach = state.get("mail_outreach") or {}
    stripe_gig_action = state.get("stripe_gig_action") or {}
    lines = [
        f"# Trismegistus Worker Run {state.get('id')}",
        "",
        f"- Timestamp: {state.get('ts')}",
        f"- Runtime lane: {worker.get('runtime_lane') or worker.get('source') or 'blocked'}",
        f"- Provider: {worker.get('provider') or 'unknown'}",
        f"- Model: {worker.get('model') or 'unknown'}",
        f"- OpenClaw session: {worker.get('session_file') or 'none'}",
        f"- Autonomy level: {state.get('autonomy_level')}",
        f"- Autonomy ready: {state.get('autonomy_ready')}",
        "",
        "## Selected Lead",
        "",
        f"- Title: {lead.get('title')}",
        f"- Source: {lead.get('source')}",
        f"- URL: {lead.get('url')}",
        f"- Budget USD: {lead.get('budget_usd')}",
        f"- Score: {selected.get('score')}",
        f"- Status: {selected.get('status')}",
        "",
        "## Deterministic First Action",
        "",
        f"Open and inspect the exact lead URL before naming a repo or clone command: {lead.get('url')}",
        "No repository URL is considered valid unless it is visible in the lead URL or a fetched source receipt.",
        "",
        "## Public Worker Summary",
        "",
        f"- Current read: {public_summary.get('current_read')}",
        f"- Draft response: {public_summary.get('draft_response')}",
        f"- Payment lane: {public_summary.get('payment_lane')}",
        f"- External gates: {public_summary.get('external_gates')}",
        f"- Next receipt: {public_summary.get('next_receipt')}",
        "",
        "## Employee Ops",
        "",
        f"- Quadro/Mac Mail draft ready: {mail_outreach.get('ready_for_draft_packets')}",
        f"- Quadro queued not sent: {(mail_outreach.get('summary') or {}).get('queued_not_sent')}",
        f"- Stripe gig packet action: {stripe_gig_action.get('action') or 'pending'}",
        f"- Stripe live money moved: {stripe_gig_action.get('live_invoice_created', False) or stripe_gig_action.get('live_payment_link_created', False)}",
        "",
        "## Recursive Discipline",
        "",
        f"- Source read: {recursive.get('source_read')}",
        f"- Smallest action: {recursive.get('smallest_action')}",
        f"- Preflight: {recursive.get('preflight')}",
        f"- Repair: {recursive.get('repair')}",
        f"- Receipt: {recursive.get('receipt')}",
        f"- Scale: {recursive.get('scale')}",
        "",
        "## Source Attachment",
        "",
        f"- Attached: {bool(source_attachment)}",
        f"- Source URL: {source_attachment.get('source_url') or 'pending'}",
        f"- Attachment Markdown: {source_attachment.get('markdown') or 'pending'}",
        f"- Attachment JSON: {source_attachment.get('json') or 'pending'}",
        "",
        "## Review Boundary",
        "",
        f"- Final decision: {consent.get('final_decision')}",
        "",
        "## OpenClaw Worker Output",
        "",
        "Raw named-agent output is preserved in the JSON receipt under `worker_result.text`.",
        "Public claims in this Markdown receipt are controlled by deterministic lead facts, trace paths, and external action gates above.",
        "",
        f"- Raw output saved: {bool(worker.get('text'))}",
        f"- Raw output error: {worker.get('error') or 'none'}",
        "",
        "## External Action Gates",
        "",
        f"- Applied: {external.get('applied')}",
        f"- Email sent: {external.get('email_sent')}",
        f"- Stripe live charge: {external.get('stripe_live_charge')}",
        f"- Gate: {external.get('gate')}",
    ]
    path.write_text("\n".join(str(item) for item in lines), encoding="utf-8")


def run_autonomous_worker_cycle(
    query: str = "wild toads road paid technical work",
    reason: str = "manual",
) -> dict[str, Any]:
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
    stripe_action = stripe_skills.draft_payment_action(lead)
    stripe_gig_action = stripe_skills.draft_gig_collection_action(lead)
    mail_status = mac_mail.status()
    runtime = model_runtime.status()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    prompt = [
        {
            "role": "system",
            "content": (
                "You are Tris, the named OpenClaw AI expert partner. Run one bounded "
                "worker receipt. Return compact Markdown only. Do not claim external "
                "apply, email, form submission, payment, browser, account, or Stripe side effects. Do "
                "not invent placeholder receipt ids, invoice ids, issue ids, source ids, "
                "commands, API endpoints, or tool names. Use the SWE recursive task loop: "
                "source read, smallest action, preflight, repair from receipts, save trace, "
                "then scale."
            ),
        },
        {
            "role": "user",
            "content": (
                "Create one local worker packet for this paid-work lead. Use only these "
                "facts, then mark every external action as review-gated. Include: current "
                "read, draft response, first execution task, Stripe/payment draft, external "
                "action gates, next receipt to collect. The host app saves the actual "
                "JSON/Markdown receipt and OpenClaw session; do not make up a receipt "
                "label or receipt id. Do not name commands or endpoints not supplied "
                "here; if source inspection is needed, name the lead URL as the next "
                "receipt target.\n\n"
                f"Lead title: {lead.get('title')}\n"
                f"Lead URL: {lead.get('url')}\n"
                f"Source: {lead.get('source')}\n"
                f"Budget USD: {lead.get('budget_usd')}\n"
                f"Score/status: {selected.get('score')} / {selected.get('status')}\n"
                f"Review boundary: {consent.get('final_decision')}\n"
                f"Stripe draft mode: {stripe_action.get('mode') or stripe_action.get('status')}\n"
                f"Stripe employee ops: {stripe_gig_action}\n"
                f"Quadro/Mac Mail draft queue: {(mail_status.get('summary') or {}).get('queued_not_sent')} queued_not_sent; send_enabled=false\n"
                "Worker route: NemoClaw/OpenClaw direct via trismegistus-openclaw"
            ),
        },
    ]
    worker_result = nemoclaw.generate(
        prompt,
        max_tokens=520,
        session_key=f"agent:trismegistus:worker:{run_id}",
        timeout_seconds=240,
    )
    worker_ok = bool(worker_result.get("ok"))

    external_actions = {
        "applied": False,
        "email_sent": False,
        "stripe_live_charge": False,
        "gate": (
            "external apply/email/form/payment connectors require their own explicit receipts; "
            "this worker run creates the local packet only"
        ),
    }
    public_summary = {
        "current_read": (
            f"Selected paid-work lead '{lead.get('title')}' from {lead.get('source')} "
            f"with budget ${lead.get('budget_usd')} and score {selected.get('score')}."
        ),
        "draft_response": (
            "Prepare a short review-gated work note for the exact lead URL; do not "
            "claim repository access, application, or send until the source receipt exists."
        ),
        "payment_lane": (
            "Stripe stays draft/sandbox-only for gig collection and bill-pay planning until a live connector receipt is reviewed."
        ),
        "external_gates": (
            "No application, email, form, account action, browser action, bill payment, or Stripe charge was sent."
        ),
        "next_receipt": f"Inspect and save the exact lead URL receipt: {lead.get('url')}",
    }
    state = {
        "id": run_id,
        "ts": utc_now(),
        "mode": "autonomous-worker-cycle",
        "reason": reason,
        "query": query,
        "autonomy_level": "local-openclaw-worker" if worker_ok else "blocked-runtime",
        "autonomy_ready": worker_ok,
        "lead_count": len(ranked),
        "selected_lead_id": lead["id"],
        "selected_title": lead["title"],
        "selected_source": lead.get("source"),
        "selected_url": lead.get("url"),
        "selected_budget_usd": lead.get("budget_usd"),
        "selected": selected,
        "scout": scout,
        "consent": consent,
        "stripe_action": stripe_action,
        "stripe_gig_action": stripe_gig_action,
        "mail_outreach": {
            "ready_for_draft_packets": mail_status.get("ready_for_draft_packets"),
            "summary": mail_status.get("summary"),
            "next_targets": mail_status.get("next_targets"),
            "live_email_sent": False,
        },
        "runtime": runtime,
        "worker_result": {
            "ok": worker_ok,
            "text": worker_result.get("text"),
            "error": worker_result.get("error"),
            "source": worker_result.get("source"),
            "runtime_lane": worker_result.get("runtime_lane"),
            "provider": worker_result.get("provider"),
            "model": worker_result.get("model"),
            "sandbox": worker_result.get("sandbox"),
            "agent": worker_result.get("agent"),
            "session_file": worker_result.get("session_file"),
            "session_id": worker_result.get("session_id"),
            "usage": worker_result.get("usage"),
            "latency_ms": worker_result.get("latency_ms"),
        },
        "public_summary": public_summary,
        "recursive_discipline": _recursive_discipline(),
        "external_actions": external_actions,
        "next_gate": (
            "Run review-gated Quadro/Mac Mail draft packet, then Stripe sandbox employee-ops receipt. "
            "Live sends, form submissions, and money movement require explicit approval."
        ),
    }

    WORKER_DIR.mkdir(parents=True, exist_ok=True)
    json_path = WORKER_DIR / f"autonomous_worker_{run_id}.json"
    md_path = WORKER_DIR / f"autonomous_worker_{run_id}.md"
    state["trace_paths"] = {
        "json": str(json_path),
        "markdown": str(md_path),
    }
    json_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    _write_markdown(md_path, state)
    db.save_run(f"autonomous_worker_{run_id}", lead["id"], state)
    db.log_event(
        "autonomous_worker_cycle",
        {
            "run_id": run_id,
            "lead_id": lead["id"],
            "model_ok": worker_ok,
            "runtime_lane": worker_result.get("runtime_lane"),
            "provider": worker_result.get("provider"),
            "model": worker_result.get("model"),
            "session_file": worker_result.get("session_file"),
            "json_path": str(json_path),
            "markdown_path": str(md_path),
        },
    )
    state_for_app = dict(state)
    state_for_app["trace_paths"] = {
        "json": _display_path(json_path),
        "markdown": _display_path(md_path),
    }
    STATE_PATH.write_text(json.dumps(state_for_app, indent=2, sort_keys=True), encoding="utf-8")
    return state_for_app
