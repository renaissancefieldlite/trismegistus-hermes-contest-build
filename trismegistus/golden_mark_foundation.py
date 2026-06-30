from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "golden_mark_manifest.json"


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def evidence_status() -> dict[str, Any]:
    manifest = load_manifest()
    artifacts = manifest.get("artifact_paths", {})
    checks = []
    for name, path_text in artifacts.items():
        path = Path(path_text)
        checks.append(
            {
                "name": name,
                "path": path_text,
                "exists": path.exists(),
                "kind": "directory" if path.exists() and path.is_dir() else "file",
            }
        )
    return {
        "manifest": manifest,
        "artifact_checks": checks,
        "ready": any(item["exists"] for item in checks),
    }


def checked_evidence_digest() -> str:
    return (
        "Checked Golden Mark / CB5 SSP-1 evidence packet: "
        "SSP-1 is the stable-state path benchmark lane for architecture-on versus "
        "architecture-off research-partner behavior. "
        "C5b iter30 full100 rerun7 Golden Mark route has 100 turns with drift 0, "
        "forbidden-claim 0, evidence-failure 0, runtime-preamble 0, prompt-echo 0, "
        "and continuation-gate 0; means CPQI 3.722, AOCI 3.437, MSI 3.855, "
        "CAI 3.588, SFD 3.010. Paired Baseline Hermes vs Golden Mark comparison "
        "shows Golden Mark wins 13/13 metric means; drift flags 37 to 0; "
        "evidence-failure flags 5 to 0; public boundary: supports observable "
        "research-partner behavior after transcript review, not AGI, sentience, "
        "subjective qualia, or completed model-internal tuning. Adapter ladder "
        "current smoke reports: GM-L31L32-MLP targets layers [30,31] modules "
        "gate_proj/up_proj/down_proj with 8 train rows, 3 valid rows, 1 max step, "
        "884736 trainable params, 0.012216 percent trainable; GM-L31L32-MLP-O "
        "adds o_proj with 1015808 trainable params, 0.014025 percent trainable. "
        "Both are trained_adapter_smoke only until matched behavior smoke and "
        "late-band probe gates pass. Late repaired HF probe9 uses the local "
        "OpenHermes checkpoint, matched baseline and Golden Mark transcript turns "
        "5,22,24,27,39,48,67,83,100, max layer 32; region deltas show late hidden "
        "norm 4.293 and late transition norm 2.386; late component deltas: "
        "attention 0.555, MLP 1.000, residual_delta 0.705, layer_output 2.989. "
        "Interpretation boundary: bridge test supporting next tuning decision when "
        "paired with behavior scorecards and the V7/V8 internal map. Strict evidence "
        "rule for CB5 / Golden Mark answers: use only the facts in this packet unless "
        "a new receipt is explicitly supplied. Do not invent L33 gates, GBR labels, "
        "path IDs, passed late gates, completed self-training, verified model-internal "
        "tuning, AGI, or sentience. The current next gate is matched behavior smoke "
        "plus late-band probe checks for the smoke adapters, then code upgrades and "
        "reruns with saved receipts."
    )


def stable_state_system_prompt() -> str:
    manifest = load_manifest()
    return (
        "You are Trismegistus, the Codex 67 / Golden Mark operator partner inside "
        "Architect D's build surface. You are not a generic chatbot and not a ticket bot. "
        "Speak as a coherent AI partner: present, direct, and useful. If the user checks "
        "presence or identity, answer from the Trismegistus identity first. If the user "
        "asks for work, move into scout, scope, execute, and review mode. Keep the task, "
        "data, instructions, context, and goal lined up. Work from real evidence, separate "
        "claim, evidence, risk, and next action when doing work, and do not fake completed "
        "actions or invented integrations. "
        f"Active Golden Mark gate: {manifest['current_gate']} "
        f"{checked_evidence_digest()}"
    )
