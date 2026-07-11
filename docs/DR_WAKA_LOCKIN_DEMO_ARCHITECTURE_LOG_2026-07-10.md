# Dr. Waka Lock-In Demo Architecture Log

Date: 2026-07-10

## Core Correction

The hosted Trismegistus demo must not behave like a curated answer board. It
must behave like a general AI partner first:

1. User asks any question.
2. The live model route answers the question.
3. SQL, JSON, RAG, source docs, evidence rows, and receipts operate as auxiliary
   memory/context, similar to an operator-side Codex support layer.
4. Proof/source/audit mode opens only when the user asks for proof, sources,
   receipts, benchmark support, or a specific external source action.
5. No fake completion language: worker, browser, outreach, payment, benchmark,
   and source actions require matching receipts.

## Failure Pattern Found

The hosted app had too much deterministic branching:

- project phrases could be intercepted by source/doctrine handlers;
- fallback copy could describe Tris instead of letting a model reason;
- weak model fallback could make the demo look alive while not meeting the
  professional field-expert bar;
- status copy could imply empty memory even after SQL/RAG rows were indexed.

That pattern is not acceptable for the Trismegistus product. It makes RAG act as
the brain instead of the support layer.

## Current Hermes Demo Patch Direction

- Route ordinary chat through `tris_turn_pipeline.run_turn`.
- Gather SQL/JSON/RAG/source docs into context before generation.
- Remove the pre-pipeline deterministic source-mission bypass from chat.
- Run explicit source missions only for real external source actions such as
  URLs, domains, fetch/read/open/crawl/search/current/latest requests.
- Keep turn receipts for every model turn.
- Do not use Qwen as the Hermes Tris default. It can fit a tiny host but it is
  the wrong model family for this product route.
- Low-quant Hermes-3 IQ2 can load in local Docker, but cold/project turns were
  too slow or unstable for a reliable small-host public click demo.
- Therefore the real hosted demo gate is either a Hermes/OpenAI-compatible
  provider secret on Render or a larger host class that proves Hermes-3 Q4 or
  Nemotron end-to-end with `/api/chat`.
- Expose real RAG counts in `/api/status`.

## ACT II Patch Target

Port the same architecture into ACT II:

- model-first general chat;
- memory/RAG as auxiliary context;
- source/browser actions only when explicitly requested;
- receipt mode only when asked for proof/audit/benchmark/source support;
- no canned fallback pretending to be intelligence;
- no local-only or Ollama fallback language on the AMD public demo;
- benchmark lanes separated by receipt: baseline, architecture-on,
  memory/RAG, novel output, and next-gate receipts.

## Acceptance Smoke

Before public handoff, test:

- arbitrary chat: "explain photosynthesis to a smart high school student";
- project context: "what is Trismegistus supposed to do";
- source/RAG: "tell me about Source Mirror Pattern";
- benchmark: "what is proven for C5B or SWE-bench";
- boundary: "what is not proven live on Render";
- external source action: "read https://example.com and summarize it";
- receipt check: verify a turn receipt is saved and `/api/status` reports
  nonzero RAG memory rows.
