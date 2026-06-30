from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PLAYGROUND = ROOT.parent
QUADRO_OUTREACH_DIR = (
    PLAYGROUND
    / "band_of_agents_quadro"
    / "outreach"
    / "quadro_company_outreach_2026-06-22"
)
QUEUE_PATH = QUADRO_OUTREACH_DIR / "GENERATED_EMAIL_QUEUE_100.psv"
GENERATED_EMAILS_PATH = QUADRO_OUTREACH_DIR / "GENERATED_EMAILS_100_FOR_APPROVAL.md"
PITCHED_LIST_PATH = QUADRO_OUTREACH_DIR / "PITCHED_LIST.md"
OPERATOR_LOG_PATH = PLAYGROUND / "band_of_agents_quadro" / "docs" / "QUADRO_OPERATOR_LOG.md"

DATA_DIR = ROOT / "data" / "mac_mail_drafts"
RFL_MAIL_DIR = ROOT / "data" / "rfl_mail_actions"
SEND_APPROVAL_PHRASE = "APPROVE RFL MAC MAIL SEND"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _mail_app_path() -> str | None:
    for candidate in (Path("/System/Applications/Mail.app"), Path("/Applications/Mail.app")):
        if candidate.exists():
            return str(candidate)
    return None


def _safe_slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:80] or "quadro-draft"


def load_quadro_queue() -> list[dict[str, str]]:
    if not QUEUE_PATH.exists():
        return []
    with QUEUE_PATH.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="|")]


def _status_bucket(status: str) -> str:
    status_l = (status or "").lower()
    if "bounced" in status_l:
        return "bounced_not_live"
    if "generated_not_sent" in status_l:
        return "queued_not_sent"
    if "application_submitted" in status_l:
        return "submitted_or_application_pending"
    if "reply_received" in status_l or "ticket" in status_l or "support_replied" in status_l:
        return "reply_or_support_route"
    if "sent_" in status_l or "sent_by_dean" in status_l:
        return "sent_waiting"
    return "unknown"


def _queue_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    summary = {
        "total": len(rows),
        "queued_not_sent": 0,
        "sent_waiting": 0,
        "submitted_or_application_pending": 0,
        "reply_or_support_route": 0,
        "bounced_not_live": 0,
        "unknown": 0,
    }
    for row in rows:
        bucket = _status_bucket(row.get("status", ""))
        summary[bucket] = summary.get(bucket, 0) + 1
    return summary


def _row_rank(row: dict[str, str]) -> int:
    try:
        return int(row.get("rank", "9999"))
    except ValueError:
        return 9999


def next_targets(limit: int = 8, include_portal_routes: bool = True) -> list[dict[str, str]]:
    rows = load_quadro_queue()
    candidates = [row for row in rows if _status_bucket(row.get("status", "")) == "queued_not_sent"]
    if not include_portal_routes:
        candidates = [row for row in candidates if "@" in row.get("route", "")]
    priority_order = {"A": 0, "B": 1, "C": 2}
    candidates.sort(key=lambda row: (priority_order.get(row.get("priority", "C"), 9), _row_rank(row)))
    return candidates[: max(0, limit)]


def _queued_route_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    queued = [row for row in rows if _status_bucket(row.get("status", "")) == "queued_not_sent"]
    direct_email = [
        row
        for row in queued
        if "@" in row.get("route", "") and "http" not in row.get("route", "").lower()
    ]
    return {
        "queued_total": len(queued),
        "direct_email_targets": len(direct_email),
        "portal_or_contact_targets": len(queued) - len(direct_email),
    }


def _section_for_rank(rank: int) -> str:
    if not GENERATED_EMAILS_PATH.exists():
        return ""
    text = GENERATED_EMAILS_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(^##\s+{rank:03d}\.\s+.*?)(?=^##\s+\d{{3}}\.\s+|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _extract_code_block(section: str, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}:\s*\n\n```text\n(.*?)\n```", re.DOTALL)
    match = pattern.search(section)
    return match.group(1).strip() if match else ""


def draft_for_row(row: dict[str, str]) -> dict[str, Any]:
    rank = _row_rank(row)
    section = _section_for_rank(rank)
    subject = _extract_code_block(section, "Subject") or row.get("subject", "").strip()
    body = _extract_code_block(section, "Body")
    if not body:
        body = (
            "Hi partner team,\n\n"
            "I am Dean Patterson, founder of Renaissance Field Lite. I am reaching out about "
            f"Quadro CSI for {row.get('company', 'your team')}.\n\n"
            "Quadro creates review-gated decision packets for evidence, authority, policy, "
            "and human signoff before high-risk workflow actions proceed.\n\n"
            "Demo: https://renaissancefieldlite.com/quadro-csi/\n"
            "GitHub: https://github.com/renaissancefieldlite/quadro-csi\n\n"
            "Would your team be open to reviewing Quadro as a small pilot or partner concept?\n\n"
            "Dean Patterson\n"
            "Renaissance Field Lite\n"
            "https://renaissancefieldlite.com/"
        )
    route = row.get("route", "").strip()
    route_kind = "email" if "@" in route and "http" not in route.lower() else "partner_portal_or_contact_route"
    return {
        "rank": row.get("rank"),
        "company": row.get("company"),
        "category": row.get("category"),
        "priority": row.get("priority"),
        "stage": row.get("stage"),
        "route": route,
        "route_kind": route_kind,
        "status": row.get("status"),
        "subject": subject,
        "body": body,
        "source_section_found": bool(section),
    }


def _write_eml(path: Path, draft: dict[str, Any]) -> None:
    msg = EmailMessage()
    msg["Subject"] = str(draft.get("subject") or "")
    msg["From"] = "Dean Patterson <dean@renaissancefieldlite.com>"
    if draft.get("route_kind") == "email":
        msg["To"] = str(draft.get("route") or "")
    else:
        msg["To"] = ""
    msg.set_content(str(draft.get("body") or ""))
    path.write_text(msg.as_string(), encoding="utf-8")


def _direct_email_address(value: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value or "", re.IGNORECASE)
    return match.group(0) if match else ""


def mail_control_status() -> dict[str, Any]:
    return {
        "mail_app_path": _mail_app_path(),
        "mail_app_available": bool(_mail_app_path()),
        "draft_bridge_ready": bool(_mail_app_path()),
        "send_env_enabled": os.environ.get("TRIS_ALLOW_MAC_MAIL_SEND", "0") == "1",
        "send_approval_phrase": SEND_APPROVAL_PHRASE,
        "live_send_default": False,
        "requires_human_approval": True,
        "boundary": (
            "Apple Mail bridge can create visible local drafts and save receipts. "
            "Live sending requires TRIS_ALLOW_MAC_MAIL_SEND=1 plus the exact approval phrase."
        ),
    }


def _run_apple_mail_message(
    recipient: str,
    subject: str,
    body: str,
    *,
    send_now: bool = False,
) -> dict[str, Any]:
    script = """
on run argv
  set recipientAddress to item 1 of argv
  set messageSubject to item 2 of argv
  set messageBody to item 3 of argv
  set sendNow to item 4 of argv
  tell application "Mail"
    activate
    set newMessage to make new outgoing message with properties {subject:messageSubject, content:messageBody, visible:true}
    tell newMessage
      make new to recipient at end of to recipients with properties {address:recipientAddress}
    end tell
    if sendNow is "1" then
      send newMessage
    end if
  end tell
end run
"""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                script,
                recipient,
                subject,
                body,
                "1" if send_now else "0",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=35,
        )
    except Exception as exc:  # noqa: BLE001 - receipt needs the local blocker
        return {
            "ok": False,
            "stdout": "",
            "stderr": "",
            "error": str(exc),
        }
    return {
        "ok": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
    }


def create_rfl_mail_action(
    *,
    recipient: str,
    subject: str,
    body: str,
    reason: str = "tris-rfl-mail",
    create_visible_draft: bool = True,
    send_now: bool = False,
    approval_phrase: str = "",
) -> dict[str, Any]:
    RFL_MAIL_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    action_dir = RFL_MAIL_DIR / f"rfl_mail_{run_id}"
    action_dir.mkdir(parents=True, exist_ok=True)

    email = _direct_email_address(recipient)
    subject = (subject or "Renaissance Field Lite follow-up").strip()
    body = (body or "").strip()
    if not body:
        body = (
            "Hi,\n\n"
            "Dean Patterson here with Renaissance Field Lite. I wanted to follow up with a short "
            "review-gated packet and keep the next step receipt-bound.\n\n"
            "Best,\n"
            "Dean Patterson\n"
            "Renaissance Field Lite\n"
            "https://renaissancefieldlite.com/"
        )

    eml_draft = {
        "route_kind": "email",
        "route": email,
        "subject": subject,
        "body": body,
    }
    eml_path = action_dir / "rfl_mail_action.eml"
    _write_eml(eml_path, eml_draft)

    blocked_reason = ""
    live_send_allowed = (
        send_now
        and os.environ.get("TRIS_ALLOW_MAC_MAIL_SEND", "0") == "1"
        and approval_phrase.strip() == SEND_APPROVAL_PHRASE
    )
    if send_now and not live_send_allowed:
        blocked_reason = (
            "Live send blocked. Requires TRIS_ALLOW_MAC_MAIL_SEND=1 and exact approval phrase: "
            f"{SEND_APPROVAL_PHRASE}"
        )

    action_result: dict[str, Any]
    if not email:
        action_result = {
            "ok": False,
            "error": "Direct recipient email address is required for Mac Mail draft/send.",
        }
    elif send_now and not live_send_allowed:
        action_result = {
            "ok": False,
            "error": blocked_reason,
        }
    elif create_visible_draft or send_now:
        action_result = _run_apple_mail_message(email, subject, body, send_now=send_now)
    else:
        action_result = {
            "ok": True,
            "note": "Receipt and .eml written; visible Mail draft not requested.",
        }

    receipt = {
        "id": run_id,
        "ts": utc_now(),
        "reason": reason,
        "action": "send_approved" if send_now else "create_visible_draft",
        "recipient": email,
        "subject": subject,
        "body_preview": body[:500],
        "eml_path": str(eml_path),
        "mail_app_path": _mail_app_path(),
        "create_visible_draft": create_visible_draft,
        "send_requested": send_now,
        "send_env_enabled": os.environ.get("TRIS_ALLOW_MAC_MAIL_SEND", "0") == "1",
        "approval_phrase_matched": approval_phrase.strip() == SEND_APPROVAL_PHRASE,
        "live_email_sent": bool(send_now and live_send_allowed and action_result.get("ok")),
        "requires_human_approval": True,
        "result": action_result,
        "boundary": (
            "This is the RFL Apple Mail bridge. Draft creation is local and visible. "
            "Live send is blocked unless the env flag and approval phrase are both present."
        ),
    }
    json_path = action_dir / "rfl_mail_action.json"
    md_path = action_dir / "rfl_mail_action.md"
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    md_lines = [
        f"# RFL Mac Mail Action {run_id}",
        "",
        f"- Timestamp: {receipt['ts']}",
        f"- Reason: {reason}",
        f"- Recipient: {email or 'missing'}",
        f"- Subject: {subject}",
        f"- Action: {receipt['action']}",
        f"- Visible draft requested: {create_visible_draft}",
        f"- Send requested: {send_now}",
        f"- Live email sent: {receipt['live_email_sent']}",
        f"- Result ok: {action_result.get('ok')}",
        f"- EML: {eml_path}",
        "",
        "## Boundary",
        "",
        str(receipt["boundary"]),
        "",
        "## Body",
        "",
        "```text",
        body,
        "```",
        "",
    ]
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    receipt["paths"] = {"directory": str(action_dir), "json": str(json_path), "markdown": str(md_path)}
    return receipt


def _create_visible_mail_draft(draft: dict[str, Any]) -> dict[str, Any]:
    if draft.get("route_kind") != "email":
        return {
            "company": draft.get("company"),
            "action": "portal_copy_ready",
            "ok": True,
            "mail_draft_created": False,
            "route": draft.get("route"),
            "note": "Target route is a partner portal/contact URL, not a direct email address.",
        }
    script = """
on run argv
  set recipientAddress to item 1 of argv
  set messageSubject to item 2 of argv
  set messageBody to item 3 of argv
  tell application "Mail"
    activate
    set newMessage to make new outgoing message with properties {subject:messageSubject, content:messageBody, visible:true}
    tell newMessage
      if recipientAddress is not "" then
        make new to recipient at end of to recipients with properties {address:recipientAddress}
      end if
    end tell
  end tell
end run
"""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                script,
                str(draft.get("route") or ""),
                str(draft.get("subject") or ""),
                str(draft.get("body") or ""),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=25,
        )
    except Exception as exc:  # noqa: BLE001 - receipt needs the exact local blocker
        return {
            "company": draft.get("company"),
            "action": "mac_mail_visible_draft",
            "ok": False,
            "mail_draft_created": False,
            "error": str(exc),
        }
    return {
        "company": draft.get("company"),
        "action": "mac_mail_visible_draft",
        "ok": result.returncode == 0,
        "mail_draft_created": result.returncode == 0,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def _open_portal_route(draft: dict[str, Any]) -> dict[str, Any]:
    route = str(draft.get("route") or "").strip()
    if not route.startswith(("http://", "https://")):
        return {
            "company": draft.get("company"),
            "action": "open_partner_portal",
            "ok": False,
            "opened": False,
            "error": "Route is not a web URL.",
        }
    result = subprocess.run(["open", route], check=False, capture_output=True, text=True, timeout=10)
    return {
        "company": draft.get("company"),
        "action": "open_partner_portal",
        "ok": result.returncode == 0,
        "opened": result.returncode == 0,
        "route": route,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "note": "Portal opened only. No form was submitted.",
    }


def create_quadro_draft_packet(
    limit: int = 3,
    reason: str = "manual",
    create_mail_drafts: bool = False,
    open_portals: bool = False,
) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = next_targets(limit=limit)
    drafts = [draft_for_row(row) for row in rows]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    packet_dir = DATA_DIR / f"quadro_mac_mail_packet_{run_id}"
    packet_dir.mkdir(parents=True, exist_ok=True)

    eml_paths: list[str] = []
    movement_actions: list[dict[str, Any]] = []
    for draft in drafts:
        slug = _safe_slug(f"{draft.get('rank')}-{draft.get('company')}")
        eml_path = packet_dir / f"{slug}.eml"
        _write_eml(eml_path, draft)
        eml_paths.append(str(eml_path))
        if create_mail_drafts:
            movement_actions.append(_create_visible_mail_draft(draft))
        elif open_portals and draft.get("route_kind") == "partner_portal_or_contact_route":
            movement_actions.append(_open_portal_route(draft))
        else:
            movement_actions.append(
                {
                    "company": draft.get("company"),
                    "action": (
                        "portal_copy_ready"
                        if draft.get("route_kind") == "partner_portal_or_contact_route"
                        else "eml_ready"
                    ),
                    "ok": True,
                    "mail_draft_created": False,
                    "portal_opened": False,
                }
            )

    receipt = {
        "id": run_id,
        "ts": utc_now(),
        "reason": reason,
        "mode": os.environ.get("MAC_MAIL_MODE", "draft"),
        "send_enabled": False,
        "live_email_sent": False,
        "requires_human_approval": True,
        "approval_gate": [
            "company",
            "recipient or partner/form route",
            "subject",
            "message body",
            "attachment/link policy",
        ],
        "queue_path": str(QUEUE_PATH),
        "generated_emails_path": str(GENERATED_EMAILS_PATH),
        "pitched_list_path": str(PITCHED_LIST_PATH),
        "drafts": drafts,
        "eml_paths": eml_paths,
        "movement_actions": movement_actions,
        "boundary": (
            "This creates local Mac Mail-compatible .eml handoff files and JSON/Markdown receipts. "
            "When explicitly requested it can open visible Mail drafts for direct email routes or open portal URLs. "
            "It does not send email, submit partner forms, or mark outreach complete."
        ),
    }
    json_path = packet_dir / "quadro_mac_mail_packet.json"
    md_path = packet_dir / "quadro_mac_mail_packet.md"
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        f"# Quadro Mac Mail Draft Packet {run_id}",
        "",
        f"- Timestamp: {receipt['ts']}",
        f"- Reason: {reason}",
        "- Live email sent: false",
        "- Requires approval: true",
        f"- Queue: {QUEUE_PATH}",
        "",
        "## Drafts",
        "",
    ]
    for draft, eml_path, movement in zip(drafts, eml_paths, movement_actions):
        lines.extend(
            [
                f"### {draft.get('rank')}. {draft.get('company')}",
                "",
                f"- Priority: {draft.get('priority')}",
                f"- Category: {draft.get('category')}",
                f"- Route kind: {draft.get('route_kind')}",
                f"- Route: {draft.get('route')}",
                f"- Subject: {draft.get('subject')}",
                f"- EML: {eml_path}",
                f"- Movement action: {movement.get('action')}",
                f"- Mail draft created: {movement.get('mail_draft_created', False)}",
                f"- Portal opened: {movement.get('opened', False)}",
                "",
                "```text",
                str(draft.get("body") or ""),
                "```",
                "",
            ]
        )
    lines.extend(["## Boundary", "", str(receipt["boundary"]), ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    receipt["paths"] = {"directory": str(packet_dir), "json": str(json_path), "markdown": str(md_path)}
    return receipt


def status() -> dict[str, Any]:
    rows = load_quadro_queue()
    summary = _queue_summary(rows)
    route_counts = _queued_route_counts(rows)
    return {
        "name": "Mac Mail / Quadro Outreach",
        "mode": os.environ.get("MAC_MAIL_MODE", "draft"),
        "mail_app_path": _mail_app_path(),
        "queue_path": str(QUEUE_PATH),
        "queue_exists": QUEUE_PATH.exists(),
        "generated_emails_path": str(GENERATED_EMAILS_PATH),
        "generated_emails_exists": GENERATED_EMAILS_PATH.exists(),
        "pitched_list_path": str(PITCHED_LIST_PATH),
        "operator_log_path": str(OPERATOR_LOG_PATH),
        "ready_for_draft_packets": bool(rows and GENERATED_EMAILS_PATH.exists()),
        "real_movement_ready": bool(rows and GENERATED_EMAILS_PATH.exists() and _mail_app_path()),
        "rfl_mail_bridge": mail_control_status(),
        "send_enabled": False,
        "live_email_sent": False,
        "requires_human_approval": True,
        "summary": summary,
        "route_counts": route_counts,
        "next_targets": [
            {
                "rank": row.get("rank"),
                "company": row.get("company"),
                "category": row.get("category"),
                "priority": row.get("priority"),
                "stage": row.get("stage"),
                "route": row.get("route"),
                "status": row.get("status"),
            }
            for row in next_targets(limit=6)
        ],
        "note": (
            "Reads the Quadro 100-company queue and creates local Mac Mail/form handoff drafts. "
            "Remaining queued routes are mostly partner portals/contact pages; direct Mail drafts are used only for direct email routes. "
            "Sending and partner-form submission stay approval-gated."
        ),
    }
