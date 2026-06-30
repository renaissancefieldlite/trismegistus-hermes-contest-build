# Trismegistus Public Benchmark And ANI15D Eval Spine

Date: 2026-06-21

## Purpose

Trismegistus needs two scoreboards that work together:

1. Public benchmark credibility: accepted agent and coding benchmarks that other
   teams recognize.
2. Tris-native cognition growth: the architecture-on / lattice-companion /
   ANI15D / Golden Mark lanes that measure the part of the system normal agent
   benchmarks do not see.

The tuning objective is not just a higher chat score. The objective is a field
expert operator that can code, research, keep long-session coherence, use
sources, explain its own route, and convert proven capability into real work
opportunities.

## Public Benchmark Targets

### SWE-bench / SWE-bench Verified

Official source:

- https://www.swebench.com/
- https://github.com/SWE-bench/SWE-bench

Use for coding, repo repair, patch generation, and self-improvement evidence.

Primary metrics:

- resolved task rate / pass rate
- patch applies
- tests pass
- cost per issue
- time per issue
- trace quality: issue read, file inspection, patch, test, receipt

Tris read:

This is the clearest public lane for "the agent can improve software." When
Tris earns real coding benchmark receipts, those receipts can also become a
paid-work scouting credential for coding gigs and repo-repair services.

### GAIA

Official source:

- https://huggingface.co/datasets/gaia-benchmark/GAIA

Use for real-world assistant tasks that require tool use, source handling,
reasoning, and sometimes multimodal interpretation.

Primary metrics:

- exact answer / task success
- source accuracy
- tool trace completeness
- cost per task
- failure category
- clarification discipline

Tris read:

This tests whether Tris behaves like an operating research partner instead of
only a local chat shell.

### WebArena

Official source:

- https://webarena.dev/
- https://github.com/web-arena-x/webarena
- https://github.com/ServiceNow/BrowserGym

Use for autonomous web/browser action tasks.

Primary metrics:

- task success rate
- browser action count
- recovery from navigation errors
- cost per session
- receipt quality
- no fake completion claims

Tris read:

This is the outside web-action lane. It matches the OpenClaw / NemoClaw vision:
free-roaming agent work with bounded receipts.

Browser stack decision:

- Playwright is the primary browser-control engine.
- CDP is the host-browser attachment bridge for a normal local Chrome/Chromium
  session.
- BrowserGym/WebArena is the benchmark harness layer.
- Firecrawl is the fast source/RAG ingestion sidecar, not the main autonomous
  browser lane.

Combined stack:

```text
Playwright action + CDP host attachment + Firecrawl source ingestion +
BrowserGym/WebArena tasks + Tris SQL/JSON/RAG receipts
```

## Tris-Native Eval Targets

### 100 / 500 Turn Coherence Iterations

Use for long-session stability and natural partner behavior.

Metrics:

- presence coherence
- prompt/receipt spill rate
- cross-thread recall
- source/RAG routing
- clarification instead of guessing
- mission continuity
- tone fit: conversational first, audit behind the veil

### Golden Mark / C5B / SSP Architecture-On Comparison

Use for architecture-on versus architecture-off measurement.

Metrics:

- context retention
- evidence recall
- state-path stability
- drift reduction
- reasoning lane consistency
- support label accuracy

### ANI15D / Lattice Companion Cross-Field Eval

Use for what makes Tris different: companion mapping and universal-pattern
recognition across fields.

The eval should test whether Tris can identify the same state/control/drift/
alignment pattern across the six discipline partner lanes:

- AI partner / expert architecture
- quantum computing / circuits and mathematics
- structured matter / physical systems
- life sciences / medical research
- Mirror Architecture / Golden Mark evidence methods
- relationship / paid-work field operations

Metrics:

- cross-domain pattern recognition
- field-lane routing accuracy
- support label discipline
- next experiment proposal quality
- public-safe explanation quality
- ability to turn a source pack into a mission queue

## Tuning Objective

Add the public benchmark suite at the end of the tuning ladder once the local
route is stable:

1. Baseline untuned Hermes / model route.
2. Tris architecture-on route.
3. Same public benchmark slice.
4. Same custom ANI15D / lattice / Golden Mark eval slice.
5. Compare task success, long-session coherence, cost per session, source
   accuracy, and coding repair credibility.

The goal is to show measurable improvement against baseline while keeping the
process honest: no fake autonomy, no fake benchmark scores, no fake outbound
actions.

## Current Gate

Public benchmark harness readiness is a gate, not a claim.

The immediate command is:

```bash
.venv-browser/bin/python scripts/run_public_benchmark_gates.py
```

That command checks what can run now, what needs access, and what needs the
official benchmark harness installed before a public score can be claimed.

## Current Receipt

As of 2026-06-21:

- Browser runtime venv exists at `.venv-browser`.
- Playwright, Gymnasium, BrowserGym core, BrowserGym WebArena, and BrowserGym
  experiments are installed in that venv.
- Official WebArena repo is staged at `vendor/webarena`.
- Official BrowserGym repo is staged at `vendor/BrowserGym`.
- CDP smoke passed:
  `data/browser_autonomy/tris_browser_cdp_smoke_20260621T052440Z.md`.
- Latest benchmark gate:
  `data/benchmark_gates/tris_public_benchmark_gate_20260621T052755Z.md`.

Current read:

- Baseline untuned route: ready.
- Tris 100/500 coherence route: ready.
- SWE-bench Verified dataset: accessible; official harness still needed.
- GAIA: gated on Hugging Face access/token.
- WebArena: browser runtime ready; self-hosted WebArena sites/domains still
  need to be brought up before a task-success score can be claimed.
- ANI15D / lattice companion eval: objective locked; task bank still needs to
  be generated.

## WebArena Baseline Locations

Official local WebArena baseline files staged under Tris:

- raw task source:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/webarena/config_files/test.raw.json`
- generated task config folder:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/webarena/config_files`
- benchmark runner:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/webarena/run.py`
- environment URL gate:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/webarena/browser_env/env_config.py`
- evaluator harness:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/webarena/evaluation_harness/evaluators.py`
- official prompt baselines:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/webarena/agent/prompts/raw`
- BrowserGym WebArena wrapper:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/BrowserGym/browsergym/webarena`
- BrowserGym WebArena Verified wrapper:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/vendor/BrowserGym/browsergym/webarena_verified`

Current live source sequence receipt:

```text
/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/browser_autonomy/tris_live_site_sequence_20260621T061650Z.md
```

This receipt loaded `7/7` public source targets and records the WebArena
baseline map. It is source-intake proof, not a scored WebArena result.

## Small Same-Task Baseline Slice

Command:

```bash
python3 scripts/run_benchmark_compare.py --count 4 --timeout 180
```

Receipt:

```text
/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/coherence_iters/tris_baseline_compare_20260621T070307Z.md
```

Runs:

```text
/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/coherence_iters/tris_coherence_iter_20260621T070241Z.md
/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/coherence_iters/tris_coherence_iter_20260621T070307Z.md
```

Read:

- baseline Hermes/GFL mean: `0.75`
- architecture-on Tris mean: `1.0`
- delta: `+0.25`
- prompt spills: `0`
- raw receipt spills: `0`

Interpretation:

The early architecture-on route is already improving the exact surface the
operator was testing: presence, 123 coherence probes, identity, and coherent
research/business-partner framing. This is a small internal same-task score
slice. It supports continued iteration and visible demo capture; it is not a
public SWE-bench, GAIA, or full WebArena score.

## Next Implementation Gate

1. Run the benchmark gate receipt.
2. Stage official SWE-bench harness path.
3. Stage GAIA access path after Hugging Face access is confirmed.
4. Stage WebArena/browser environment path.
5. Keep running 100/500 Tris-native coherence iterations while official public
   benchmark harnesses are prepared.
6. Use coding benchmark receipts as part of the future paid-work/coding-gig
   scouting lane.
