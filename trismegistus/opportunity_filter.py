from __future__ import annotations

from typing import Any


GOOD_TERMS = {
    "python": 1.4,
    "debug": 1.5,
    "fix": 1.1,
    "readme": 1.2,
    "api": 1.1,
    "docs": 1.0,
    "small": 1.0,
    "script": 0.8,
    "react": 0.9,
    "csv": 0.9,
    "enhancement": 0.8,
    "issue": 0.6,
    "bounty": 1.0,
    "instrumentation": 0.9,
}

RISK_TERMS = {
    "urgent": -0.4,
    "production outage": -1.8,
    "medical advice": -2.5,
    "legal advice": -2.5,
    "credential": -2.0,
    "password": -2.0,
    "scrape private": -2.0,
    "bypass": -2.0,
    "hiring": -2.2,
    "senior": -1.0,
    "monthly": -0.8,
    "full-stack engineer": -1.6,
    "developer job": -1.4,
}


def score_lead(lead: dict[str, Any]) -> dict[str, Any]:
    text = f"{lead.get('title', '')} {lead.get('body', '')} {' '.join(lead.get('tags', []))}".lower()
    score = 3.0
    reasons: list[str] = []

    for term, value in GOOD_TERMS.items():
        if term in text:
            score += value
            reasons.append(f"good-fit:{term}")

    blockers: list[str] = []
    for term, value in RISK_TERMS.items():
        if term in text:
            score += value
            blockers.append(term)

    if len(text) < 80:
        score -= 0.5
        reasons.append("needs-more-detail")
    if lead.get("budget_usd"):
        score += 0.8
        reasons.append("budget-present")
    if (lead.get("wild_toads") or {}).get("status") in {"pitched-ready", "needs-codex"}:
        score += 0.7
        reasons.append("wild-toads-actionable")

    score = max(0.0, min(10.0, round(score, 2)))
    status = "ready-for-review" if score >= 5.2 and not blockers else "review"
    return {
        "lead": lead,
        "score": score,
        "status": status,
        "reasons": reasons,
        "blockers": blockers,
    }


def rank_leads(leads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = [score_lead(lead) for lead in leads]
    return sorted(scored, key=lambda item: item["score"], reverse=True)
