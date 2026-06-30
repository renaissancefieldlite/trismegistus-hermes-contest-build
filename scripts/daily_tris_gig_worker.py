#!/usr/bin/env python3
from __future__ import annotations

import argparse
import email.message
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PLAYGROUND = ROOT.parent
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "gig_applications"
PROGRESS_LOG = ROOT / "docs" / "TRISMEGISTUS_DEMO_PROGRESS_LOG_2026-06-18.md"
RICK_LOG = PLAYGROUND / "codex(ricks thoughts) playground log.md"
MAILBOX_NAMES = [
    "Tris Gigs",
    "Tris Gigs/Ready To Apply",
    "Tris Gigs/Sent Applications",
    "Tris Gigs/Needs Route",
    "Tris Gigs/Receipts",
]
MIN_STRICT_SCORE = 4.5
DEFAULT_MIN_BUDGET_USD = 20
DEFAULT_MIN_SCORE = 4.5
ALGORA_TRANSACTIONS_URL = os.environ.get("TRIS_ALGORA_TRANSACTIONS_URL", "https://algora.io/user/transactions")
BOUNTY_PLATFORM_REGISTRY = [
    {
        "platform": "Algora",
        "url": "https://algora.io/",
        "best_for": "open-source GitHub issue bounties and PR-merge bounty tracking",
        "tris_route": "GitHub issue search plus Algora transaction receipt tracking",
        "payment": "Algora payout flow with Stripe-connected tracking when available",
    },
    {
        "platform": "Opire",
        "url": "https://opire.dev/home",
        "best_for": "open-source GitHub issue bounties where anyone can fund issues",
        "tris_route": "GitHub issue search for Opire/bounty labels, then PR-first delivery",
        "payment": "Opire payout route; verify fiat or crypto receipt before marking paid",
    },
    {
        "platform": "Replit Bounties",
        "url": "https://replit.com/blog/bounties",
        "best_for": "browser-delivered project specs and MVP/build tasks",
        "tris_route": "visible browser marketplace review, then browser/project delivery gate",
        "payment": "Replit/marketplace payment receipt required before paid status",
    },
    {
        "platform": "Gitcoin",
        "url": "https://gitcoin.co/mechanisms/bounties",
        "best_for": "Web3, open-source documentation, dapp tooling, scripts, and integrations",
        "tris_route": "Gitcoin bounty/grant discovery, wallet/payment-gated submission tracking",
        "payment": "Gitcoin/Web3 payout receipt required before paid status",
    },
]

sys.path.insert(0, str(ROOT))

from trismegistus import db  # noqa: E402
from trismegistus.wild_toads import collect_wild_toads  # noqa: E402


LOW_HANGING_TERMS = {
    "api",
    "automation",
    "bug",
    "dashboard",
    "debug",
    "django",
    "fastapi",
    "fix",
    "javascript",
    "next.js",
    "node",
    "python",
    "react",
    "script",
    "svelte",
    "sveltekit",
    "typescript",
    "wordpress",
}

HARD_FILTER_TERMS = {
    "account executive",
    "art director",
    "campaign manager",
    "game tester",
    "inside sales",
    "engineering manager",
    "field reliability engineer",
    "senior director",
    "director",
    "head of sales",
    "product manager",
    "sap pp consultant",
    "process data consultant",
    "sales assistant",
    "staff engineer",
    "technical support",
    "tech lead",
    "principal",
    "clearance",
    "onsite",
    "hybrid",
    "internship",
    "unpaid",
}

TITLE_CODING_SIGNAL_TERMS = {
    "api",
    "backend",
    "bug",
    "code",
    "developer",
    "devops",
    "django",
    "engineer",
    "fastapi",
    "frontend",
    "full-stack",
    "javascript",
    "next.js",
    "node",
    "python",
    "react",
    "software",
    "svelte",
    "typescript",
    "wordpress",
}

CODING_SIGNAL_TERMS = {
    "api",
    "backend",
    "bug",
    "ci",
    "cli",
    "code",
    "coding",
    "compose",
    "debug",
    "developer",
    "django",
    "fastapi",
    "frontend",
    "full-stack",
    "github",
    "implementation",
    "integration",
    "javascript",
    "next.js",
    "node",
    "open source",
    "python",
    "react",
    "repo",
    "script",
    "svelte",
    "sveltekit",
    "testing",
    "typescript",
    "wordpress",
}

JOB_SEEKER_TERMS = {
    "looking for a job",
    "looking for back end developer roles",
    "looking for remote job",
    "looking for roles",
    "looking for work",
    "my resume",
    "seeking a job",
    "self taught",
    "what salary can i get",
}

SOURCE_PRIORITY = {
    "wild-toads-road": 2.0,
    "algora": 2.0,
    "github-issue-search": 1.35,
    "remotive": 0.35,
    "remoteok": 0.3,
    "arbeitnow": 0.25,
    "hackernews-algolia": -0.35,
}

PUBLIC_SOURCES = [
    "Wild Toads Road / gig_scout local receipts",
    "Remotive software-dev API",
    "Arbeitnow job-board API",
    "RemoteOK public API",
    "Hacker News Algolia public search",
    "GitHub issue search through gh api when authenticated",
    "Algora/GitHub bounty search through gh api when authenticated",
]

GITHUB_QUERIES = [
    "algora bounty python",
    "algora bounty typescript",
    "algora bounty javascript",
    "algora good first issue",
    "opire bounty python",
    "opire bounty typescript",
    "gitcoin bounty python",
    "gitcoin bounty javascript",
    "good first issue python bug",
    "good first issue typescript bug",
    "help wanted python bug",
    "help wanted javascript bug",
    "help wanted sveltekit",
    "bounty python",
    "bounty typescript",
]

HN_QUERIES = [
    "freelance python contract",
    "freelance javascript contract",
    "python developer contract remote",
    "react developer contract remote",
    "ai automation contract developer",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slug(text: str, limit: int = 90) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return (value[:limit] or "tris-gig").strip("-")


def stable_id(*parts: str) -> str:
    raw = "|".join(parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"tris-gig-{slug(parts[0], 54)}-{digest}"


def clean_text(value: Any) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()


def fetch_json(url: str, *, timeout: int = 18) -> Any | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "TrismegistusGigWorker/1.0 dean@renaissancefieldlite.com",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except Exception:
        return None


def extract_email(text: str) -> str:
    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text or "", re.I)
    return match.group(0) if match else ""


def parse_money(text: str) -> int | None:
    matches = re.findall(r"\$ ?([0-9][0-9,]*(?:\.[0-9]+)?)", text or "")
    if not matches:
        return None
    try:
        return max(int(float(match.replace(",", ""))) for match in matches)
    except ValueError:
        return None


def parse_dt(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        # RemoteOK and HN-style epochs are seconds.
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def source_priority(source: str) -> float:
    for key, value in SOURCE_PRIORITY.items():
        if key in source:
            return value
    return 0.0


def lead_text(lead: dict[str, Any]) -> str:
    return " ".join(
        [
            lead.get("title", ""),
            lead.get("company", ""),
            lead.get("body", ""),
            " ".join(lead.get("tags", [])),
            lead.get("source", ""),
        ]
    ).lower()


def is_recent(lead: dict[str, Any], *, days: int) -> bool:
    posted = parse_dt(lead.get("posted_at"))
    if posted is None:
        return True
    return posted >= datetime.now(timezone.utc) - timedelta(days=days)


def quality_gate(lead: dict[str, Any], *, min_budget_usd: int = DEFAULT_MIN_BUDGET_USD) -> dict[str, Any]:
    text = lead_text(lead)
    title = lead.get("title", "").lower()
    source = lead.get("source", "")
    reasons: list[str] = []
    reject = False
    strict = True

    if any(term in text for term in JOB_SEEKER_TERMS):
        reject = True
        reasons.append("reject:job_seeker_post")
    if title in {"view open positions", "developer job"}:
        reject = True
        reasons.append("reject:generic_listing")
    if title.startswith("[demand]"):
        reject = True
        reasons.append("reject:generic_demand_issue")
    if "github.com/" in (lead.get("apply_url") or lead.get("url") or "") and "/pull/" in (lead.get("apply_url") or lead.get("url") or ""):
        reject = True
        reasons.append("reject:github_pull_not_apply_route")
    if any(term in text for term in HARD_FILTER_TERMS):
        reject = True
        reasons.append("reject:non_low_hanging_or_role_mismatch")
    budget = lead.get("budget_usd")
    if isinstance(budget, (int, float)) and 0 < budget < min_budget_usd:
        reject = True
        reasons.append(f"reject:below_budget_floor:{min_budget_usd}")
    if source == "hackernews-algolia":
        if not is_recent(lead, days=45):
            reject = True
            reasons.append("reject:stale_hn_thread")
        if title.startswith(("ask hn:", "show hn:")) and not any(term in text for term in ["hiring", "contract", "freelance", "bounty"]):
            reject = True
            reasons.append("reject:hn_discussion_not_job")
        strict = False
        reasons.append("backup:hn_requires_manual_route_check")
    if not any(term in text for term in CODING_SIGNAL_TERMS):
        reject = True
        reasons.append("reject:no_coding_signal")
    if source in {"remotive", "remoteok", "arbeitnow"} and not any(term in title for term in TITLE_CODING_SIGNAL_TERMS):
        reject = True
        reasons.append("reject:job_board_title_non_coding")
    if any(term in title for term in ["senior ", "lead ", "principal", "staff "]):
        strict = False
        reasons.append("backup:senior_or_lead_scope")
    if lead.get("route_kind") in {"direct_email", "github_issue"}:
        reasons.append(f"route:{lead.get('route_kind')}")
    return {"accept": not reject, "strict": strict and not reject, "reasons": reasons}


def create_mailboxes() -> dict[str, Any]:
    if shutil.which("osascript") is None:
        return {"ok": False, "error": "osascript unavailable", "mailboxes": []}
    script = """
on run argv
  set madeList to {}
  tell application "Mail"
    repeat with mailboxName in argv
      set existingNames to name of every mailbox
      if existingNames contains (mailboxName as text) then
        set end of madeList to "exists:" & (mailboxName as text)
      else
        make new mailbox with properties {name:(mailboxName as text)}
        set end of madeList to "created:" & (mailboxName as text)
      end if
    end repeat
  end tell
  return madeList
end run
"""
    result = subprocess.run(
        ["osascript", "-e", script, *MAILBOX_NAMES],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "mailboxes": MAILBOX_NAMES,
    }


def normal_lead(
    *,
    source: str,
    title: str,
    company: str = "",
    url: str = "",
    apply_url: str = "",
    body: str = "",
    tags: list[str] | None = None,
    budget_usd: int | None = None,
    posted_at: Any = None,
    raw: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    title = clean_text(title)
    body = clean_text(body)
    company = clean_text(company)
    route = clean_text(apply_url or url)
    if not title or not route:
        return None
    haystack = f"{title} {company} {body} {route}"
    email = extract_email(haystack)
    route_kind = "direct_email" if email else "apply_url"
    if "github.com/" in route and "/issues/" in route:
        route_kind = "github_issue"
    parsed_posted_at = parse_dt(posted_at)
    return {
        "id": stable_id(title, route),
        "source": source,
        "title": title,
        "company": company,
        "url": url or apply_url,
        "apply_url": apply_url or url,
        "route_kind": route_kind,
        "direct_email": email,
        "body": body,
        "tags": tags or [],
        "budget_usd": budget_usd or parse_money(haystack),
        "posted_at": parsed_posted_at.isoformat().replace("+00:00", "Z") if parsed_posted_at else "",
        "raw": raw or {},
    }


def load_wild_toads(limit: int = 80) -> list[dict[str, Any]]:
    payload = collect_wild_toads(limit=limit)
    leads = []
    for item in payload.get("leads", []):
        lead = normal_lead(
            source=item.get("source") or "wild-toads-road",
            title=item.get("title") or "",
            url=item.get("url") or "",
            body=item.get("body") or "",
            tags=item.get("tags") or [],
            budget_usd=item.get("budget_usd"),
            posted_at=item.get("created_utc") or item.get("created_at") or item.get("ts"),
            raw=item,
        )
        if lead:
            lead["source_file"] = item.get("wild_toads", {}).get("source_file")
            leads.append(lead)
    return leads


def fetch_remotive(limit: int = 80) -> list[dict[str, Any]]:
    data = fetch_json("https://remotive.com/api/remote-jobs?category=software-dev")
    leads: list[dict[str, Any]] = []
    for item in (data or {}).get("jobs", [])[:limit]:
        lead = normal_lead(
            source="remotive",
            title=item.get("title") or "",
            company=item.get("company_name") or "",
            url=item.get("url") or "",
            apply_url=item.get("url") or "",
            body=item.get("description") or "",
            tags=item.get("tags") or [],
            posted_at=item.get("publication_date"),
            raw=item,
        )
        if lead:
            leads.append(lead)
    return leads


def fetch_arbeitnow(limit: int = 80) -> list[dict[str, Any]]:
    data = fetch_json("https://www.arbeitnow.com/api/job-board-api")
    leads: list[dict[str, Any]] = []
    for item in (data or {}).get("data", [])[:limit]:
        lead = normal_lead(
            source="arbeitnow",
            title=item.get("title") or "",
            company=item.get("company_name") or "",
            url=item.get("url") or "",
            apply_url=item.get("url") or "",
            body=item.get("description") or "",
            tags=item.get("tags") or [],
            posted_at=item.get("created_at") or item.get("date"),
            raw=item,
        )
        if lead:
            leads.append(lead)
    return leads


def fetch_remoteok(limit: int = 100) -> list[dict[str, Any]]:
    data = fetch_json("https://remoteok.com/api")
    leads: list[dict[str, Any]] = []
    for item in (data or [])[:limit]:
        if not isinstance(item, dict) or "position" not in item:
            continue
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        lead = normal_lead(
            source="remoteok",
            title=item.get("position") or "",
            company=item.get("company") or "",
            url=item.get("url") or "",
            apply_url=item.get("apply_url") or item.get("url") or "",
            body=item.get("description") or "",
            tags=[str(tag) for tag in tags],
            budget_usd=item.get("salary_max") or item.get("salary_min"),
            posted_at=item.get("date") or item.get("epoch"),
            raw=item,
        )
        if lead:
            leads.append(lead)
    return leads


def fetch_hn(limit_per_query: int = 12) -> list[dict[str, Any]]:
    leads: list[dict[str, Any]] = []
    for query in HN_QUERIES:
        encoded = urllib.parse.urlencode({"query": query, "tags": "story"})
        data = fetch_json(f"https://hn.algolia.com/api/v1/search_by_date?{encoded}")
        for item in (data or {}).get("hits", [])[:limit_per_query]:
            object_id = str(item.get("objectID") or "")
            url = item.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
            lead = normal_lead(
                source="hackernews-algolia",
                title=item.get("title") or item.get("story_title") or "",
                url=url,
                apply_url=url,
                body=item.get("story_text") or item.get("comment_text") or "",
                tags=["hn", query],
                posted_at=item.get("created_at") or item.get("created_at_i"),
                raw=item,
            )
            if lead:
                leads.append(lead)
    return leads


def fetch_github(limit_per_query: int = 12) -> list[dict[str, Any]]:
    if shutil.which("gh") is None:
        return []
    leads: list[dict[str, Any]] = []
    for query in GITHUB_QUERIES:
        source = "algora-github-search" if "algora" in query.lower() else "github-issue-search"
        result = subprocess.run(
            [
                "gh",
                "search",
                "issues",
                query,
                "--state",
                "open",
                "--limit",
                str(limit_per_query),
                "--json",
                "url,title,body,labels,repository,createdAt",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if result.returncode != 0:
            continue
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        for item in payload[:limit_per_query]:
            labels = [label.get("name", "") for label in item.get("labels", []) if isinstance(label, dict)]
            repository = item.get("repository") or {}
            lead = normal_lead(
                source=source,
                title=item.get("title") or "",
                company=repository.get("nameWithOwner") or repository.get("name") or "",
                url=item.get("url") or "",
                apply_url=item.get("url") or "",
                body=item.get("body") or "",
                tags=["github", *labels, query],
                posted_at=item.get("createdAt"),
                raw=item,
            )
            if lead:
                leads.append(lead)
    return leads


def score_lead(lead: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    text = lead_text(lead)
    score = 2.5
    reasons: list[str] = []
    priority_bump = source_priority(lead.get("source", ""))
    if priority_bump:
        score += priority_bump
        reasons.append(f"source_priority:{lead.get('source')}")
    for term in LOW_HANGING_TERMS:
        if term in text:
            score += 0.45
            reasons.append(f"matches:{term}")
    for term in HARD_FILTER_TERMS:
        if term in text:
            score -= 1.2
            reasons.append(f"risk:{term}")
    if lead.get("route_kind") == "direct_email":
        score += 1.5
        reasons.append("direct_email_route")
    elif lead.get("route_kind") == "github_issue":
        score += 0.9
        reasons.append("github_issue_route")
    else:
        score += 0.25
        reasons.append("apply_url_route")
    budget = lead.get("budget_usd")
    if isinstance(budget, (int, float)) and budget:
        if budget >= 100:
            score += 0.7
            reasons.append("budget_visible")
        elif budget < 25:
            score -= 0.6
            reasons.append("low_budget")
    if any(word in text for word in ["full-time", "full time", "permanent"]):
        score -= 0.55
        reasons.append("less_gig_like")
    if any(word in text for word in ["contract", "freelance", "task", "bounty", "part-time", "part time"]):
        score += 0.7
        reasons.append("gig_like")
    if is_recent(lead, days=21):
        score += 0.35
        reasons.append("recent")
    elif not is_recent(lead, days=90):
        score -= 0.5
        reasons.append("older_source")
    return round(max(score, 0.1), 3), {"reasons": reasons[:12]}


def classify_offer(lead: dict[str, Any], score: float) -> dict[str, Any]:
    text = f"{lead.get('title','')} {lead.get('body','')} {' '.join(lead.get('tags', []))}".lower()
    budget = lead.get("budget_usd")
    if isinstance(budget, (int, float)) and 0 < budget <= 75:
        lane = "bounty / fast proof patch"
        bid = f"${int(budget)} listed bounty"
    elif "bounty" in text or "algora" in text:
        lane = "bounty / confirm payout route"
        bid = "confirm listed bounty before work"
    elif "wordpress" in text or "website" in text or "landing" in text:
        lane = "fast website / integration repair"
        bid = "$150-$450 fixed scope"
    elif "data" in text or "dashboard" in text or "scrap" in text:
        lane = "data automation / dashboard"
        bid = "$250-$900 fixed scope"
    elif "bug" in text or "fix" in text or "issue" in text:
        lane = "bug fix / repo patch"
        bid = "$100-$500 fixed scope"
    elif "ai" in text or "llm" in text or "automation" in text:
        lane = "AI automation / workflow integration"
        bid = "$300-$1,200 fixed scope"
    else:
        lane = "coding support / implementation sprint"
        bid = "$200-$800 fixed scope"
    if score >= 6.8:
        priority = "A"
    elif score >= 5.2:
        priority = "B"
    else:
        priority = "C"
    return {"offer_lane": lane, "bid_hint": bid, "priority": priority}


def proposal_text(lead: dict[str, Any], offer: dict[str, Any]) -> str:
    company = lead.get("company") or "team"
    route_line = lead.get("apply_url") or lead.get("url")
    return f"""Hi {company},

I saw your post for: {lead.get("title")}.

I can help with this as a focused {offer["offer_lane"]} engagement. My approach would be:

1. confirm the exact target files, repo, or workflow
2. reproduce the issue or inspect the current implementation
3. ship a small reviewed patch or working deliverable
4. leave a short receipt: what changed, how it was tested, and any next gate

Suggested first scope: {offer["bid_hint"]}, depending on the exact repo/access and delivery format.

Relevant fit:
- Python / JavaScript / TypeScript implementation work
- AI-assisted debugging and repo triage
- source-backed documentation, tests, and delivery receipts
- fast turnaround on bounded tasks

If this is still open, send the repo/access details and preferred delivery format and I can scope the first pass cleanly.

Dean Patterson
Renaissance Field Lite
https://renaissancefieldlite.com/
"""


def write_eml(path: Path, to_addr: str, subject: str, body: str) -> None:
    msg = email.message.EmailMessage()
    msg["To"] = to_addr
    msg["From"] = "Dean Patterson <dean@renaissancefieldlite.com>"
    msg["Subject"] = subject
    msg.set_content(body)
    path.write_text(msg.as_string(), encoding="utf-8")


def gh_comment(issue_url: str, body_path: Path, *, live: bool) -> dict[str, Any]:
    if not live:
        return {"ok": False, "status": "not_requested"}
    if shutil.which("gh") is None:
        return {"ok": False, "status": "blocked", "error": "gh unavailable"}
    match = re.search(r"github\.com/([^/]+/[^/]+)/issues/([0-9]+)", issue_url)
    if not match:
        return {"ok": False, "status": "blocked", "error": "not a GitHub issue URL"}
    repo, number = match.groups()
    result = subprocess.run(
        ["gh", "issue", "comment", number, "--repo", repo, "--body-file", str(body_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
    )
    return {
        "ok": result.returncode == 0,
        "status": "comment_sent" if result.returncode == 0 else "failed",
        "repo": repo,
        "issue": number,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def save_sql(lead: dict[str, Any], score: float, status: str, payload: dict[str, Any]) -> None:
    db.save_lead({**lead, **payload}, score, status)
    source_entity_id = f"tris_daily_gig_source:{lead['id']}"
    db.save_source_document(
        source_entity_id,
        "tris_daily_gig_worker",
        lead.get("title", ""),
        payload.get("proposal_path", ""),
        lead.get("url", ""),
        status,
        "Paid-work lead. Application is only claimed when an actual send/comment/submission receipt exists.",
        payload,
    )
    db.save_evidence_node(
        f"tris_daily_gig_evidence:{lead['id']}",
        "relationship_paid_work_field_ops",
        source_entity_id,
        status,
        f"Tris found and scored paid-work lead: {lead.get('title')}",
        f"Source={lead.get('source')}; route={lead.get('route_kind')}; score={score}; proposal={payload.get('proposal_path')}",
        "Do not claim money, acceptance, or application submission unless live route receipt exists.",
        payload.get("next_gate", "Verify route and apply through saved receipt path."),
        payload,
    )


def collect_all_sources() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_status: dict[str, Any] = {}
    groups = [
        ("wild_toads", lambda: load_wild_toads()),
        ("remotive", fetch_remotive),
        ("arbeitnow", fetch_arbeitnow),
        ("remoteok", fetch_remoteok),
        ("hackernews", fetch_hn),
        ("github", fetch_github),
    ]
    leads: list[dict[str, Any]] = []
    for name, fn in groups:
        try:
            items = fn()
            source_status[name] = {"ok": True, "count": len(items)}
            leads.extend(items)
        except Exception as exc:  # noqa: BLE001 - receipt needs source blocker
            source_status[name] = {"ok": False, "error": str(exc)}
    return leads, source_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Tris daily paid-work/gig worker")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--min-limit", type=int, default=25)
    parser.add_argument("--min-budget", type=int, default=DEFAULT_MIN_BUDGET_USD)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--create-mailbox", action="store_true")
    parser.add_argument("--live-github-comment", action="store_true")
    parser.add_argument("--approval-phrase", default="")
    args = parser.parse_args()

    db.init_db()
    run_id = stamp()
    run_dir = OUT_DIR / f"tris_gigs_daily_{run_id}"
    proposal_dir = run_dir / "proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)

    mailbox_status = create_mailboxes() if args.create_mailbox else {"ok": None, "mailboxes": MAILBOX_NAMES}
    raw_leads, source_status = collect_all_sources()

    deduped: dict[str, dict[str, Any]] = {}
    for lead in raw_leads:
        key = (lead.get("apply_url") or lead.get("url") or lead["id"]).strip().lower()
        if key and key not in deduped:
            deduped[key] = lead

    scored: list[dict[str, Any]] = []
    rejected_count = 0
    for lead in deduped.values():
        gate = quality_gate(lead, min_budget_usd=args.min_budget)
        if not gate["accept"]:
            rejected_count += 1
            continue
        score, details = score_lead(lead)
        offer = classify_offer(lead, score)
        if score < args.min_score:
            rejected_count += 1
            continue
        if gate["strict"] and score < MIN_STRICT_SCORE:
            gate = {
                **gate,
                "strict": False,
                "reasons": [*gate["reasons"], f"backup:below_strict_score_floor:{MIN_STRICT_SCORE}"],
            }
        scored.append({**lead, "score": score, "score_details": details, "offer": offer, "quality_gate": gate})
    scored.sort(
        key=lambda item: (
            1 if item["quality_gate"]["strict"] else 0,
            item["score"],
            item.get("budget_usd") or 0,
        ),
        reverse=True,
    )
    strict_scored = [item for item in scored if item["quality_gate"]["strict"]]
    backup_scored = [item for item in scored if not item["quality_gate"]["strict"]]
    target_count = max(args.min_limit, min(args.limit, 40))
    selected = strict_scored[:target_count]
    if len(selected) < args.min_limit:
        selected.extend(backup_scored[: args.min_limit - len(selected)])

    live_comment_allowed = (
        args.live_github_comment
        and os.environ.get("TRIS_GIG_ALLOW_GITHUB_COMMENT", "0") == "1"
        and args.approval_phrase.strip() == "APPROVE TRIS GIG LIVE APPLY"
    )

    rows: list[dict[str, Any]] = []
    for idx, lead in enumerate(selected, 1):
        offer = lead["offer"]
        proposal = proposal_text(lead, offer)
        lead_slug = slug(f"{idx:02d}-{lead['title']}")
        proposal_path = proposal_dir / f"{lead_slug}_proposal.md"
        body_path = proposal_dir / f"{lead_slug}_apply_body.txt"
        body_path.write_text(proposal, encoding="utf-8")
        proposal_path.write_text(
            "\n".join(
                [
                    f"# Tris Gig Proposal {idx:02d}",
                    "",
                    f"- Lead ID: `{lead['id']}`",
                    f"- Source: {lead['source']}",
                    f"- Title: {lead['title']}",
                    f"- Company: {lead.get('company') or ''}",
                    f"- Route kind: {lead['route_kind']}",
                    f"- Apply URL: {lead.get('apply_url') or lead.get('url')}",
                    f"- Direct email: {lead.get('direct_email') or ''}",
                    f"- Score: {lead['score']}",
                    f"- Priority: {offer['priority']}",
                    f"- Quality tier: {'strict' if lead['quality_gate']['strict'] else 'backup_review'}",
                    f"- Offer lane: {offer['offer_lane']}",
                    f"- Bid hint: {offer['bid_hint']}",
                    "",
                    "## Score Reasons",
                    "",
                    "\n".join(f"- {reason}" for reason in lead["score_details"]["reasons"]),
                    "",
                    "## Quality Gate",
                    "",
                    "\n".join(f"- {reason}" for reason in lead["quality_gate"]["reasons"]),
                    "",
                    "## Proposal",
                    "",
                    "```text",
                    proposal.strip(),
                    "```",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        action_status = "proposal_ready"
        action_receipt: dict[str, Any] = {"status": "proposal_ready"}
        if not lead["quality_gate"]["strict"]:
            action_status = "backup_review_needed"
            action_receipt = {
                "status": action_status,
                "reason": "Lead passed coding filter but needs manual review before outreach.",
            }
        elif lead["route_kind"] == "direct_email":
            eml_path = proposal_dir / f"{lead_slug}.eml"
            write_eml(
                eml_path,
                lead["direct_email"],
                f"Proposal: {lead['title'][:90]}",
                proposal,
            )
            action_status = "email_ready_not_sent"
            action_receipt = {"status": action_status, "eml_path": str(eml_path)}
        elif lead["route_kind"] == "github_issue":
            action_receipt = gh_comment(lead["apply_url"], body_path, live=live_comment_allowed)
            action_status = "github_comment_sent" if action_receipt.get("ok") else "github_comment_ready_not_sent"
        else:
            action_status = "needs_apply_route"
            action_receipt = {"status": action_status, "apply_url": lead.get("apply_url") or lead.get("url")}

        saved = {
            "rank": idx,
            "proposal_path": str(proposal_path),
            "body_path": str(body_path),
            "action_status": action_status,
            "action_receipt": action_receipt,
            "next_gate": (
                "Apply through the listed URL or approve live route execution."
                if action_status != "github_comment_sent"
                else "Watch for maintainer response and be ready to deliver the patch."
            ),
        }
        save_sql(lead, lead["score"], action_status, saved)
        rows.append({**lead, **saved})

    applied_count = sum(1 for row in rows if row["action_status"] in {"github_comment_sent", "email_sent", "portal_submitted"})
    ready_count = sum(1 for row in rows if row["action_status"] in {"email_ready_not_sent", "github_comment_ready_not_sent", "proposal_ready"})
    needs_route_count = sum(1 for row in rows if row["action_status"] == "needs_apply_route")
    backup_selected_count = sum(1 for row in rows if row["action_status"] == "backup_review_needed")

    receipt = {
        "ok": True,
        "id": run_id,
        "ts": utc_now(),
        "action": "tris_daily_gig_worker",
        "requested_daily_range": "25-40",
        "min_budget_usd": args.min_budget,
        "min_score": args.min_score,
        "selected_count": len(rows),
        "applied_count": applied_count,
        "ready_count": ready_count,
        "needs_route_count": needs_route_count,
        "backup_selected_count": backup_selected_count,
        "strict_count": len(strict_scored),
        "backup_count": len(backup_scored),
        "rejected_count": rejected_count,
        "source_status": source_status,
        "payout_tracking": {
            "provider": "Algora",
            "transactions_url": ALGORA_TRANSACTIONS_URL,
            "status": "configured_for_receipt_tracking",
            "boundary": "Use for accepted bounty/payment receipts. Do not claim paid until a transaction receipt exists.",
        },
        "bounty_platform_registry": BOUNTY_PLATFORM_REGISTRY,
        "mailbox_status": mailbox_status,
        "live_comment_allowed": live_comment_allowed,
        "sources": PUBLIC_SOURCES,
        "run_dir": str(run_dir),
        "proposal_dir": str(proposal_dir),
        "boundary": "Real leads and real proposals. Applied is only counted when a live email/comment/form receipt exists.",
        "rows": rows,
    }

    json_path = run_dir / "TRIS_GIG_DAILY_RECEIPT.json"
    md_path = run_dir / "TRIS_GIG_DAILY_READOUT.md"
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Tris Daily Gig Worker",
        "",
        f"- Generated: {receipt['ts']}",
        f"- Selected leads: {len(rows)}",
        f"- Minimum visible budget: ${args.min_budget}",
        f"- Minimum score: {args.min_score}",
        f"- Strict coding leads available: {len(strict_scored)}",
        f"- Backup review leads available: {len(backup_scored)}",
        f"- Rejected as stale/non-coding/job-seeker: {rejected_count}",
        f"- Applied with live receipt: {applied_count}",
        f"- Proposal/apply-ready: {ready_count}",
        f"- Needs route: {needs_route_count}",
        f"- Backup selected for manual review: {backup_selected_count}",
        f"- Mailbox: {', '.join(MAILBOX_NAMES)}",
        "",
        "## Boundary",
        "",
        receipt["boundary"],
        "",
        "## Payout Tracking",
        "",
        f"- Provider: Algora",
        f"- Transactions: {ALGORA_TRANSACTIONS_URL}",
        "- Boundary: use for accepted bounty/payment receipts only; do not claim paid until a transaction receipt exists.",
        "",
        "## Bounty Platform Registry",
        "",
        "| Platform | Best for | Tris route | Payment boundary |",
        "| --- | --- | --- | --- |",
        *[
            f"| {item['platform']} | {item['best_for']} | {item['tris_route']} | {item['payment']} |"
            for item in BOUNTY_PLATFORM_REGISTRY
        ],
        "",
        "## Sources",
        "",
        *[f"- {source}" for source in PUBLIC_SOURCES],
        "",
        "## Leads",
        "",
        "| Rank | Score | Tier | Status | Source | Title | Route | Proposal |",
        "| ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {rank} | {score} | {tier} | {status} | {source} | {title} | {route} | `{proposal}` |".format(
                rank=row["rank"],
                score=row["score"],
                tier="strict" if row["quality_gate"]["strict"] else "backup",
                status=row["action_status"],
                source=row["source"],
                title=row["title"].replace("|", "/")[:90],
                route=(row.get("apply_url") or row.get("url") or "").replace("|", "%7C")[:90],
                proposal=Path(row["proposal_path"]).name,
            )
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    db.save_memory_item(
        "tris_daily_gig_worker",
        f"tris_daily_gig_worker:{run_id}",
        "Tris daily gig worker receipt",
        md_path.read_text(encoding="utf-8"),
        receipt,
    )
    db.log_event("tris_daily_gig_worker", receipt)

    progress_entry = (
        "\n"
        f"{receipt['ts']} - Tris daily gig worker:\n\n"
        f"- Selected {len(rows)} real paid-work/coding leads from Wild Toad + public job APIs.\n"
        f"- Minimum visible budget gate: ${args.min_budget}.\n"
        f"- Minimum score gate: {args.min_score}.\n"
        f"- Strict coding leads available: {len(strict_scored)}; backup review leads available: {len(backup_scored)}; rejected: {rejected_count}.\n"
        f"- Applied with live receipt: {applied_count}.\n"
        f"- Proposal/apply-ready: {ready_count}.\n"
        f"- Needs route: {needs_route_count}.\n"
        f"- Backup selected for manual review: {backup_selected_count}.\n"
        f"- Algora payout tracking: `{ALGORA_TRANSACTIONS_URL}`.\n"
        f"- Bounty platform registry: Algora, Opire, Replit Bounties, Gitcoin.\n"
        f"- Mail folder: `Tris Gigs` with subfolders Ready To Apply, Sent Applications, Needs Route, Receipts.\n"
        f"- Readout: `{md_path}`\n"
        f"- Receipt: `{json_path}`\n"
        "- Boundary: no application is counted unless a live send/comment/submission receipt exists.\n"
    )
    PROGRESS_LOG.open("a", encoding="utf-8").write(progress_entry)
    RICK_LOG.open("a", encoding="utf-8").write(progress_entry)
    print(json.dumps({"ok": True, "receipt": str(json_path), "readout": str(md_path), "selected": len(rows), "strict_available": len(strict_scored), "backup_available": len(backup_scored), "rejected": rejected_count, "applied": applied_count, "ready": ready_count, "needs_route": needs_route_count, "backup_selected": backup_selected_count}, indent=2))


if __name__ == "__main__":
    main()
