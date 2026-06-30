#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "swebench"
os.environ.setdefault("TRIS_BASELINE_MAX_NEW_TOKENS", "320")
sys.path.insert(0, str(ROOT))

GFL_GENERATE_URL = os.environ.get("TRIS_GFL_GENERATE_URL", "http://127.0.0.1:8788/api/generate")
DIRECT_PATCH_MAX_NEW_TOKENS = int(os.environ.get("TRIS_PATCH_MAX_NEW_TOKENS", "900"))


def load_rows(dataset_name: str, split: str, count: int, offset: int = 0) -> list[dict[str, Any]]:
    from datasets import load_dataset

    start = max(0, offset)
    stop = start + count
    dataset = load_dataset(dataset_name, "default", split=f"{split}[{start}:{stop}]")
    return [dict(row) for row in dataset]


def raw_github_url(repo: str, commit: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"


def list_from_jsonish(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [value]
        return parsed if isinstance(parsed, list) else [parsed]
    return []


def add_path(paths: list[str], path: str) -> None:
    clean = path.strip().lstrip("/")
    if "github.com/" in clean or clean.startswith(("home/", "Users/", "etc/")):
        return
    if clean.endswith(".py") and clean not in paths:
        paths.append(clean)


def implementation_candidates_for_test_path(path: str) -> list[str]:
    candidates: list[str] = []
    if "/tests/test_" in path:
        candidates.append(path.replace("/tests/test_", "/").replace("test_", ""))
    if path == "astropy/io/ascii/tests/test_rst.py":
        candidates.append("astropy/io/ascii/rst.py")
    if path == "astropy/coordinates/tests/test_sky_coord.py":
        candidates.append("astropy/coordinates/sky_coordinate.py")
    if path == "astropy/units/tests/test_quantity_ufuncs.py":
        candidates.append("astropy/units/quantity.py")
    if path == "astropy/coordinates/tests/test_intermediate_transformations.py":
        candidates.extend(
            [
                "astropy/coordinates/builtin_frames/intermediate_rotation_transforms.py",
                "astropy/coordinates/builtin_frames/cirs_observed_transforms.py",
                "astropy/coordinates/builtin_frames/icrs_observed_transforms.py",
                "astropy/coordinates/builtin_frames/itrs.py",
            ]
        )
    return candidates


def guess_source_paths(row: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in list_from_jsonish(row.get("FAIL_TO_PASS")):
        path = str(item).split("::", 1)[0]
        for source_path in implementation_candidates_for_test_path(path):
            add_path(paths, source_path)
        add_path(paths, path)
    text = "\n".join(
        [
            str(row.get("problem_statement") or ""),
            str(row.get("hints_text") or ""),
        ]
    )
    for github_path in re.findall(
        r"github\.com/[^/\s]+/[^/\s]+/blob/[0-9a-fA-F]+/([\w./-]+\.py)",
        text,
    ):
        add_path(paths, github_path)
    for path in re.findall(r"[\w./-]+\.py", text):
        add_path(paths, path)
    return paths[:4]


def source_keywords(row: dict[str, Any], path: str) -> list[str]:
    words: list[str] = []
    if path.endswith("rst.py"):
        words.extend(["RST", "header_rows", "write", "__init__"])
    if path.endswith("quantity.py"):
        words.extend(
            [
                "__array_ufunc__",
                "converters_and_unit(function",
                "except ValueError",
                "return NotImplemented",
                'kwargs.get("out"',
            ]
        )
    if path.endswith("sky_coordinate.py"):
        words.extend(["__getattr__", "frame_transform_graph", "lookup_name", "transform_to"])
    if path.endswith("sliced_wcs.py"):
        words.extend(["world_to_pixel_values", "_world_keep", "_pixel_keep"])
    for item in list_from_jsonish(row.get("FAIL_TO_PASS")):
        test_name = str(item).split("::")[-1]
        if test_name:
            base_name = test_name.split("[", 1)[0]
            words.extend([base_name, base_name.replace("test_", "")])
    problem = str(row.get("problem_statement") or "")
    for match in re.findall(r"`([A-Za-z_][\w.]*)`|\b([A-Za-z_][\w]{4,})\b", problem):
        token = next((part for part in match if part), "")
        if token and token.lower() not in {"description", "following", "python", "would", "great", "support"}:
            words.append(token)
    seen: set[str] = set()
    clean_words = []
    for word in words:
        clean = str(word).strip()
        if clean and clean not in seen:
            seen.add(clean)
            clean_words.append(clean)
    return clean_words[:18]


def compact_source_text(path: str, text: str, row: dict[str, Any], max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    lines = text.splitlines()
    keywords = source_keywords(row, path)
    selected: set[int] = set()
    lowered_keywords = [keyword.lower() for keyword in keywords if keyword]
    for index, line in enumerate(lines):
        lower = line.lower()
        if any(keyword.lower() in lower for keyword in lowered_keywords):
            for near in range(max(0, index - 18), min(len(lines), index + 42)):
                selected.add(near)
    if not selected:
        return text[:max_chars]
    chunks = []
    last = -2
    for index in sorted(selected):
        if index != last + 1:
            chunks.append(f"\n# ... {path} lines {index + 1} ...")
        chunks.append(lines[index])
        last = index
    compact = "\n".join(chunks).strip()
    if len(compact) > max_chars:
        return compact[:max_chars]
    return compact


def fetch_source_pack(row: dict[str, Any], max_file_chars: int) -> list[dict[str, str]]:
    repo = str(row.get("repo") or "")
    commit = str(row.get("base_commit") or "")
    sources: list[dict[str, str]] = []
    if not repo or not commit:
        return sources
    for path in guess_source_paths(row):
        url = raw_github_url(repo, commit, path)
        try:
            with urlopen(url, timeout=20) as response:
                text = response.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, UnicodeDecodeError):
            continue
        compacted = compact_source_text(path, text, row, max_file_chars)
        sources.append(
            {
                "path": path,
                "url": url,
                "text": compacted,
                "preflight_text": text,
                "truncated": str(len(text) > max_file_chars),
                "compacted": str(compacted != text),
            }
        )
    return sources


def format_source_pack(sources: list[dict[str, str]]) -> str:
    if not sources:
        return "No source files were fetched for this slice."
    blocks = []
    for source in sources:
        blocks.append(
            "\n".join(
                [
                    f"### {source['path']}",
                    f"Source URL: {source['url']}",
                    f"Truncated: {source['truncated']}",
                    f"Compacted: {source.get('compacted', 'False')}",
                    "```python",
                    source["text"],
                    "```",
                ]
            )
        )
    return "\n\n".join(blocks)


def validate_unified_diff_counts(patch: str) -> str | None:
    if not patch.strip():
        return None
    first_patch_line = next((line for line in patch.splitlines() if line.strip()), "")
    if first_patch_line.startswith("@@"):
        return "missing file headers before hunk"
    if "diff --git " not in patch and not re.search(r"(?m)^--- a/.+\n\+\+\+ b/.+", patch):
        return "missing unified diff file headers"
    lines = patch.splitlines()
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    saw_hunk = False
    index = 0
    while index < len(lines):
        match = hunk_re.match(lines[index])
        if not match:
            index += 1
            continue
        saw_hunk = True
        old_expected = int(match.group(2) or "1")
        new_expected = int(match.group(4) or "1")
        old_seen = 0
        new_seen = 0
        index += 1
        while index < len(lines):
            line = lines[index]
            if hunk_re.match(line) or line.startswith("diff --git ") or line.startswith("--- "):
                break
            if line.startswith("\\ No newline at end of file"):
                index += 1
                continue
            if not line:
                old_seen += 1
                new_seen += 1
            elif line.startswith(" "):
                old_seen += 1
                new_seen += 1
            elif line.startswith("-"):
                old_seen += 1
            elif line.startswith("+"):
                new_seen += 1
            else:
                return f"unexpected hunk line: {line[:80]}"
            index += 1
        if old_seen != old_expected or new_seen != new_expected:
            return (
                f"hunk count mismatch: expected -{old_expected}/+{new_expected}, "
                f"saw -{old_seen}/+{new_seen}"
            )
    if not saw_hunk:
        return "no unified diff hunks found"
    return None


def normalize_unified_diff(patch: str) -> str:
    if not patch.strip():
        return ""
    lines = patch.splitlines()
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")
    normalized: list[str] = []
    index = 0
    while index < len(lines):
        match = hunk_re.match(lines[index])
        if not match:
            normalized.append(lines[index])
            index += 1
            continue
        old_start = int(match.group(1))
        new_start = int(match.group(3))
        tail = match.group(5) or ""
        hunk_lines: list[str] = []
        old_seen = 0
        new_seen = 0
        index += 1
        while index < len(lines):
            line = lines[index]
            if hunk_re.match(line) or line.startswith(("diff --git ", "--- ", "Index: ")):
                break
            if line.startswith("\\ No newline at end of file"):
                hunk_lines.append(line)
            elif not line:
                hunk_lines.append(" ")
                old_seen += 1
                new_seen += 1
            elif line[0] == " ":
                hunk_lines.append(line)
                old_seen += 1
                new_seen += 1
            elif line[0] == "-":
                hunk_lines.append(line)
                old_seen += 1
            elif line[0] == "+":
                hunk_lines.append(line)
                new_seen += 1
            else:
                hunk_lines.append(line)
            index += 1
        normalized.append(f"@@ -{old_start},{old_seen} +{new_start},{new_seen} @@{tail}")
        normalized.extend(hunk_lines)
    return "\n".join(normalized).strip()


def patch_file_paths(patch: str) -> list[str]:
    paths: list[str] = []
    for line in patch.splitlines():
        if not line.startswith(("--- ", "+++ ")):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        path = parts[1]
        if path == "/dev/null":
            continue
        clean = path.removeprefix("a/").removeprefix("b/")
        if clean and clean not in paths:
            paths.append(clean)
    return paths


def fetch_base_file(row: dict[str, Any], path: str) -> str | None:
    repo = str(row.get("repo") or "")
    commit = str(row.get("base_commit") or "")
    if not repo or not commit or not path:
        return None
    try:
        with urlopen(raw_github_url(repo, commit, path), timeout=20) as response:
            return response.read().decode("utf-8", errors="replace")
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError):
        return None


def preflight_patch_apply(row: dict[str, Any], sources: list[dict[str, str]], patch: str) -> str | None:
    if not patch.strip():
        return None
    paths = patch_file_paths(patch)
    if not paths:
        return "preflight missing patch file paths"
    source_by_path = {source["path"]: source.get("preflight_text") or source.get("text", "") for source in sources}
    with tempfile.TemporaryDirectory(prefix="tris_swe_patch_preflight_") as tmp:
        repo_dir = Path(tmp)
        for path in paths:
            text = source_by_path.get(path)
            if text is None:
                text = fetch_base_file(row, path)
            if text is None:
                return f"preflight missing base file: {path}"
            target = repo_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        patch_path = repo_dir / "candidate.patch"
        patch_text = patch if patch.endswith("\n") else patch + "\n"
        patch_path.write_text(patch_text, encoding="utf-8")
        result = subprocess.run(
            ["git", "apply", "--check", "--recount", str(patch_path)],
            cwd=repo_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    if result.returncode == 0:
        return None
    message = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part).strip()
    return message or f"git apply --check failed with exit {result.returncode}"


def _json_objects_from_text(text: str) -> list[Any]:
    raw = str(text or "").strip()
    if not raw:
        return []
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    candidates = [fence.group(1).strip()] if fence else []
    candidates.append(raw)
    for candidate in candidates:
        try:
            return [json.loads(candidate)]
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    objects: list[Any] = []
    for index, char in enumerate(raw):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        objects.append(value)
    return objects


def _strip_numbered_source_lines(text: str) -> str:
    lines = str(text or "").splitlines()
    stripped: list[str] = []
    saw_numbered = False
    for line in lines:
        match = re.match(r"^\s*\d{1,5}:\s?(.*)$", line)
        if match:
            saw_numbered = True
            stripped.append(match.group(1))
        else:
            stripped.append(line)
    return "\n".join(stripped) if saw_numbered else str(text or "")


def _intent_changes_from_value(value: Any) -> list[dict[str, str]]:
    if isinstance(value, list):
        raw_changes = value
    elif isinstance(value, dict):
        raw_changes = value.get("changes") or value.get("edits") or value.get("patches") or [value]
    else:
        return []
    if not isinstance(raw_changes, list):
        return []

    changes: list[dict[str, str]] = []
    for item in raw_changes:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("file") or item.get("filename") or "").strip()
        old = item.get("old") or item.get("before") or item.get("find") or item.get("original")
        new = item.get("new") or item.get("after") or item.get("replace") or item.get("replacement")
        if not path or old is None or new is None:
            continue
        changes.append(
            {
                "path": path.lstrip("/").removeprefix("a/").removeprefix("b/"),
                "old": _strip_numbered_source_lines(str(old)).strip("\n"),
                "new": _strip_numbered_source_lines(str(new)).strip("\n"),
            }
        )
    return changes


def _apply_intent_change(source: str, old: str, new: str) -> tuple[str | None, str | None]:
    if not old:
        return None, "empty old snippet"
    variants = [old, old + "\n"]
    if "\r\n" in source:
        variants.extend([old.replace("\n", "\r\n"), (old + "\n").replace("\n", "\r\n")])
    for variant in variants:
        count = source.count(variant)
        if count == 1:
            return source.replace(variant, new, 1), None
        if count > 1:
            return None, "old snippet matched multiple locations"
    return None, "old snippet not found in exact base source"


def compile_patch_intent(row: dict[str, Any], sources: list[dict[str, str]], text: str) -> tuple[str, str | None]:
    changes: list[dict[str, str]] = []
    for value in _json_objects_from_text(text):
        changes.extend(_intent_changes_from_value(value))
    if not changes:
        return "", "no structured patch intent found"

    source_by_path = {source["path"]: source.get("preflight_text") or source.get("text", "") for source in sources}
    updated_by_path: dict[str, str] = {}
    for change in changes:
        path = change["path"]
        original = updated_by_path.get(path) or source_by_path.get(path) or fetch_base_file(row, path)
        if original is None:
            return "", f"intent missing base file: {path}"
        updated, error = _apply_intent_change(original, change["old"], change["new"])
        if error:
            return "", f"{path}: {error}"
        updated_by_path[path] = updated or original

    patches: list[str] = []
    for path, updated in updated_by_path.items():
        original = source_by_path.get(path) or fetch_base_file(row, path)
        if original is None:
            return "", f"intent missing base file: {path}"
        if original == updated:
            continue
        diff = difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        diff_lines = list(diff)
        if len(diff_lines) <= 2:
            continue
        patches.append("\n".join([f"diff --git a/{path} b/{path}", *diff_lines]))

    patch = normalize_unified_diff("\n".join(patches))
    if not patch.strip():
        return "", "structured patch intent produced no source change"
    validation_error = validate_unified_diff_counts(patch)
    if validation_error:
        return "", validation_error
    preflight_error = preflight_patch_apply(row, sources, patch)
    if preflight_error:
        return "", preflight_error
    return patch, None


def _source_by_path(sources: list[dict[str, str]]) -> dict[str, str]:
    return {source["path"]: source.get("preflight_text") or source.get("text", "") for source in sources}


def _error_line_refs(error: str) -> list[tuple[str, int]]:
    refs: list[tuple[str, int]] = []
    for path, line in re.findall(r"([\w./-]+\.py):(\d+)", error or ""):
        refs.append((path, int(line)))
    return refs


def source_window_for_repair(
    row: dict[str, Any],
    sources: list[dict[str, str]],
    patch: str,
    error: str,
    radius: int = 40,
) -> str:
    by_path = _source_by_path(sources)
    error_refs = _error_line_refs(error)
    refs: list[tuple[str, int]] = []
    paths = patch_file_paths(patch)
    for path in paths:
        text = by_path.get(path)
        if text is None:
            text = fetch_base_file(row, path)
        if text is None:
            continue
        lowered = text.lower()
        for keyword in source_keywords(row, path):
            clean_keyword = keyword.strip()
            if not clean_keyword:
                continue
            position = lowered.find(clean_keyword.lower())
            if position < 0:
                continue
            line_number = text[:position].count("\n") + 1
            refs.append((path, line_number))
    refs.extend(error_refs)
    if not refs:
        for path in paths:
            refs.append((path, 1))
    blocks = []
    seen: set[tuple[str, int]] = set()
    emitted_lines_by_path: dict[str, list[int]] = {}
    for path, line_number in refs[:6]:
        if (path, line_number) in seen:
            continue
        if any(abs(line_number - existing) <= radius for existing in emitted_lines_by_path.get(path, [])):
            continue
        seen.add((path, line_number))
        text = by_path.get(path)
        if text is None:
            text = fetch_base_file(row, path)
        if text is None:
            continue
        lines = text.splitlines()
        start = max(1, line_number - radius)
        stop = min(len(lines), line_number + radius)
        numbered = "\n".join(f"{index:04d}: {lines[index - 1]}" for index in range(start, stop + 1))
        blocks.append(f"### {path} lines {start}-{stop}\n```python\n{numbered}\n```")
        emitted_lines_by_path.setdefault(path, []).append(line_number)
    if blocks:
        return "\n\n".join(blocks)
    return format_source_pack(sources)


def build_repair_prompt(
    row: dict[str, Any],
    route: str,
    original_prompt: str,
    previous_patch: str,
    validation_error: str | None,
    preflight_error: str | None,
    sources: list[dict[str, str]],
) -> str:
    failure = preflight_error or validation_error or "candidate did not pass local patch checks"
    source_window = source_window_for_repair(row, sources, previous_patch, failure)
    problem = str(row.get("problem_statement") or "")[:1800]
    fail_to_pass = list_from_jsonish(row.get("FAIL_TO_PASS"))
    hints = str(row.get("hints_text") or "").strip()[:800]
    return f"""Strict SWE-bench patch repair.

Route: {route}
Instance id: {row.get('instance_id')}
Repository: {row.get('repo')}
Base commit: {row.get('base_commit')}
Fail-to-pass tests: {json.dumps(fail_to_pass)}

The previous candidate failed local preflight:
{failure}

Problem statement:
{problem}

Hints:
{hints or 'none supplied'}

Previous candidate:
```diff
{previous_patch or '# no usable patch'}
```

Exact base-commit source context for the failed location:
{source_window}

Repair task:
- Rewrite the patch against the exact base source above.
- Return one complete unified diff only.
- Include `diff --git`, `--- a/path`, `+++ b/path`, and valid hunks.
- Do not explain.
- Do not emit Markdown fences.
- If the source context is not sufficient, return exactly:
# insufficient source context: unable to patch safely
"""


def clean_patch_from_result(
    row: dict[str, Any],
    sources: list[dict[str, str]],
    text: str,
) -> tuple[str, str | None, str | None]:
    patch = normalize_unified_diff(extract_patch(text))
    if patch:
        validation_error = validate_unified_diff_counts(patch)
        if validation_error in {"missing unified diff file headers", "missing file headers before hunk"}:
            compiled_patch, compiler_error = compile_patch_intent(row, sources, text)
            if compiled_patch:
                patch = compiled_patch
                validation_error = None
            else:
                validation_error = compiler_error or validation_error
    else:
        patch, validation_error = compile_patch_intent(row, sources, text)
    preflight_error = None
    if patch and not validation_error:
        preflight_error = preflight_patch_apply(row, sources, patch)
    if validation_error or preflight_error:
        return "", validation_error, preflight_error
    return patch, None, None


def build_prompt(row: dict[str, Any], max_problem_chars: int, source_pack: str) -> str:
    problem = str(row.get("problem_statement") or "")[:max_problem_chars]
    fail_to_pass = list_from_jsonish(row.get("FAIL_TO_PASS"))
    hints = str(row.get("hints_text") or "").strip()
    return f"""Official SWE-bench Verified patch-generation slice.

This is prediction generation for the official SWE-bench harness.
It is not a public resolved score until the official Docker evaluator runs.

Instance id: {row.get('instance_id')}
Repository: {row.get('repo')}
Base commit: {row.get('base_commit')}
Version: {row.get('version')}
Fail-to-pass tests: {json.dumps(fail_to_pass)}

Problem statement:
{problem}

Hints:
{hints or 'none supplied'}

Base-commit source context:
{source_pack}

Output contract:
- Preferred: return a JSON patch intent with this exact shape:
  {{"changes":[{{"path":"relative/file.py","old":"exact base-source snippet","new":"replacement snippet"}}]}}
- The `old` snippet must be copied exactly from the supplied base-commit source.
- If you can emit a valid unified diff instead, that is allowed.
- No Markdown. No explanation.
- Do not echo the prompt or test text.
- If there is not enough source context to safely patch, return exactly:
# insufficient source context: unable to patch safely
"""


def build_direct_patch_prompt(row: dict[str, Any], max_problem_chars: int, source_pack: str, route: str) -> str:
    route_instruction = (
        "You are baseline Hermes in strict SWE patch mode. Use only the supplied problem and source context."
        if route == "baseline"
        else (
            "You are Tris architecture-on in strict SWE patch mode. Use the supplied problem and source context, "
            "keep evidence discipline, and output only the patch."
        )
    )
    return route_instruction + "\n\n" + build_prompt(row, max_problem_chars, source_pack)


def _strip_trailing_non_patch(text: str) -> str:
    cut_markers = ("\n```", "\nHunk count:", "\n# insufficient source context:", "\nThe patch", "\nExplanation:")
    end = len(text)
    for marker in cut_markers:
        position = text.find(marker)
        if position >= 0:
            end = min(end, position)
    return text[:end].strip()


def extract_patch(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    raw = raw.replace("<|im_start|>assistant", "").replace("<|im_end|>", "")
    fence = re.search(r"```(?:diff|patch)?\s*(.*?)```", raw, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    markers = ("diff --git ", "--- ", "Index: ")
    for marker in markers:
        idx = raw.find(marker)
        if idx >= 0:
            patch = _strip_trailing_non_patch(raw[idx:])
            if patch.startswith("--- "):
                lines = patch.splitlines()
                if len(lines) >= 2 and lines[0].startswith("--- a/") and lines[1].startswith("+++ b/"):
                    old_path = lines[0].split(None, 1)[1]
                    new_path = lines[1].split(None, 1)[1]
                    patch = "\n".join([f"diff --git {old_path} {new_path}", *lines])
            return patch.strip()
    if raw.startswith("# insufficient source context:"):
        return ""
    if "insufficient source context" in raw.lower():
        return ""
    return raw


def direct_patch_generate(route: str, prompt: str, timeout: float) -> dict[str, Any]:
    payload = {
        "prompt": prompt,
        "checkpoint": "hermes",
        "model": "hermes",
        "options": {
            "temperature": 0.0,
            "top_p": 0.9,
            "max_new_tokens": DIRECT_PATCH_MAX_NEW_TOKENS,
            "repetition_penalty": 1.08,
        },
    }
    request = Request(
        GFL_GENERATE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.time()
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "source": f"{route}-direct-patch",
            "runtime_lane": "gfl-hermes-direct-patch",
            "error": str(exc),
            "latency_ms": round((time.time() - started) * 1000),
        }
    text = str(data.get("response") or data.get("text") or "").strip()
    return {
        "ok": bool(text),
        "source": f"{route}-direct-patch",
        "runtime_lane": "gfl-hermes-direct-patch",
        "text": text,
        "latency_ms": round((time.time() - started) * 1000),
        "raw": data,
    }


def should_attempt_repair(raw_patch: str, validation_error: str | None, preflight_error: str | None) -> bool:
    if not raw_patch.strip() or not patch_file_paths(raw_patch):
        return False
    if preflight_error:
        return True
    if validation_error and validation_error.startswith("hunk count mismatch:"):
        return True
    return False


def run_route(
    route: str,
    row: dict[str, Any],
    prompt: str,
    sources: list[dict[str, str]],
    base_url: str,
    timeout: float,
    repair_timeout: float,
    repair_attempts: int,
) -> dict[str, Any]:
    if route in {"architecture_on", "baseline"}:
        result = direct_patch_generate(route, prompt, timeout)
    else:
        raise ValueError(f"Unknown route: {route}")
    raw_patch = normalize_unified_diff(extract_patch(result.get("text", "")))
    patch, patch_validation_error, patch_preflight_error = clean_patch_from_result(row, sources, result.get("text", ""))
    attempts: list[dict[str, Any]] = [
        {
            "attempt": 0,
            "ok": bool(result.get("ok")),
            "latency_ms": result.get("latency_ms"),
            "patch_chars": len(raw_patch),
            "patch_nonempty_after_checks": bool(patch),
            "validation_error": patch_validation_error,
            "preflight_error": patch_preflight_error,
        }
    ]
    current_raw_patch = raw_patch
    current_text = str(result.get("text", ""))
    for attempt in range(1, repair_attempts + 1):
        if patch:
            break
        if not should_attempt_repair(current_raw_patch, patch_validation_error, patch_preflight_error):
            break
        repair_prompt = build_repair_prompt(
            row,
            route,
            prompt,
            current_raw_patch,
            patch_validation_error,
            patch_preflight_error,
            sources,
        )
        repair_result = direct_patch_generate(f"{route}-repair{attempt}", repair_prompt, min(timeout, repair_timeout))
        current_text = str(repair_result.get("text", ""))
        current_raw_patch = normalize_unified_diff(extract_patch(current_text))
        patch, patch_validation_error, patch_preflight_error = clean_patch_from_result(row, sources, current_text)
        attempts.append(
            {
                "attempt": attempt,
                "ok": bool(repair_result.get("ok")),
                "latency_ms": repair_result.get("latency_ms"),
                "patch_chars": len(current_raw_patch),
                "patch_nonempty_after_checks": bool(patch),
                "validation_error": patch_validation_error,
                "preflight_error": patch_preflight_error,
            }
        )
    return {
        "route": route,
        "instance_id": row.get("instance_id"),
        "repo": row.get("repo"),
        "ok": bool(result.get("ok")),
        "source": result.get("source"),
        "runtime_lane": result.get("runtime_lane"),
        "latency_ms": result.get("latency_ms"),
        "raw_text": current_text,
        "model_patch": patch,
        "patch_nonempty": bool(patch.strip()),
        "patch_has_diff_marker": "diff --git " in patch or patch.startswith("--- "),
        "patch_validation_error": patch_validation_error,
        "patch_preflight_error": patch_preflight_error,
        "repair_attempts": attempts,
        "prompt_spill": bool(result.get("prompt_spill")),
        "raw_receipt_spill": bool(result.get("raw_receipt_spill")),
        "error": result.get("error"),
    }


def write_jsonl(path: Path, model_name: str, items: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for item in items:
            model_patch = item["model_patch"]
            if model_patch and not model_patch.endswith("\n"):
                model_patch += "\n"
            handle.write(
                json.dumps(
                    {
                        "instance_id": item["instance_id"],
                        "model_patch": model_patch,
                        "model_name_or_path": model_name,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


def write_outputs(payload: dict[str, Any]) -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = payload["id"]
    json_path = OUT_DIR / f"{run_id}.json"
    md_path = OUT_DIR / f"{run_id}.md"
    baseline_path = OUT_DIR / f"{run_id}_baseline_predictions.jsonl"
    tris_path = OUT_DIR / f"{run_id}_tris_predictions.jsonl"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    write_jsonl(baseline_path, "tris-baseline-hermes", payload["baseline"])
    write_jsonl(tris_path, "tris-architecture-on", payload["architecture_on"])

    lines = [
        f"# SWE-bench Verified Slice {run_id}",
        "",
        f"- Dataset: `{payload['dataset_name']}`",
        f"- Split: `{payload['split']}`",
        f"- Count: `{payload['count']}`",
        f"- Baseline predictions: `{baseline_path}`",
        f"- Tris predictions: `{tris_path}`",
        "",
        "## Boundary",
        "",
        payload["truth_boundary"],
        "",
        "## Rows",
        "",
        "| Route | Instance | Patch Nonempty | Diff Marker | Validation | Preflight | Error |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for route in ("baseline", "architecture_on"):
        for item in payload[route]:
            lines.append(
                f"| {route} | `{item['instance_id']}` | `{item['patch_nonempty']}` | "
                f"`{item['patch_has_diff_marker']}` | {item.get('patch_validation_error') or ''} | "
                f"{item.get('patch_preflight_error') or ''} | "
                f"{item.get('error') or ''} |"
            )
    lines.extend(
        [
            "",
            "## Evaluator Command Shape",
            "",
            "```bash",
            (
                ".venv-browser/bin/python -m swebench.harness.run_evaluation "
                "-d SWE-bench/SWE-bench_Verified -s test "
                f"-p {tris_path} -i INSTANCE_ID "
                "--max_workers 1 --timeout 900 --cache_level instance "
                "-id tris_swe_verified_slice"
            ),
            "```",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return {
        "json": str(json_path),
        "markdown": str(md_path),
        "baseline_predictions": str(baseline_path),
        "tris_predictions": str(tris_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate baseline and Tris SWE-bench Verified prediction slices.")
    parser.add_argument("--dataset-name", default="SWE-bench/SWE-bench_Verified")
    parser.add_argument("--split", default="test")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--base-url", default="http://127.0.0.1:8898")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--max-problem-chars", type=int, default=4500)
    parser.add_argument("--max-file-chars", type=int, default=7000)
    parser.add_argument("--repair-attempts", type=int, default=1)
    parser.add_argument("--repair-timeout", type=float, default=60.0)
    args = parser.parse_args()

    rows = load_rows(args.dataset_name, args.split, args.count, args.offset)
    baseline: list[dict[str, Any]] = []
    architecture: list[dict[str, Any]] = []
    source_receipts: list[dict[str, Any]] = []
    for row in rows:
        sources = fetch_source_pack(row, max_file_chars=args.max_file_chars)
        source_receipts.append(
            {
                "instance_id": row.get("instance_id"),
                "sources": [
                    {key: source[key] for key in ("path", "url", "truncated")}
                    for source in sources
                ],
            }
        )
        source_pack = format_source_pack(sources)
        baseline_prompt = build_direct_patch_prompt(row, args.max_problem_chars, source_pack, "baseline")
        architecture_prompt = build_direct_patch_prompt(row, args.max_problem_chars, source_pack, "architecture_on")
        baseline.append(
            run_route(
                "baseline",
                row,
                baseline_prompt,
                sources,
                args.base_url,
                args.timeout,
                args.repair_timeout,
                args.repair_attempts,
            )
        )
        architecture.append(
            run_route(
                "architecture_on",
                row,
                architecture_prompt,
                sources,
                args.base_url,
                args.timeout,
                args.repair_timeout,
                args.repair_attempts,
            )
        )

    payload = {
        "id": time.strftime("swebench_verified_slice_%Y%m%dT%H%M%SZ", time.gmtime()),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_name": args.dataset_name,
        "split": args.split,
        "offset": args.offset,
        "count": len(rows),
        "truth_boundary": (
            "This generates official-format SWE-bench prediction files for a small Verified slice. "
            "It is not a resolved SWE-bench score until the official Docker evaluator completes."
        ),
        "rows": [
            {
                "instance_id": row.get("instance_id"),
                "repo": row.get("repo"),
                "base_commit": row.get("base_commit"),
                "version": row.get("version"),
                "difficulty": row.get("difficulty"),
            }
            for row in rows
        ],
        "source_receipts": source_receipts,
        "baseline": baseline,
        "architecture_on": architecture,
    }
    paths = write_outputs(payload)
    print(json.dumps({"ok": True, "paths": paths, "count": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
