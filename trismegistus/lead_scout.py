from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .wild_toads import collect_wild_toads

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "seeds" / "low_hanging_fruit_leads.json"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "lead"


def seed_leads() -> list[dict[str, Any]]:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def live_hackernews_scan(query: str, limit: int = 6) -> dict[str, Any]:
    encoded = urllib.parse.urlencode({"query": query, "tags": "story"})
    url = f"https://hn.algolia.com/api/v1/search_by_date?{encoded}"
    request = urllib.request.Request(url, headers={"User-Agent": "trismegistus-local-operator"})
    try:
        with urllib.request.urlopen(request, timeout=7) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - surfaced in UI
        return {"ok": False, "source": url, "error": str(exc), "leads": []}

    leads: list[dict[str, Any]] = []
    for item in payload.get("hits", [])[:limit]:
        title = item.get("title") or item.get("story_title") or "Untitled technical lead"
        body = item.get("comment_text") or item.get("story_text") or title
        object_id = item.get("objectID") or _slug(title)
        leads.append(
            {
                "id": f"hn-{object_id}",
                "source": "hackernews-live",
                "title": title,
                "body": re.sub(r"<[^>]+>", " ", body),
                "url": item.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                "budget_usd": None,
                "tags": ["live-scan", "technical-lead"],
            }
        )
    return {"ok": True, "source": url, "leads": leads}


def collect_leads(query: str = "freelance python debugging ai agent") -> dict[str, Any]:
    wild = collect_wild_toads()
    live_enabled = os.environ.get("TRISMEGISTUS_LIVE_SCAN", "0") == "1"
    live = live_hackernews_scan(query) if live_enabled else {"ok": False, "leads": [], "error": "disabled"}
    leads = wild.get("leads", []) + live.get("leads", [])
    return {
        "query": query,
        "wild_toads": wild,
        "live_scan": live,
        "leads": leads,
    }
