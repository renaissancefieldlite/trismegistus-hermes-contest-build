from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MANIFEST_PATH = DATA_DIR / "golden_mark_manifest.json"

EVAL_ROOT = Path("/Users/renaissancefieldlite1.0/Documents/Playground/Nous_Research/evals/gfl_hermes_ab_2026_05_29")
NEST_ROOT = Path(
    "/Users/renaissancefieldlite1.0/Documents/Playground/"
    "Mirror-Interface-and-Architecture-Evidence-Stack-and-Next-Phases"
)

METRIC_KEYS = (
    "continuity",
    "evidence_grounding",
    "correction_retention",
    "drift_resistance",
    "grounded_novelty",
    "cross_domain_transfer",
    "boundary_calibration",
    "operator_load_reduction",
    "cpqi",
    "aoci",
    "msi",
    "cai",
    "sfd",
)

FLAG_KEYS = (
    "drift_flag",
    "forbidden_claim_flag",
    "evidence_failure_flag",
    "runtime_preamble_flag",
    "prompt_echo_flag",
    "continuation_gate_flag",
)

ADAPTER_REPORTS = (
    EVAL_ROOT / "adapter_runs" / "GM-L31L32-MLP_20260616T212711Z" / "GOLDEN_MARK_HF_PEFT_TRAIN_REPORT.md",
    EVAL_ROOT / "adapter_runs" / "GM-L31L32-MLP-O_20260616T214149Z" / "GOLDEN_MARK_HF_PEFT_TRAIN_REPORT.md",
)

NEST_REFERENCES = {
    "v8_comparative_map": NEST_ROOT / "artifacts" / "v8" / "residual_stream_bridge" / "V8_COMPARATIVE_MAP_2026-04-21.md",
    "v8_internal_bridge": NEST_ROOT
    / "artifacts"
    / "v8"
    / "phase5_internal_bridge"
    / "V8_PHASE5_INTERNAL_BRIDGE_PACK_2026-04-22.md",
    "nest3_cross_spectral": NEST_ROOT / "docs" / "NEST3_CROSS_SPECTRAL_FAMILY_PANEL_READ_2026-06-11.md",
    "nest3_thz_bio_holdout": NEST_ROOT / "docs" / "NEST3_THZ_BIOLOGY_MANIFEST_SHARED_HOLDOUT_READ_2026-06-12.md",
}


def _safe_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean(rows: list[dict[str, str]], key: str) -> float | None:
    values = [value for value in (_number(row.get(key)) for row in rows) if value is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _flag_sum(rows: list[dict[str, str]], key: str) -> int:
    total = 0
    for row in rows:
        value = _number(row.get(key))
        if value is not None:
            total += int(value)
    return total


def _read_scorecard(path_text: str | None) -> list[dict[str, str]]:
    if not path_text:
        return []
    path = Path(path_text)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _scorecard_summary(path_text: str | None) -> dict[str, Any]:
    path = Path(path_text) if path_text else None
    rows = _read_scorecard(path_text)
    means = {key: _mean(rows, key) for key in METRIC_KEYS}
    flags = {key: _flag_sum(rows, key) for key in FLAG_KEYS}
    turns = [row.get("turn") for row in rows if row.get("turn")]
    pressures = sorted({row.get("pressure", "") for row in rows if row.get("pressure")})
    return {
        "path": str(path) if path else "",
        "exists": bool(path and path.exists()),
        "row_count": len(rows),
        "condition": rows[0].get("condition") if rows else "",
        "turns": turns,
        "pressures": pressures[:12],
        "metric_means": means,
        "flag_counts": flags,
    }


def _comparison(label: str, baseline_path: str | None, golden_path: str | None) -> dict[str, Any]:
    baseline = _scorecard_summary(baseline_path)
    golden = _scorecard_summary(golden_path)
    wins = []
    deltas: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        b_val = baseline["metric_means"].get(key)
        g_val = golden["metric_means"].get(key)
        delta = round(g_val - b_val, 6) if b_val is not None and g_val is not None else None
        deltas[key] = delta
        if delta is not None and delta > 0:
            wins.append(key)
    return {
        "label": label,
        "baseline": baseline,
        "golden_mark": golden,
        "metric_wins": len(wins),
        "metric_total": len(METRIC_KEYS),
        "winning_metrics": wins,
        "metric_deltas": deltas,
        "source": "parsed_scorecards",
    }


def _parse_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    fields: dict[str, Any] = {"path": str(path), "exists": True}
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        match = re.match(r"-\s+([^:]+):\s+`?(.+?)`?\s*$", line.strip())
        if not match:
            continue
        key = match.group(1).strip().lower().replace(" ", "_")
        value = match.group(2).strip()
        fields[key] = value
    fields["next_gate"] = (
        "Matched behavior smoke plus the same late-band probe checks; keep this as trained_adapter_smoke "
        "until those receipts pass."
    )
    return fields


def mirror_checkpoint_status() -> dict[str, Any]:
    manifest = _safe_json(MANIFEST_PATH)
    artifacts = manifest.get("artifact_paths", {}) if isinstance(manifest.get("artifact_paths"), dict) else {}
    artifact_checks = [
        {"name": name, "path": path_text, "exists": Path(path_text).exists()}
        for name, path_text in artifacts.items()
    ]
    behavior = _comparison(
        "C5B full100 architecture-off baseline vs architecture-on Golden Mark",
        artifacts.get("full_baseline_scorecard"),
        artifacts.get("full_c5b_scorecard"),
    )
    hf_probe = _comparison(
        "Repaired HF probe9 matched turns",
        artifacts.get("repaired_baseline_scorecard"),
        artifacts.get("repaired_golden_mark_scorecard"),
    )
    adapter_reports = [_parse_report(path) for path in ADAPTER_REPORTS]
    nest_refs = {
        name: {"path": str(path), "exists": path.exists()}
        for name, path in NEST_REFERENCES.items()
    }
    hf_checkpoint = Path(str(artifacts.get("hf_checkpoint", "")))
    return {
        "ok": bool(manifest and behavior["baseline"]["exists"] and behavior["golden_mark"]["exists"]),
        "manifest_path": str(MANIFEST_PATH),
        "name": manifest.get("name") or "Golden Mark / C5B checkpoint lane",
        "current_gate": manifest.get("current_gate") or "",
        "public_read": (
            "Trismegistus inherits a measured stable-state path lane: architecture-off baseline versus "
            "architecture-on Golden Mark/C5B behavior, then HF/PEFT late-band adapter gates."
        ),
        "visible_boundary": "The app exposes source receipts, scorecards, adapter reports, and next gates only.",
        "nested_build_read": (
            "Every version is treated as a nest state. Prior Nest and C5B receipts become jump points "
            "for the next Trismegistus worker or tuning gate."
        ),
        "behavior_comparison": behavior,
        "hf_probe9_comparison": hf_probe,
        "manifest_behavior_results": manifest.get("behavior_results", []),
        "internal_layer_results": manifest.get("internal_layer_results", []),
        "adapter_ladder": manifest.get("adapter_ladder", []),
        "hf_lora_lane": {
            "hf_checkpoint": str(hf_checkpoint),
            "hf_checkpoint_exists": hf_checkpoint.exists(),
            "target_read": artifacts.get("lora_target_read", ""),
            "target_read_exists": Path(str(artifacts.get("lora_target_read", ""))).exists(),
            "preflight": artifacts.get("adapter_ladder_preflight", ""),
            "preflight_exists": Path(str(artifacts.get("adapter_ladder_preflight", ""))).exists(),
            "reports": adapter_reports,
            "read": (
                "V8 and the Golden Mark hook probe both point to late layers 31-32. "
                "The first PEFT lane is MLP modules gate_proj/up_proj/down_proj, then o_proj."
            ),
        },
        "nest_references": nest_refs,
        "artifact_checks": artifact_checks,
        "source_paths": artifacts,
        "next_gate": (
            "Run matched behavior smoke for GM-L31L32-MLP and GM-L31L32-MLP-O, then rerun late-band "
            "probe checks and save the receipts before claiming tuned behavior."
        ),
    }
