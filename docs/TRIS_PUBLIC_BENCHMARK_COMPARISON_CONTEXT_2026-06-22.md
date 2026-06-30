# Trismegistus Public Benchmark Comparison Context

Generated: 2026-06-22 UTC

Purpose: give Tris a public comparison layer for benchmark framing without
mixing local receipts with official leaderboard claims.

## Public-safe claim boundary

Trismegistus has local baseline-vs-architecture-on receipts and bounded
WebArena subset action receipts. It does not yet have official SWE-bench,
GAIA, or full WebArena leaderboard scores.

Use this document as comparison context only until the official harnesses run.

## Current Tris receipts

- Internal six-lane matched slice:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/eval_runs/golden_mark_udp_compare_20260622T072725Z.md`
  - Baseline mean: `0.826`
  - Tris architecture-on mean: `0.99`
  - Delta: `+0.163`
- Captured live-browser source compare:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/eval_runs/live_browser_compare_20260622T072105Z.md`
  - Baseline mean: `0.987`
  - Tris architecture-on mean: `1.0`
  - Delta: `+0.013`
- Bounded official WebArena homepage subset action receipt:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/browser_autonomy/tris_browser_action_trace_20260622T175236Z.md`
  - Action: homepage -> calculator -> expression `67+5`
  - Expected: `72`
  - Observed: `72`
- Bounded WebArena receipt comparison:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/eval_runs/webarena_action_compare_20260622T181324Z.md`
  - Baseline score: `1.0`
  - Tris architecture-on score: `1.0`
  - Delta: `0.0`

## Official benchmark context to compare against

### SWE-bench

Why it matters: public coding/self-improvement credibility. It measures whether
a system can resolve real software issues. The official leaderboard reports
`% Resolved`; SWE-bench Verified is a human-filtered `500`-instance subset.

Tris gate:

- Dataset access: ready.
- Official harness: staged in `.venv-browser` with `swebench==4.1.0`.
- First small Verified prediction slice:
  `/Users/renaissancefieldlite1.0/Documents/Playground/trismegistus/data/swebench/swebench_verified_slice_20260622T182931Z.md`
- Official evaluator status:
  invoked on `astropy__astropy-12907`, but local scoring did not complete
  because the x86_64 environment image build failed with exit code `137` on
  the current `colima-tris` profile.
- Next gate: rerun on a larger Colima/x86-capable environment or Modal/remote
  runner, then compare baseline Hermes route and Tris architecture-on route on
  the same small Verified slice before scaling.

Source:

- https://www.swebench.com/

### WebArena

Why it matters: public autonomous web action credibility. WebArena evaluates
long-horizon tasks in realistic websites across e-commerce, social/forum,
collaborative development, content management, maps, and knowledge tools.

Reference anchor:

- WebArena paper reports its best GPT-4-based agent at `14.41%` end-to-end
  success versus human performance at `78.24%`.

Tris gate:

- Browser runtime: ready.
- Official self-hosted sites/domains: pending.
- Bounded subset: homepage + calculator action receipt is working.
- Next gate: stage official domains/containers or a bounded official subset,
  then run matched baseline vs Tris action receipts.

Sources:

- https://arxiv.org/abs/2307.13854
- https://webarena.dev/

### GAIA

Why it matters: public general-assistant credibility across reasoning,
multimodality, web browsing, and tool use.

Reference anchor:

- GAIA paper reports humans at `92%` versus GPT-4 with plugins at `15%`, and
  describes `466` questions with held-out answers powering a leaderboard.

Tris gate:

- Current local check: blocked at Hugging Face access / dataset gate.
- Next gate: confirm accessible split/token, then run baseline and
  architecture-on on the same small validation slice.

Sources:

- https://arxiv.org/abs/2311.12983
- https://huggingface.co/gaia-benchmark

## Nous / Hermes comparison context

### Hermes 4.3 36B

Why it matters: this is the cleanest current Nous/Hermes model-card comparison
surface for Tris framing.

Useful public numbers from the model card:

- RefusalBench questions answered:
  - Hermes 4.3 36B Non-Reasoning: `74.60%`
  - Hermes 4.3 36B Reasoning: `72.29%`
- Benchmarks:
  - AIME 24: `71.9`
  - AIME 25: `69.3`
  - BBH: `86.4`
  - GPQA Diamond: `65.5`
  - MATH-500: `93.8`
  - MMLU: `87.7`
  - MMLU-Pro: `80.7`

How to use this:

- Compare Tris against Hermes baseline only when the same task and same runtime
  route are used.
- Use Hermes public numbers to show the ecosystem we are building beside, not
  as a substitute for our own receipts.

Source:

- https://huggingface.co/NousResearch/Hermes-4.3-36B

## NVIDIA / Nemotron comparison context

### NVIDIA Nemotron 3 Ultra

Why it matters: NVIDIA’s own public framing matches the Tris target: long-running
agent workflows, tool use, code/research tasks, cost per task, OpenShell,
NemoClaw, OpenClaw, and Hermes Agent support.

Useful public numbers from the NVIDIA model card:

- Parameters: `550B` total / `55B` active.
- Context length: up to `1M` tokens.
- SWE-bench Verified:
  - BF16: `71.9`
  - NVFP4: `69.7`
- SWE-bench Multilingual:
  - BF16: `67.7`
  - NVFP4: `65.8`
- Terminal Bench 2.1:
  - BF16: `56.4`
  - NVFP4: `53.9`
- PinchBench:
  - BF16: `90`
  - NVFP4: `89.8`
- RULER 1M:
  - BF16: `94.7`
  - NVFP4: `94.0`

Useful public framing from the NVIDIA blog:

- Nemotron 3 Ultra is positioned for long-running agents where context, tool
  calls, sub-agents, reasoning, and cost discipline matter.
- NVIDIA reports up to `30%` lower cost to complete SWE-bench Verified
  benchmark tasks through fewer total tokens / fewer tokens per turn.
- NVIDIA states Hermes Agent is officially available and supported with
  Nemotron, and identifies OpenShell + NemoClaw + OpenClaw as the secure
  runtime/blueprint stack for safer always-on autonomous systems.

How to use this:

- Treat Nemotron as an external frontier comparison and possible future runtime,
  not as a Tris score.
- Track Tris cost per task, tokens per task, task success, source accuracy,
  long-session coherence, and repair quality so our receipts can sit beside
  NVIDIA’s public framing.

Sources:

- https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard
- https://developer.nvidia.com/blog/nvidia-nemotron-3-ultra-powers-faster-more-efficient-reasoning-for-long-running-agents/

## Benchmark narrative for the next demo

Public-safe line:

Trismegistus is being evaluated as an AI Partner / Expert Architecture across
internal six-lane coherence, captured-source browsing, bounded WebArena action
receipts, and then official SWE-bench, GAIA, and WebArena runs. Local receipts
show architecture-on improvements on our current task banks. Public benchmark
numbers from SWE-bench, GAIA, WebArena, Nous/Hermes, and NVIDIA/Nemotron define
the comparison sea we are steering into next.

## Next clean gate

1. Stage full official WebArena domains/containers or a bounded official subset.
2. Run matched baseline vs Tris on the same WebArena tasks with action traces.
3. Stage official SWE-bench harness and run a small Verified slice.
4. Resolve GAIA Hugging Face access and run a small validation slice.
5. Add a comparison dashboard with local receipt scores, public benchmark
   references, cost per task, tokens per task, and next-gate status.
