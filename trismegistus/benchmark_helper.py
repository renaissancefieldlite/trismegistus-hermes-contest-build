from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from . import db


ROOT = Path(__file__).resolve().parents[1]
SWE_DIR = ROOT / "data" / "swebench"
CODING_MISSION_DIR = SWE_DIR / "codex_helper_missions"


def _latest(pattern: str, directory: Path = ROOT) -> Path | None:
    matches = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _latest_runnable_helper_prediction() -> Path | None:
    matches = sorted(
        SWE_DIR.glob("swebench_codex_helper_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in matches:
        payload = _load_json(path)
        if not payload:
            continue
        items = payload.get("items") or []
        if int(payload.get("submitted_count") or 0) > 0 and any(
            item.get("patch_nonempty") for item in items
        ):
            return path
    return matches[0] if matches else None


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {
            "submitted": 0,
            "completed": 0,
            "resolved": 0,
            "empty_patch": 0,
            "errors": 0,
        }
    return {
        "submitted": int(report.get("submitted_instances") or 0),
        "completed": int(report.get("completed_instances") or 0),
        "resolved": int(report.get("resolved_instances") or 0),
        "empty_patch": int(report.get("empty_patch_instances") or 0),
        "errors": int(report.get("error_instances") or 0),
    }


def _prediction_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "id": "",
            "baseline_nonempty": 0,
            "baseline_count": 0,
            "tris_nonempty": 0,
            "tris_count": 0,
        }
    baseline = payload.get("baseline") or []
    tris = payload.get("architecture_on") or []
    return {
        "id": str(payload.get("id") or ""),
        "baseline_nonempty": sum(1 for item in baseline if item.get("patch_nonempty")),
        "baseline_count": len(baseline),
        "tris_nonempty": sum(1 for item in tris if item.get("patch_nonempty")),
        "tris_count": len(tris),
    }


def _helper_prediction_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "id": "",
            "offset": 0,
            "count": 0,
            "submitted_count": 0,
            "nonempty": 0,
            "only_nonempty": False,
        }
    items = payload.get("items") or []
    return {
        "id": str(payload.get("id") or ""),
        "offset": int(payload.get("offset") or 0),
        "count": int(payload.get("count") or len(items)),
        "submitted_count": int(payload.get("submitted_count") or 0),
        "nonempty": sum(1 for item in items if item.get("patch_nonempty")),
        "only_nonempty": bool(payload.get("only_nonempty")),
    }


def _ids(report: dict[str, Any] | None, key: str) -> list[str]:
    values = (report or {}).get(key) or []
    return [str(value) for value in values]


def _swe_tools() -> Any:
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import run_swebench_verified_slice  # type: ignore  # noqa: PLC0415

    return run_swebench_verified_slice


def _write_prediction_jsonl(path: Path, instance_id: str, patch: str) -> None:
    patch_text = patch if patch.endswith("\n") else patch + "\n"
    path.write_text(
        json.dumps(
            {
                "instance_id": instance_id,
                "model_patch": patch_text,
                "model_name_or_path": "tris-codex-helper-mission",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_prediction_jsonl_rows(path: Path, rows: list[dict[str, str]]) -> None:
    lines: list[str] = []
    for row in rows:
        patch = row["patch"]
        patch_text = patch if patch.endswith("\n") else patch + "\n"
        lines.append(
            json.dumps(
                {
                    "instance_id": row["instance_id"],
                    "model_patch": patch_text,
                    "model_name_or_path": "tris-codex-helper-mission",
                },
                sort_keys=True,
            )
        )
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def _latest_codex_helper_build_request_id(mission_id: str) -> str:
    for request in db.list_codex_build_requests(limit=25):
        if request.get("mission_id") == mission_id and "Codex-helper" in str(request.get("title") or ""):
            return str(request.get("id") or "")
    return ""


def _helper_patch_for_item(item: dict[str, Any]) -> tuple[str, str]:
    patch_path = Path(str(item.get("helper_patch_path") or ""))
    if patch_path.exists():
        return patch_path.read_text(encoding="utf-8").strip(), str(patch_path)
    return str(item.get("model_patch") or "").strip(), "embedded-helper-prediction"


def _sources_for_patch(tools: Any, item: dict[str, Any], patch: str, max_file_chars: int) -> list[dict[str, str]]:
    sources = tools.fetch_source_pack(item, max_file_chars=max_file_chars)
    if sources:
        return sources
    fallback: list[dict[str, str]] = []
    for source_path in tools.patch_file_paths(patch):
        source_text = tools.fetch_base_file(item, source_path)
        if source_text is None:
            continue
        fallback.append(
            {
                "path": source_path,
                "url": tools.raw_github_url(
                    str(item.get("repo") or ""),
                    str(item.get("base_commit") or ""),
                    source_path,
                ),
                "text": source_text[:max_file_chars],
                "preflight_text": source_text,
                "truncated": str(len(source_text) > max_file_chars),
                "compacted": "False",
            }
        )
    return fallback


def _preflight_helper_item(
    tools: Any,
    item: dict[str, Any],
    max_file_chars: int,
) -> tuple[dict[str, Any], str]:
    instance_id = str(item.get("instance_id") or "")
    patch, patch_source = _helper_patch_for_item(item)
    sources = _sources_for_patch(tools, item, patch, max_file_chars)
    validation_error = tools.validate_unified_diff_counts(patch)
    preflight_error = None if validation_error else tools.preflight_patch_apply(item, sources, patch)
    preflight_clean = bool(patch.strip()) and not validation_error and not preflight_error
    receipt = {
        "instance_id": instance_id,
        "repo": item.get("repo"),
        "base_commit": item.get("base_commit"),
        "version": item.get("version"),
        "difficulty": item.get("difficulty"),
        "fail_to_pass": item.get("fail_to_pass") or [],
        "patch_source": patch_source,
        "patch_nonempty": bool(patch.strip()),
        "patch_validation_error": validation_error,
        "patch_preflight_error": preflight_error,
        "preflight_clean": preflight_clean,
        "source_receipt": [
            {key: source.get(key, "") for key in ("path", "url", "truncated", "compacted")}
            for source in sources
        ],
        "source_pack_preview": tools.format_source_pack(sources)[:2200],
    }
    return receipt, patch


def benchmark_helper_status() -> dict[str, Any]:
    compare_path = _latest("swebench_verified_slice_*_official_compare.md", SWE_DIR)
    prediction_path = _latest("swebench_verified_slice_*.json", SWE_DIR)
    baseline_path = _latest("tris-baseline-hermes.*clean4*.json") or _latest(
        "tris-baseline-hermes.*_external8g.json"
    )
    tris_path = _latest("tris-architecture-on.*clean4*.json") or _latest(
        "tris-architecture-on.*_external8g.json"
    )
    helper_path = (
        _latest("tris-codex-helper-mission.codex_helper_mission_clean4*.json")
        or _latest("tris-codex-helper.codex_helper_swe_verified_clean*.json")
        or _latest("tris-codex-helper.*_external8g.json")
    )
    gold_control_path = _latest("swebench-gold-control.gold_control_swe_verified_slice_*.json")
    helper_prediction_path = _latest_runnable_helper_prediction()
    latest_helper_prediction_any_path = _latest("swebench_codex_helper_*.json", SWE_DIR)

    helper_report = _load_json(helper_path)
    baseline = _summary(_load_json(baseline_path))
    tris = _summary(_load_json(tris_path))
    helper = _summary(helper_report)
    gold_control = _summary(_load_json(gold_control_path))
    latest_prediction = _prediction_summary(_load_json(prediction_path))
    helper_prediction = _helper_prediction_summary(_load_json(helper_prediction_path))
    resolved_ids = ", ".join(_ids(helper_report, "resolved_ids")) or "none"
    unresolved_ids = ", ".join(_ids(helper_report, "unresolved_ids")) or "none"

    answer = "\n".join(
        [
            "SWE-bench helper lane status:",
            "",
            "Active coding route: Codex-helper recursive patch synthesis.",
            "Comparison routes: baseline Hermes and Tris architecture-on stay in the matched scoring lane so we can measure what improves.",
            "",
            "The latest official Verified clean slice submitted the same 4 instances through baseline Hermes, Tris architecture-on, and Codex-helper.",
            f"Baseline Hermes: resolved {baseline['resolved']}/{baseline['submitted']}, empty patches {baseline['empty_patch']}, errors {baseline['errors']}.",
            f"Tris architecture-on: resolved {tris['resolved']}/{tris['submitted']}, empty patches {tris['empty_patch']}, errors {tris['errors']}.",
            f"Clean Tris Codex helper: resolved {helper['resolved']}/{helper['submitted']}, empty patches {helper['empty_patch']}, errors {helper['errors']}.",
            f"Clean helper resolved ids: {resolved_ids}.",
            f"Clean helper unresolved ids: {unresolved_ids}.",
            f"Gold control: resolved {gold_control['resolved']}/{gold_control['submitted']}, empty patches {gold_control['empty_patch']}, errors {gold_control['errors']}.",
            f"Latest source-repaired prediction: baseline nonempty {latest_prediction['baseline_nonempty']}/{latest_prediction['baseline_count']}, Tris nonempty {latest_prediction['tris_nonempty']}/{latest_prediction['tris_count']}.",
            f"Latest clean helper prediction: nonempty {helper_prediction['nonempty']}/{helper_prediction['count']}, submitted {helper_prediction['submitted_count']}, offset {helper_prediction['offset']}, only-nonempty {helper_prediction['only_nonempty']}.",
            "",
            "Boundary: gold control uses public dataset gold patches to prove the evaluator path. The clean helper run uses helper-authored patches on fresh instances and does not read gold patch fields.",
            "Next gate: author helper patches for the next official subset, run local exact-source preflight, then launch the official evaluator only on nonempty preflight-clean predictions.",
        ]
    )

    payload = {
        "ok": bool(compare_path and helper_path),
        "source": "tris-benchmark-helper",
        "mode": "swebench-helper-receipt",
        "active_recursive_coding_route": {
            "name": "Codex-helper recursive patch synthesis",
            "status": "active",
            "role": "working coding lane for patch generation and evaluator-ready predictions",
            "report": str(helper_path) if helper_path else "",
            "prediction": str(helper_prediction_path) if helper_prediction_path else "",
        },
        "comparison_routes": {
            "baseline_hermes": {
                "status": "comparison",
                "report": str(baseline_path) if baseline_path else "",
            },
            "tris_architecture_on": {
                "status": "comparison",
                "report": str(tris_path) if tris_path else "",
            },
        },
        "answer": answer,
        "compare_receipt": str(compare_path) if compare_path else "",
        "reports": {
            "baseline": str(baseline_path) if baseline_path else "",
            "tris_architecture_on": str(tris_path) if tris_path else "",
            "tris_codex_helper": str(helper_path) if helper_path else "",
            "gold_control": str(gold_control_path) if gold_control_path else "",
            "latest_prediction": str(prediction_path) if prediction_path else "",
            "latest_helper_prediction": str(helper_prediction_path) if helper_prediction_path else "",
            "latest_helper_prediction_any": (
                str(latest_helper_prediction_any_path) if latest_helper_prediction_any_path else ""
            ),
        },
        "scores": {
            "baseline": baseline,
            "tris_architecture_on": tris,
            "tris_codex_helper": helper,
            "gold_control": gold_control,
            "latest_prediction": latest_prediction,
            "latest_helper_prediction": helper_prediction,
            "latest_helper_resolved_ids": _ids(helper_report, "resolved_ids"),
            "latest_helper_unresolved_ids": _ids(helper_report, "unresolved_ids"),
        },
        "truth_boundary": (
            "Receipt summary only. This does not claim public leaderboard score, "
            "broad SWE-bench performance, pure Tris model coding ability, or "
            "autonomous coding performance from gold-control rows."
        ),
        "next_gate": (
            "Author helper patches for the next official subset, run local "
            "exact-source preflight, then launch the official evaluator only on "
            "nonempty preflight-clean predictions."
        ),
    }
    db.log_event("benchmark_helper_status", payload)
    return payload


def queue_codex_helper_build_request(body: dict[str, Any] | None = None) -> dict[str, Any]:
    from .field_missions import create_codex_build_request

    helper = benchmark_helper_status()
    active_route = helper.get("active_recursive_coding_route") or {}
    reports = helper.get("reports") or {}
    scores = helper.get("scores") or {}
    codex_score = (scores.get("tris_codex_helper") or {})
    baseline_score = (scores.get("baseline") or {})
    tris_score = (scores.get("tris_architecture_on") or {})
    resolved_ids = ", ".join(scores.get("latest_helper_resolved_ids") or []) or "none"
    request_body = body or {}
    mission_id = str(request_body.get("mission_id") or "swebench-codex-helper-clean4").strip()

    build_request = create_codex_build_request(
        mission_id=mission_id,
        title="Wire Codex-helper recursive patch lane into Tris coding missions",
        evidence=(
            "Current SWE-bench Verified clean4 receipt shows Codex-helper as the "
            f"active patch route: resolved {codex_score.get('resolved', 0)}/"
            f"{codex_score.get('submitted', 0)} with {codex_score.get('empty_patch', 0)} "
            "empty patches. "
            f"Baseline Hermes remains {baseline_score.get('resolved', 0)}/"
            f"{baseline_score.get('submitted', 0)} and Tris architecture-on remains "
            f"{tris_score.get('resolved', 0)}/{tris_score.get('submitted', 0)} "
            "as comparison routes. "
            f"Resolved helper ids: {resolved_ids}. "
            f"Helper report: {active_route.get('report') or reports.get('tris_codex_helper')}. "
            f"Helper prediction: {active_route.get('prediction') or reports.get('latest_helper_prediction')}. "
            f"Compare receipt: {helper.get('compare_receipt')}."
        ),
        requested_change=(
            "Add a Tris coding mission action that accepts a source-backed coding task, "
            "creates a Codex-helper build request, generates or imports a helper-authored "
            "unified diff, runs local source preflight, writes evaluator-ready prediction "
            "receipts, and keeps baseline Hermes plus Tris architecture-on as comparison "
            "routes instead of treating them as the active patch lane."
        ),
        expected_tests=(
            "1. POST /api/benchmark-helper/queue-request creates one codex_build_requests row.\n"
            "2. GET /api/codex-build-requests returns the queued request with approval_state=draft.\n"
            "3. The request payload includes the current Codex-helper report, prediction, and compare receipt.\n"
            "4. No official evaluator run is launched unless the helper patch is preflight-clean and nonempty."
        ),
        approval_state="draft",
        implementation_receipt="",
        memory_ingestion_status="queued",
        payload={
            "request": request_body,
            "benchmark_helper": helper,
            "route": "codex-helper-recursive-patch-synthesis",
            "boundary": (
                "Queued recursive coding request only. This does not claim the "
                "mission action has been implemented or that a new evaluator run happened."
            ),
        },
    )
    payload = {
        "ok": True,
        "source": "tris-benchmark-helper",
        "mode": "codex-helper-build-request",
        "answer": (
            "Queued Codex-helper recursive patch request.\n\n"
            f"Build request: {build_request['id']}\n"
            "Approval state: draft\n"
            "Next gate: implement this queued coding mission action, then test it with a "
            "single source-backed SWE-bench task before scaling."
        ),
        "build_request": build_request,
        "benchmark_helper": helper,
        "next_gate": (
            "Implement the queued Codex-helper coding mission action and test one "
            "preflight-clean patch request before another official evaluator run."
        ),
    }
    db.log_event(
        "benchmark_helper_build_request_queued",
        {
            "build_request_id": build_request["id"],
            "mission_id": mission_id,
            "active_route": active_route.get("name"),
            "helper_report": active_route.get("report") or reports.get("tris_codex_helper"),
        },
    )
    return payload


def run_codex_helper_coding_mission(body: dict[str, Any] | None = None) -> dict[str, Any]:
    request_body = body or {}
    helper = benchmark_helper_status()
    reports = helper.get("reports") or {}
    scores = helper.get("scores") or {}
    helper_prediction_path = Path(str(reports.get("latest_helper_prediction") or ""))
    helper_prediction = _load_json(helper_prediction_path)
    items = (helper_prediction or {}).get("items") or []
    if not items:
        raise ValueError("No Codex-helper prediction items found.")

    resolved_ids = [str(value) for value in scores.get("latest_helper_resolved_ids") or []]
    requested_instance = str(request_body.get("instance_id") or "").strip()
    instance_id = requested_instance or (resolved_ids[0] if resolved_ids else "")
    selected = next(
        (
            item
            for item in items
            if str(item.get("instance_id") or "") == instance_id
        ),
        None,
    )
    if selected is None:
        selected = next((item for item in items if item.get("patch_nonempty")), items[0])
        instance_id = str(selected.get("instance_id") or "")
    if not instance_id:
        raise ValueError("No SWE-bench instance id selected.")

    tools = _swe_tools()
    max_file_chars = int(request_body.get("max_file_chars") or 14000)
    row_receipt, patch = _preflight_helper_item(tools, selected, max_file_chars)
    patch_source = str(row_receipt["patch_source"])
    validation_error = row_receipt.get("patch_validation_error")
    preflight_error = row_receipt.get("patch_preflight_error")
    preflight_clean = bool(patch.strip()) and not validation_error and not preflight_error

    run_id = time.strftime("codex_helper_coding_mission_%Y%m%dT%H%M%SZ", time.gmtime())
    CODING_MISSION_DIR.mkdir(parents=True, exist_ok=True)
    json_path = CODING_MISSION_DIR / f"{run_id}.json"
    md_path = CODING_MISSION_DIR / f"{run_id}.md"
    prediction_path = CODING_MISSION_DIR / f"{run_id}_predictions.jsonl"
    if preflight_clean:
        _write_prediction_jsonl(prediction_path, instance_id, patch)
    else:
        prediction_path.write_text("", encoding="utf-8")

    mission_id = str(request_body.get("mission_id") or "swebench-codex-helper-clean4").strip()
    build_request_id = str(request_body.get("build_request_id") or "").strip()
    if not build_request_id:
        build_request_id = _latest_codex_helper_build_request_id(mission_id)

    receipt = {
        "id": run_id,
        "source": "tris-codex-helper-coding-mission",
        "mode": "one-task-helper-preflight",
        "ok": preflight_clean,
        "status": "preflight_clean" if preflight_clean else "preflight_failed",
        "instance_id": instance_id,
        "repo": row_receipt.get("repo"),
        "base_commit": row_receipt.get("base_commit"),
        "version": row_receipt.get("version"),
        "difficulty": row_receipt.get("difficulty"),
        "fail_to_pass": row_receipt.get("fail_to_pass") or [],
        "patch_source": patch_source,
        "patch_nonempty": bool(row_receipt.get("patch_nonempty")),
        "patch_validation_error": validation_error,
        "patch_preflight_error": preflight_error,
        "source_receipt": row_receipt.get("source_receipt") or [],
        "source_pack_preview": row_receipt.get("source_pack_preview") or "",
        "prediction_jsonl": str(prediction_path),
        "paths": {
            "json": str(json_path),
            "markdown": str(md_path),
            "prediction_jsonl": str(prediction_path),
        },
        "build_request_id": build_request_id,
        "truth_boundary": (
            "This is a local one-task Codex-helper preflight receipt. It imports a "
            "helper-authored patch, validates it, and writes evaluator-ready JSONL "
            "only when local source preflight passes. It does not launch or claim a "
            "new official SWE-bench evaluator run."
        ),
        "next_gate": (
            "Use this one-task preflight-clean mission as the template for a bounded "
            "clean4 mission action, then run the official evaluator only on nonempty "
            "preflight-clean predictions."
        ),
    }
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(
        "\n".join(
            [
                f"# Codex Helper Coding Mission {run_id}",
                "",
                f"- Instance: `{instance_id}`",
                f"- Status: `{receipt['status']}`",
                f"- Patch source: `{patch_source}`",
                f"- Prediction JSONL: `{prediction_path}`",
                f"- Build request: `{build_request_id or 'not-linked'}`",
                "",
                "## Source Files",
                "",
                *[
                    f"- `{source.get('path')}` -> {source.get('url')}"
                    for source in receipt["source_receipt"]
                ],
                "",
                "## Validation",
                "",
                f"- Unified diff validation: `{validation_error or 'passed'}`",
                f"- Local preflight: `{preflight_error or 'passed'}`",
                "",
                "## Boundary",
                "",
                receipt["truth_boundary"],
                "",
                "## Next Gate",
                "",
                receipt["next_gate"],
            ]
        ),
        encoding="utf-8",
    )

    build_request_updated = False
    if build_request_id:
        build_request_updated = db.update_codex_build_request_receipt(
            build_request_id,
            implementation_receipt=str(md_path),
            approval_state="implemented_local_preflight_clean" if preflight_clean else "needs_patch_repair",
            memory_ingestion_status="receipt_saved",
            receipt_payload=receipt,
        )
    db.save_memory_item(
        "codex_helper_coding_mission",
        f"codex_helper_coding_mission:{run_id}",
        f"Codex-helper coding mission: {instance_id}",
        f"{receipt['status']}\n{receipt['truth_boundary']}\n{receipt['next_gate']}",
        receipt,
    )
    db.log_event(
        "codex_helper_coding_mission",
        {
            "run_id": run_id,
            "instance_id": instance_id,
            "ok": preflight_clean,
            "build_request_id": build_request_id,
            "build_request_updated": build_request_updated,
            "prediction_jsonl": str(prediction_path),
        },
    )

    answer = "\n".join(
        [
            "Codex-helper coding mission receipt:",
            "",
            f"Instance: {instance_id}",
            f"Status: {receipt['status']}",
            f"Patch source: {patch_source}",
            f"Prediction JSONL: {prediction_path}",
            f"Build request updated: {build_request_updated}",
            "",
            "Boundary: local preflight only; no new official evaluator run.",
            f"Next gate: {receipt['next_gate']}",
        ]
    )
    return {
        "ok": preflight_clean,
        "source": "tris-codex-helper-coding-mission",
        "mode": "one-task-helper-preflight",
        "answer": answer,
        "receipt": receipt,
        "build_request_updated": build_request_updated,
        "next_gate": receipt["next_gate"],
    }


def run_codex_helper_clean_slice_mission(body: dict[str, Any] | None = None) -> dict[str, Any]:
    request_body = body or {}
    helper = benchmark_helper_status()
    reports = helper.get("reports") or {}
    helper_prediction_path = Path(str(reports.get("latest_helper_prediction") or ""))
    helper_prediction = _load_json(helper_prediction_path)
    items = list((helper_prediction or {}).get("items") or [])
    if not items:
        raise ValueError("No Codex-helper prediction items found.")

    requested_ids = [str(value) for value in request_body.get("instance_ids") or [] if str(value).strip()]
    if requested_ids:
        selected_items = [
            item
            for item in items
            if str(item.get("instance_id") or "") in requested_ids
        ]
    else:
        selected_items = items
    requested_count = int(request_body.get("count") or 0)
    if requested_count > 0:
        selected_items = selected_items[:requested_count]
    if not selected_items:
        raise ValueError("No matching Codex-helper clean-slice rows selected.")

    tools = _swe_tools()
    max_file_chars = int(request_body.get("max_file_chars") or 14000)
    run_id = time.strftime("codex_helper_clean4_mission_%Y%m%dT%H%M%SZ", time.gmtime())
    CODING_MISSION_DIR.mkdir(parents=True, exist_ok=True)
    json_path = CODING_MISSION_DIR / f"{run_id}.json"
    md_path = CODING_MISSION_DIR / f"{run_id}.md"
    prediction_path = CODING_MISSION_DIR / f"{run_id}_predictions.jsonl"

    rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, str]] = []
    for item in selected_items:
        row_receipt, patch = _preflight_helper_item(tools, item, max_file_chars)
        rows.append(row_receipt)
        if row_receipt.get("preflight_clean"):
            prediction_rows.append(
                {
                    "instance_id": str(row_receipt["instance_id"]),
                    "patch": patch,
                }
            )

    _write_prediction_jsonl_rows(prediction_path, prediction_rows)
    submitted_count = len(selected_items)
    clean_count = len(prediction_rows)
    failed_count = submitted_count - clean_count
    all_preflight_clean = submitted_count > 0 and clean_count == submitted_count
    nonempty_prediction_jsonl = prediction_path.exists() and prediction_path.stat().st_size > 0

    mission_id = str(request_body.get("mission_id") or "swebench-codex-helper-clean4").strip()
    build_request_id = str(request_body.get("build_request_id") or "").strip()
    if not build_request_id:
        build_request_id = _latest_codex_helper_build_request_id(mission_id)

    receipt = {
        "id": run_id,
        "source": "tris-codex-helper-clean-slice-mission",
        "mode": "clean4-helper-preflight",
        "ok": all_preflight_clean and nonempty_prediction_jsonl,
        "status": "preflight_clean" if all_preflight_clean else "preflight_partial",
        "helper_prediction_source": str(helper_prediction_path),
        "submitted_count": submitted_count,
        "clean_count": clean_count,
        "failed_count": failed_count,
        "all_preflight_clean": all_preflight_clean,
        "nonempty_prediction_jsonl": nonempty_prediction_jsonl,
        "prediction_jsonl": str(prediction_path),
        "rows": rows,
        "paths": {
            "json": str(json_path),
            "markdown": str(md_path),
            "prediction_jsonl": str(prediction_path),
        },
        "build_request_id": build_request_id,
        "official_evaluator_status": "not_run",
        "truth_boundary": (
            "This is a local clean-slice Codex-helper preflight receipt. It imports "
            "helper-authored patches, validates unified diffs, checks exact-source "
            "application, and writes evaluator-ready JSONL only for rows that pass "
            "local preflight. It does not read dataset gold patches and does not by "
            "itself claim a new official SWE-bench evaluator run."
        ),
        "next_gate": (
            "Run the official SWE-bench evaluator only if this prediction JSONL is "
            "nonempty and every selected row is preflight-clean."
        ),
    }
    json_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        f"# Codex Helper Clean4 Mission {run_id}",
        "",
        f"- Status: `{receipt['status']}`",
        f"- Helper prediction source: `{helper_prediction_path}`",
        f"- Submitted rows: `{submitted_count}`",
        f"- Preflight-clean rows: `{clean_count}`",
        f"- Failed rows: `{failed_count}`",
        f"- Prediction JSONL: `{prediction_path}`",
        f"- Build request: `{build_request_id or 'not-linked'}`",
        "",
        "## Rows",
        "",
        "| Instance | Patch | Unified Diff | Local Preflight | Source Files |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['instance_id']}` | "
            f"`{'nonempty' if row.get('patch_nonempty') else 'empty'}` | "
            f"`{row.get('patch_validation_error') or 'passed'}` | "
            f"`{row.get('patch_preflight_error') or 'passed'}` | "
            f"`{len(row.get('source_receipt') or [])}` |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            receipt["truth_boundary"],
            "",
            "## Next Gate",
            "",
            receipt["next_gate"],
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    build_request_updated = False
    if build_request_id:
        build_request_updated = db.update_codex_build_request_receipt(
            build_request_id,
            implementation_receipt=str(md_path),
            approval_state="implemented_clean4_preflight_clean" if all_preflight_clean else "needs_patch_repair",
            memory_ingestion_status="receipt_saved",
            receipt_payload=receipt,
        )
    db.save_memory_item(
        "codex_helper_clean_slice_mission",
        f"codex_helper_clean_slice_mission:{run_id}",
        f"Codex-helper clean4 mission: {clean_count}/{submitted_count} preflight-clean",
        f"{receipt['status']}\n{receipt['truth_boundary']}\n{receipt['next_gate']}",
        receipt,
    )
    db.log_event(
        "codex_helper_clean_slice_mission",
        {
            "run_id": run_id,
            "ok": receipt["ok"],
            "submitted_count": submitted_count,
            "clean_count": clean_count,
            "failed_count": failed_count,
            "build_request_id": build_request_id,
            "build_request_updated": build_request_updated,
            "prediction_jsonl": str(prediction_path),
        },
    )

    answer = "\n".join(
        [
            "Codex-helper clean4 mission receipt:",
            "",
            f"Status: {receipt['status']}",
            f"Preflight-clean rows: {clean_count}/{submitted_count}",
            f"Prediction JSONL: {prediction_path}",
            f"Build request updated: {build_request_updated}",
            "",
            "Boundary: local preflight only; official evaluator is still a separate gate.",
            f"Next gate: {receipt['next_gate']}",
        ]
    )
    return {
        "ok": bool(receipt["ok"]),
        "source": "tris-codex-helper-clean-slice-mission",
        "mode": "clean4-helper-preflight",
        "answer": answer,
        "receipt": receipt,
        "build_request_updated": build_request_updated,
        "next_gate": receipt["next_gate"],
    }


def wants_benchmark_helper(content: str) -> bool:
    text = " ".join(str(content or "").lower().split())
    if not text:
        return False
    terms = (
        "swe-bench",
        "swebench",
        "verified slice",
        "coding benchmark",
        "code benchmark",
        "codex helper",
        "codex-helper",
        "recursive patch",
        "recursive coding",
        "active coding route",
        "helper loop",
        "patch repair",
        "patch synthesis",
        "official benchmark",
    )
    return any(term in text for term in terms)
