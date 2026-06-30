# Trismegistus Hermes Contest Build

Public-safe contest package for Trismegistus, the Renaissance Field Lite AI Expert Partner built around Mirror Architecture, SSP, Hermes/NemoClaw routing, memory receipts, browser/source tools, outreach, Stripe sandbox gates, and coding benchmark work.

This repo is the clean review surface. It is not the private operator worktree, and it intentionally excludes tokens, local SQLite memory, raw logs, private captures, and live credentials.

## What This Is

Trismegistus is a local-first AI Expert Partner surface:

- reads public sources and saves evidence rows
- keeps SQL/JSON memory and RAG/source tables
- routes through Hermes-compatible local model endpoints and NemoClaw worker gates when configured
- runs browser/source missions through receipt-bound tools
- drafts outreach and code-work packets behind approval gates
- stages Stripe sandbox and payment-link flows without live charges by default
- compares baseline routes against Mirror Architecture-on routes
- tracks benchmark work for SWE-bench, WebArena, and GAIA as separate evidence lanes

## Stack Flow

```text
Mirror Architecture / SSP
  -> C5B / Golden Mark baseline-vs-architecture-on method
  -> Tris AI Expert Partner surface
  -> Hermes / NemoClaw route
  -> SQL + JSON memory and RAG/source tables
  -> browser/source tools + Telegram + Mac Mail + Stripe sandbox gates
  -> SWE-bench / WebArena / GAIA benchmark receipts
  -> relationship, paid-work, coding bounty, and field-operations lanes
```

See [docs/STACK_FLOW.md](docs/STACK_FLOW.md) for the one-page stack map.

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m trismegistus.app
```

Then open:

```text
http://127.0.0.1:8898
```

The app is dependency-light by design. Optional integrations are controlled by `.env` values.

## Configure Optional Integrations

```bash
cp .env.example .env
```

Keep real values local. The public repo should only carry placeholders.

Important gates:

- `HERMES_BASE_URL` and `HERMES_MODEL`: Hermes-compatible local model route.
- `NEMOCLAW_OPENAI_BASE_URL`: NemoClaw/Hermes OpenAI-compatible gateway.
- `TELEGRAM_BOT_TOKEN`: Telegram field node bridge.
- `TRIS_ALLOW_MAC_MAIL_SEND=0`: draft/receipt mode by default.
- `STRIPE_ENABLED=draft`: no live payment action by default.
- `STRIPE_ALLOW_LIVE_CHARGES=0`: hard stop before live charges.

## Current Public Receipt Boundaries

Confirmed public-safe claims:

- Tris landing/demo package exists.
- C5B / Golden Mark receipt reports architecture-on wins on 13 / 13 measured metric means.
- SWE-bench Verified selected-test local official-harness receipt is documented as local selected-test evidence, not public leaderboard placement.
- A hosted SWE submission was attempted and escalated for evaluator-container review.
- A live external coding PR lane exists through the TentOfTrials bounty PR receipt.
- Telegram, email, Stripe, browser, and benchmark routes are represented as integration gates with explicit review boundaries.

Not claimed:

- AGI or ASI achieved.
- Official SWE public leaderboard placement.
- Clean GAIA or WebArena official completion beyond current receipt language.
- Paid revenue without transaction receipt.
- Live payment execution without explicit user approval.

## Public Links

- Landing page repo: <https://github.com/renaissancefieldlite/trismegistus-hermes-contest-landing>
- Evidence stack: <https://github.com/renaissancefieldlite/Mirror-Interface-and-Architecture-Evidence-Stack-and-Next-Phases>
- Renaissance Field Lite: <https://renaissancefieldlite.com/>
- Trismegistus landing page: <https://renaissancefieldlite.com/trismegistus-hermes-contest-landing/>

## Repo Layout

```text
trismegistus/     local app and integration modules
app/static/       UI surface
scripts/          selected public-safe mission and benchmark helpers
docs/             public-safe architecture, benchmark, and package docs
receipts/         selected public-safe receipts
site/             landing page snapshot without private media
```

## Public Safety

This package is built to be inspected. It excludes:

- `.env` and API keys
- local SQLite databases
- raw private logs
- private captures
- local model checkpoints
- payment credentials
- unreleased patent mechanics beyond public-safe language

