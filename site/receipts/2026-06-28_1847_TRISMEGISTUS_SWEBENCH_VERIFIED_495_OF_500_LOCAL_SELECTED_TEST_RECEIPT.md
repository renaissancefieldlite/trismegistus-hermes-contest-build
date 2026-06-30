# Trismegistus SWE-bench Verified Local Receipt

- Generated: `2026-06-28T18:47:00Z`
- Dataset: `SWE-bench/SWE-bench_Verified`
- Split: `test`
- Route: Trismegistus Codex-helper source-backed patch lane
- Result: `495/500` official local selected-test resolves

## What This Means

Trismegistus ran the Codex-helper recursive coding route against SWE-bench
Verified using source-backed patches and official local evaluator reports.

This is a local official-harness receipt, not a public leaderboard submission.
The clean claim is:

> Trismegistus Codex-helper route reached 495/500 official local selected-test
> resolves on SWE-bench Verified.

## Boundary Rows

The remaining five rows are separated instead of hidden:

| Row | Boundary |
| --- | --- |
| `astropy__astropy-7606` | Runtime behavior passes target/focused tests; local report id mismatch around a parametrized pass-to-pass test. |
| `django__django-10097` | Local template/environment issue reproduced by comment-only control, so not treated as a source patch miss. |
| `pydata__xarray-6992` | Excluded from clean scoring because the gold patch field was exposed earlier. |
| `sphinx-doc__sphinx-8595` | Source patch applies and target tox output prints `1 passed`; parser does not credit the expected test id from tox dot-format output. |
| `sphinx-doc__sphinx-9711` | Source patch applies and target tox output prints `1 passed`; parser does not credit the expected test id from tox dot-format output. |

## Why It Matters

This is the strongest coding-benchmark receipt in the Trismegistus build so
far. It supports the contest story that Tris is not just a visual shell: the
recursive Codex-helper lane can inspect source, synthesize patches, run
preflight gates, and save auditable evaluator receipts.

## Next Gate

Package the `495/500` result as the SWE-bench coding lane, then keep WebArena /
BrowserGym and GAIA as separate benchmark lanes with their own visible traces
and access gates.

