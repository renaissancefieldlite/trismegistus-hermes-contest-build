#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
OUT_DIR = ROOT / "data" / "swebench"
HELPER_PATCH_DIR = OUT_DIR / "codex_helper_patches"

sys.path.insert(0, str(SCRIPTS))
from run_swebench_verified_slice import (  # noqa: E402
    fetch_source_pack,
    format_source_pack,
    list_from_jsonish,
    load_rows,
    validate_unified_diff_counts,
)


def load_patch(patch_dir: Path, instance_id: str) -> tuple[str, str | None]:
    path = patch_dir / f"{instance_id}.diff"
    if not path.exists():
        return "", "missing helper patch"
    patch = path.read_text(encoding="utf-8").strip()
    if not patch:
        return "", "empty helper patch"
    error = validate_unified_diff_counts(patch)
    if error:
        return "", error
    return patch + "\n", None


def write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            handle.write(
                json.dumps(
                    {
                        "instance_id": item["instance_id"],
                        "model_patch": item["model_patch"],
                        "model_name_or_path": "tris-codex-helper",
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a SWE-bench prediction file from Codex-helper authored patch files. "
            "This script never reads the dataset gold patch field."
        )
    )
    parser.add_argument("--dataset-name", default="SWE-bench/SWE-bench_Verified")
    parser.add_argument("--split", default="test")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--patch-dir", type=Path, default=HELPER_PATCH_DIR)
    parser.add_argument("--max-file-chars", type=int, default=14000)
    parser.add_argument(
        "--only-nonempty",
        action="store_true",
        help="Write only nonempty validated helper patches to the evaluator JSONL.",
    )
    args = parser.parse_args()

    rows = load_rows(args.dataset_name, args.split, args.count, args.offset)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    args.patch_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("swebench_codex_helper_%Y%m%dT%H%M%SZ", time.gmtime())
    json_path = OUT_DIR / f"{run_id}.json"
    md_path = OUT_DIR / f"{run_id}.md"
    prediction_path = OUT_DIR / f"{run_id}_predictions.jsonl"

    items: list[dict[str, Any]] = []
    for row in rows:
        instance_id = str(row.get("instance_id") or "")
        sources = fetch_source_pack(row, max_file_chars=args.max_file_chars)
        patch, validation_error = load_patch(args.patch_dir, instance_id)
        items.append(
            {
                "instance_id": instance_id,
                "repo": row.get("repo"),
                "base_commit": row.get("base_commit"),
                "version": row.get("version"),
                "difficulty": row.get("difficulty"),
                "fail_to_pass": list_from_jsonish(row.get("FAIL_TO_PASS")),
                "source_receipt": [
                    {key: source[key] for key in ("path", "url", "truncated")}
                    for source in sources
                ],
                "source_pack_preview": format_source_pack(sources)[:1600],
                "helper_patch_path": str(args.patch_dir / f"{instance_id}.diff"),
                "model_patch": patch,
                "patch_nonempty": bool(patch.strip()),
                "patch_validation_error": validation_error,
            }
        )

    prediction_items = (
        [item for item in items if item["patch_nonempty"]] if args.only_nonempty else items
    )
    write_jsonl(prediction_path, prediction_items)
    payload = {
        "id": run_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_name": args.dataset_name,
        "split": args.split,
        "offset": args.offset,
        "count": len(rows),
        "submitted_count": len(prediction_items),
        "only_nonempty": args.only_nonempty,
        "patch_dir": str(args.patch_dir),
        "prediction_jsonl": str(prediction_path),
        "truth_boundary": (
            "Codex-helper prediction builder. It consumes helper-authored patch files "
            "and source/problem/test metadata, and never reads the dataset gold patch field."
        ),
        "items": items,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        f"# SWE-bench Codex Helper Slice {run_id}",
        "",
        f"- Dataset: `{args.dataset_name}`",
        f"- Split: `{args.split}`",
        f"- Offset: `{args.offset}`",
        f"- Count: `{len(rows)}`",
        f"- Submitted predictions: `{len(prediction_items)}`",
        f"- Only nonempty: `{args.only_nonempty}`",
        f"- Patch dir: `{args.patch_dir}`",
        f"- Prediction JSONL: `{prediction_path}`",
        "",
        "## Boundary",
        "",
        payload["truth_boundary"],
        "",
        "## Rows",
        "",
        "| Instance | Patch Nonempty | Validation | Patch File |",
        "| --- | ---: | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| `{item['instance_id']}` | `{item['patch_nonempty']}` | "
            f"{item['patch_validation_error'] or ''} | `{item['helper_patch_path']}` |"
        )
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "id": run_id,
                "json": str(json_path),
                "markdown": str(md_path),
                "prediction_jsonl": str(prediction_path),
                "count": len(rows),
                "nonempty": sum(1 for item in items if item["patch_nonempty"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
