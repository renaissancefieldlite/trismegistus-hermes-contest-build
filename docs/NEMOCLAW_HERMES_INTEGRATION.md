# NemoClaw / Hermes Integration

Trismegistus does not mark NemoClaw or Hermes live until the local stack answers.

## Local probes

- CLI checks: `nemohermes`, `nemoclaw`.
- OpenShell check: `openshell sandbox exec -n trismegistus -- openclaw agents list --json`.
- Direct agent smoke: `openshell sandbox exec -n trismegistus -- openclaw agent --local --agent trismegistus --model ollama-direct/hf.co/nvidia/NVIDIA-Nemotron-3-Nano-4B-GGUF:Q4_K_M --json`.
- Dashboard check: `NEMOCLAW_DASHBOARD_URL`, default `http://127.0.0.1:18789`.
- OpenAI-compatible model check: `NEMOCLAW_OPENAI_BASE_URL`, default `http://127.0.0.1:8642/v1`.
- Chat completion: `HERMES_BASE_URL`, default `http://127.0.0.1:8642/v1/chat/completions`.

## Active route

The wrapper command can report a stale local registry even when the OpenShell sandbox is
ready. The app therefore treats the lower-level OpenShell/OpenClaw path as the controlling
receipt:

```text
openshell sandbox exec -n trismegistus -- openclaw agent --local --agent trismegistus ...
```

The named `trismegistus` OpenClaw agent must exist and return JSON with `agentMeta`,
`provider`, `model`, and `sessionFile` before the UI calls the route live.

## Demo behavior

If OpenClaw responds through the sandbox, Trismegistus uses it for chat and worker packets.

If OpenClaw does not respond, Trismegistus writes the route error into the run packet. Worker
autonomy is not marked ready.

Stripe stays draft-only until a separate Stripe sandbox/live receipt exists.
