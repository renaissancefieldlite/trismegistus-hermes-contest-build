from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "stripe_employee_ops"
STRIPE_API_BASE = "https://api.stripe.com/v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def status() -> dict[str, Any]:
    enabled = os.environ.get("STRIPE_ENABLED", "draft").strip().lower()
    key_present = bool(os.environ.get("STRIPE_SECRET_KEY", "").strip())
    publishable_present = bool(os.environ.get("STRIPE_PUBLISHABLE_KEY", "").strip())
    sandbox_ready = enabled in {"sandbox", "test"} and key_present
    live_ready = enabled == "live" and key_present
    return {
        "name": "Stripe Skills",
        "mode": enabled,
        "enabled": enabled,
        "key_present": key_present,
        "publishable_key_present": publishable_present,
        "ready": live_ready,
        "sandbox_ready": sandbox_ready,
        "payment_link_ready": sandbox_ready,
        "draft_safe": enabled != "live",
        "live_money_movement_enabled": False,
        "requires_human_approval": True,
        "employee_ops": {
            "quote_invoice_drafts": True,
            "gig_collection_packets": True,
            "bill_pay_planning": True,
            "bill_pay_orchestration": True,
            "live_bill_pay": False,
            "live_charge": live_ready and os.environ.get("STRIPE_ALLOW_LIVE_CHARGES", "0") == "1",
            "outgoing_bill_pay_route": "stripe_issuing_virtual_card_or_operator_card",
            "inbound_collection_route": "stripe_payment_links",
        },
        "note": (
            "Draft/sandbox mode prepares payment, invoice, gig collection, and bill-pay planning packets only. "
            "Payment Links collect money for RFL; outgoing bill pay needs a card/Issuing route and a separate live approval gate."
        ),
    }


def setup_status() -> dict[str, Any]:
    state = status()
    missing_required: list[str] = []
    missing_recommended: list[str] = []
    if not state["publishable_key_present"]:
        missing_recommended.append("STRIPE_PUBLISHABLE_KEY")
    if not state["key_present"]:
        missing_required.append("STRIPE_SECRET_KEY")
    if state["mode"] not in {"sandbox", "test", "live"}:
        missing_required.append("STRIPE_ENABLED=sandbox")
    return {
        "ok": not missing_required,
        "sandbox_ready": state["sandbox_ready"],
        "payment_link_ready": state["sandbox_ready"],
        "live_ready": state["ready"],
        "live_money_movement_enabled": state["live_money_movement_enabled"],
        "missing": missing_required,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "safe_env_template": [
            "STRIPE_ENABLED=sandbox",
            "STRIPE_PUBLISHABLE_KEY=pk_test_...",
            "STRIPE_SECRET_KEY=sk_test_...",
            "STRIPE_ALLOW_LIVE_CHARGES=0",
        ],
        "boundary": (
            "Use sandbox/test keys for showtime integration. Never store keys in logs or public docs. "
            "Live charges remain disabled unless STRIPE_ENABLED=live and STRIPE_ALLOW_LIVE_CHARGES=1 are both set after explicit approval."
        ),
    }


def _stripe_secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def _stripe_post(path: str, params: list[tuple[str, str]]) -> dict[str, Any]:
    key = _stripe_secret_key()
    if not key:
        return {"ok": False, "error": "STRIPE_SECRET_KEY is not configured."}
    credentials = base64.b64encode(f"{key}:".encode("utf-8")).decode("ascii")
    data = parse.urlencode(params).encode("utf-8")
    req = request.Request(
        f"{STRIPE_API_BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        return {"ok": True, "stripe": payload}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "status": exc.code, "error": detail[:1200]}
    except Exception as exc:  # noqa: BLE001 - receipt needs the exact connector blocker
        return {"ok": False, "error": str(exc)}


def _sanitize_stripe_object(obj: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "object",
        "active",
        "application",
        "created",
        "currency",
        "livemode",
        "metadata",
        "url",
        "amount_total",
        "status",
    }
    return {key: value for key, value in obj.items() if key in allowed}


def create_test_payment_link(payload: dict[str, Any]) -> dict[str, Any]:
    setup = setup_status()
    if not setup["payment_link_ready"]:
        return {
            "ok": False,
            "action": "stripe_test_payment_link",
            "setup": setup,
            "error": "Stripe sandbox keys are not configured in local .env.",
            "live_money_moved": False,
        }
    if status()["enabled"] not in {"sandbox", "test"}:
        return {
            "ok": False,
            "action": "stripe_test_payment_link",
            "setup": setup,
            "error": "Payment links are only enabled for STRIPE_ENABLED=sandbox or test in this lane.",
            "live_money_moved": False,
        }
    amount = payload.get("amount_usd") or payload.get("amount") or 67
    try:
        amount_usd = float(amount)
    except (TypeError, ValueError):
        amount_usd = 67.0
    amount_usd = max(1.0, min(amount_usd, 10000.0))
    cents = int(round(amount_usd * 100))
    service_title = str(payload.get("service_title") or "Renaissance Field Lite expert services").strip()
    description = str(
        payload.get("description")
        or "Review-gated Trismegistus/Quadro pilot or scoped expert-services packet."
    ).strip()
    params = [
        ("line_items[0][price_data][currency]", "usd"),
        ("line_items[0][price_data][unit_amount]", str(cents)),
        ("line_items[0][price_data][product_data][name]", service_title[:250]),
        ("line_items[0][price_data][product_data][description]", description[:1000]),
        ("line_items[0][quantity]", "1"),
        ("metadata[source]", "trismegistus"),
        ("metadata[lane]", str(payload.get("lane") or "employee_ops")),
        ("metadata[approval_state]", "review_gated"),
        ("after_completion[type]", "hosted_confirmation"),
        (
            "after_completion[hosted_confirmation][custom_message]",
            "Thanks. Renaissance Field Lite will review the receipt before fulfillment.",
        ),
    ]
    result = _stripe_post("/payment_links", params)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    receipt = {
        "id": run_id,
        "ts": utc_now(),
        "action": "stripe_test_payment_link",
        "request": {
            "amount_usd": amount_usd,
            "amount_cents": cents,
            "currency": "usd",
            "service_title": service_title,
            "lane": payload.get("lane") or "employee_ops",
        },
        "ok": bool(result.get("ok")),
        "stripe_object": _sanitize_stripe_object(result.get("stripe") or {}) if result.get("ok") else {},
        "error": result.get("error"),
        "status": result.get("status"),
        "livemode": bool((result.get("stripe") or {}).get("livemode")),
        "live_money_moved": False,
        "live_charge_created": False,
        "requires_human_approval": True,
        "boundary": (
            "Creates a real Stripe test-mode Payment Link when sandbox keys are configured. "
            "It does not charge a card by itself, send an invoice, or enable live money movement."
        ),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"stripe_payment_link_{run_id}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["path"] = str(path)
    return receipt


def draft_payment_action(lead: dict[str, Any]) -> dict[str, Any]:
    amount = lead.get("budget_usd") or 100
    cents = int(amount * 100)
    return {
        "mode": os.environ.get("STRIPE_ENABLED", "draft"),
        "action": "draft_payment_intent",
        "amount_usd": amount,
        "amount_cents": cents,
        "currency": "usd",
        "description": f"Trismegistus scoped service packet: {lead.get('title', '')}",
        "live_charge_created": False,
        "requires_human_approval": True,
    }


def draft_gig_collection_action(lead: dict[str, Any], service_title: str | None = None) -> dict[str, Any]:
    amount = lead.get("budget_usd") or 100
    return {
        "mode": os.environ.get("STRIPE_ENABLED", "draft"),
        "action": "draft_quote_or_invoice_packet",
        "service_title": service_title or f"Trismegistus scoped work packet: {lead.get('title', '')}",
        "customer_or_lead": lead.get("source") or lead.get("id") or "review_required",
        "amount_usd": amount,
        "currency": "usd",
        "collection_goal": "collect approved paid-work revenue for Renaissance Field Lite",
        "live_invoice_created": False,
        "live_payment_link_created": False,
        "requires_human_approval": True,
    }


def draft_bill_pay_action(bill: dict[str, Any]) -> dict[str, Any]:
    amount = bill.get("amount_usd") or bill.get("amount") or 0
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0.0
    return {
        "mode": os.environ.get("STRIPE_ENABLED", "draft"),
        "action": "draft_bill_pay_plan",
        "vendor": bill.get("vendor") or "review_required",
        "amount_usd": amount,
        "due_date": bill.get("due_date") or "review_required",
        "funding_source": bill.get("funding_source") or "Stripe balance / bank account review required",
        "vendor_payment_url": bill.get("vendor_payment_url") or bill.get("url") or "review_required",
        "orchestration_route": "visible_browser_checkout_with_human_final_approval",
        "stripe_route_truth": {
            "payment_links": "inbound_collection_only",
            "issuing_virtual_card": "correct Stripe route for controlled outgoing card spend if enabled",
            "current_live_outgoing_bill_pay": False,
        },
        "agent_steps": [
            "verify vendor, amount, due date, account context, and payment URL",
            "create or select an approved funding instrument; Stripe Issuing virtual card is preferred when enabled",
            "apply spend controls at or slightly above the approved amount and restrict the card to online bill-pay use where possible",
            "open the vendor checkout in visible Chrome and fill only non-sensitive fields that are approved",
            "pause at final payment review for explicit operator confirmation",
            "after payment, save vendor receipt plus Stripe/card authorization metadata without storing full card data",
        ],
        "sensitive_data_policy": "Do not log full card number, CVV, OTP, password, or Boost account secrets.",
        "live_bill_paid": False,
        "live_money_moved": False,
        "requires_human_approval": True,
        "boundary": (
            "Tris may prepare a bill-pay checklist and payment packet. Payment Links are for collecting RFL revenue, "
            "not paying Boost. Live bill pay requires an approved card/Stripe Issuing route, visible checkout, "
            "operator confirmation at the final payment button, and a separate receipt."
        ),
    }


def save_employee_ops_receipt(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt = {
        "id": run_id,
        "ts": utc_now(),
        "kind": kind,
        "stripe_status": status(),
        "payload": payload,
        "live_money_moved": False,
        "requires_human_approval": True,
    }
    path = DATA_DIR / f"stripe_{kind}_{run_id}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    receipt["path"] = str(path)
    return receipt
