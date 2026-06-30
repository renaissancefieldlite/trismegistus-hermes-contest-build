from __future__ import annotations

import os
from typing import Any

from .golden_mark_foundation import stable_state_system_prompt
from .integrations import model_runtime


def _fallback_deliverable(scored_lead: dict[str, Any], consent: dict[str, Any]) -> str:
    lead = scored_lead["lead"]
    return "\n".join(
        [
            f"Scoped work packet for: {lead.get('title', '')}",
            "",
            "What Trismegistus can do now:",
            "- Confirm the client owns the task and can share relevant files.",
            "- Produce a first-pass fix plan with exact files, tests, and risk notes.",
            "- Draft a short delivery note that explains the change in plain English.",
            "",
            "Golden Mark stable-state operating rule:",
            "Keep the problem, data, instructions, context, and goal lined up before writing code.",
            "",
            f"Quadro decision: {consent.get('final_decision')}",
        ]
    )


def create_deliverable(scored_lead: dict[str, Any], consent: dict[str, Any]) -> dict[str, Any]:
    lead = scored_lead["lead"]
    messages = [
        {"role": "system", "content": stable_state_system_prompt()},
        {
            "role": "user",
            "content": (
                "Create a concise service-agent work packet for this lead. "
                "Include scope, first action, consent boundary, likely deliverable, and payment path. "
                "Do not claim the work is complete.\n\n"
                f"Lead: {lead}\n\nScore: {scored_lead}\n\nConsent chain: {consent}"
            ),
        },
    ]
    live = model_runtime.generate(messages)
    if live.get("ok"):
        return live
    if os.environ.get("TRISMEGISTUS_ALLOW_LOCAL_FALLBACK") == "1":
        return {
            "ok": True,
            "source": "local_golden_mark_fallback",
            "hermes_error": live.get("error"),
            "text": _fallback_deliverable(scored_lead, consent),
        }
    return {
        "ok": False,
        "source": "model_runtime_required",
        "error": (
            "No model answered. Start NemoHermes/OpenClaw/NemoClaw, "
            "then run this packet again."
        ),
        "runtime_error": live.get("error"),
    }
