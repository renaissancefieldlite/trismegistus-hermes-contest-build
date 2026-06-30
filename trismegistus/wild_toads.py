from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


GIG_SCOUT_ROOT = Path("/Users/renaissancefieldlite1.0/Documents/Playground/gig_scout")
OUTPUT_DIR = GIG_SCOUT_ROOT / "output"
LATEST_RESULTS = OUTPUT_DIR / "latest_results.json"
LEADS_DIR = OUTPUT_DIR / "leads"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:96] or "wild-toads-lead"


def _money(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(value).replace(",", ""))
    if not match:
        return None
    try:
        return int(round(float(match.group(1))))
    except ValueError:
        return None


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _normalize(item: dict[str, Any], source_path: Path | None = None) -> dict[str, Any] | None:
    snapshot = item.get("packet_snapshot") if isinstance(item.get("packet_snapshot"), dict) else {}
    title = _clean(item.get("title") or snapshot.get("title"))
    if not title:
        return None

    source_id = _clean(item.get("source_id") or snapshot.get("lead_id") or item.get("lead_id") or title)
    lead_id = _clean(item.get("lead_id") or source_id or title)
    body = _clean(
        item.get("excerpt")
        or snapshot.get("excerpt")
        or item.get("next_action")
        or snapshot.get("reply_draft")
        or item.get("reply_draft")
        or title
    )
    categories = item.get("categories") or snapshot.get("categories") or []
    if isinstance(categories, str):
        categories = [categories]
    tags = [str(tag) for tag in categories if str(tag).strip()]
    tags.extend(["wild-toads-road", "real-intake"])

    budget = _money(item.get("pay_hint") or snapshot.get("pay_hint"))
    source = _clean(item.get("source") or snapshot.get("source") or "wild-toads-road")
    url = _clean(item.get("url") or snapshot.get("url") or f"local://wild-toads/{_slug(lead_id)}")
    normalized = {
        "id": f"wild-{_slug(lead_id)}",
        "source": source,
        "title": title,
        "body": body,
        "url": url,
        "budget_usd": budget,
        "tags": tags,
        "wild_toads": {
            "lead_id": lead_id,
            "source_id": source_id,
            "status": item.get("status") or snapshot.get("status"),
            "next_action": item.get("next_action"),
            "pay_hint": item.get("pay_hint") or snapshot.get("pay_hint"),
            "profile_brand": item.get("profile_brand") or "Wild Toads Road",
            "source_file": str(source_path) if source_path else str(LATEST_RESULTS),
            "scope_questions": snapshot.get("scope_questions") or [],
            "execution_plan": snapshot.get("execution_plan") or [],
            "recommended_worker": snapshot.get("recommended_worker"),
        },
    }
    return normalized


def collect_wild_toads(limit: int = 40) -> dict[str, Any]:
    leads: list[dict[str, Any]] = []
    seen: set[str] = set()

    if LEADS_DIR.exists():
        files = sorted(LEADS_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in files:
            item = _load_json(path)
            if isinstance(item, dict):
                normalized = _normalize(item, path)
                key = (normalized["url"] or normalized["id"]) if normalized else ""
                if normalized and key not in seen:
                    leads.append(normalized)
                    seen.add(key)
            if len(leads) >= limit:
                break

    latest = _load_json(LATEST_RESULTS)
    if isinstance(latest, dict):
        for item in latest.get("items", []):
            if isinstance(item, dict):
                normalized = _normalize(item, LATEST_RESULTS)
                key = (normalized["url"] or normalized["id"]) if normalized else ""
                if normalized and key not in seen:
                    leads.append(normalized)
                    seen.add(key)

    return {
        "ok": bool(leads),
        "source": "Wild Toads Road / gig_scout",
        "root": str(GIG_SCOUT_ROOT),
        "latest_results": str(LATEST_RESULTS),
        "lead_count": len(leads[:limit]),
        "leads": leads[:limit],
    }
