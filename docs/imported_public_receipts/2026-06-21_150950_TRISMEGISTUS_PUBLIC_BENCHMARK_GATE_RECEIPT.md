# Tris Public Benchmark Gate tris_public_benchmark_gate_20260621T150950Z

- Generated: `2026-06-21T15:09:44Z`
- Purpose: prepare baseline untuned model versus architecture-on Tris for public benchmarks and Tris-native evals.

## Gate Status

| Gate | Status | Public Score Ready | Next Gate |
| --- | --- | ---: | --- |
| SWE-bench Verified | `dataset_ready_harness_missing` | `False` | Install/stage the official SWE-bench harness, then run baseline and architecture-on on the same issue slice. |
| GAIA | `blocked_hf_access_or_dataset_gate` | `False` | Confirm gated dataset access, then run baseline and architecture-on on the same validation slice. |
| WebArena | `vendor_staged_runtime_missing` | `False` | Bring up official self-hosted WebArena domains/containers, then run bounded WebArena tasks with saved action traces. |
| Tris 100/500 coherence iterations | `ready` | `False` | Run 100 turns, patch failures, then scale to 500. This supports long-session coherence, not public benchmark replacement. |
| ANI15D / lattice companion custom eval | `objective_locked_task_bank_needed` | `False` | Build the six-discipline-lane task bank across AI partner/expert architecture, quantum computing / circuits and mathematics, structured matter/physical systems, life sciences/medical research, Mirror Architecture/Golden Mark evidence, and relationship/paid-work field operations. |
| Baseline untuned model route | `ready` | `True` | Use this as the no-Tris-router baseline whenever comparing against architecture-on Tris. |

## Benchmark Order

1. Run baseline untuned model route.
2. Run architecture-on Tris route.
3. Use the same task slice, same budget accounting, and saved receipts.
4. Compare task success, cost per task, source accuracy, long-session coherence, and repair quality.
5. Feed coding benchmark receipts into the future paid-work/coding-gig scouting lane.

## Commands

```bash
python scripts/run_public_benchmark_gates.py
python scripts/browser_cdp_smoke.py --url <local-tris-app-url>
python3 scripts/run_coherence_iters.py --backend baseline --count 100 --timeout 180
python3 scripts/run_coherence_iters.py --backend architecture_on --count 100 --timeout 180
python3 scripts/run_benchmark_compare.py --count 12 --timeout 180
```

## Boundary

This receipt checks readiness and locks the implementation path. It does not claim SWE-bench, GAIA, or WebArena scores until the official harness/task run completes.
