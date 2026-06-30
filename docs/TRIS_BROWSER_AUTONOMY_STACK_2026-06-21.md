# Trismegistus Browser Autonomy Stack

Date: 2026-06-21

## Decision

Use a combined browser/source stack:

1. Playwright as the primary browser-control engine.
2. CDP as the host-browser attachment bridge when Hermes/OpenClaw needs to
   connect to a normal local Chrome/Chromium instance.
3. Firecrawl as the fast RAG/source-ingestion sidecar.

## Why This Order

### 1. Playwright Primary

Playwright is the most robust local browser automation route for Tris because
it can:

- launch Chromium reliably
- click, type, inspect, wait, and recover
- capture screenshots and traces
- run visible or headless
- support BrowserGym and WebArena-style tasks
- produce saved action receipts

This is the route for WebArena, BrowserGym, visible browser tests, and future
OpenClaw browser worker tasks.

### 2. CDP Attachment Bridge

CDP is still important. It lets Tris/Hermes/OpenClaw attach to a browser that
is already running on the host machine through a debug port.

This is useful when:

- the operator wants to see the real browser
- a login/session already exists in a normal browser profile
- Hermes/OpenClaw needs a direct browser bridge
- we want visible local action traces without hiding everything in Docker

The preferred bridge is:

```text
host Chrome/Chromium with --remote-debugging-port=9222
-> Playwright connect_over_cdp
-> Tris/OpenClaw action loop
-> saved trace/receipt
```

### 3. Firecrawl Sidecar

Firecrawl is useful for fast page crawling, markdown extraction, source-pack
building, and RAG ingestion.

It should not be the main autonomy lane because it does not prove the agent can
operate a browser, recover from UI friction, click through tasks, or complete
WebArena-style sessions.

Use Firecrawl second, after Playwright/CDP are the action lane:

```text
FIRECRAWL_API_URL=http://localhost:3002
FIRECRAWL_API_KEY=local_development_key
```

## Combined Route

```text
User / Tris mission
-> classify: action task or source-ingest task
-> Playwright/CDP for browser action, screenshots, traces, and WebArena tasks
-> Firecrawl for fast public-source crawl / markdown / RAG source packs
-> Tris SQL / JSON / RAG memory
-> source/evidence labels
-> next mission or Codex build request
```

This combined route is the stack:

```text
Tris Browser Source Stack =
Playwright control
+ CDP host attachment
+ Firecrawl local crawl/RAG sidecar
+ WebArena/BrowserGym benchmark harness
+ Tris receipt memory
```

## Implementation Gates

1. Install Playwright and Chromium into the Tris browser environment. `done`
2. Add a visible Playwright smoke test. `done through CDP smoke`
3. Add a local CDP launcher and attachment smoke test. `done`
4. Save screenshot/trace receipts under `data/browser_autonomy`.
5. Connect Tris field missions to the browser worker lane.
6. Stage WebArena/BrowserGym official tasks.
7. Add Firecrawl local Docker only as the source-ingestion/RAG sidecar.

## Current Receipt

Passed smoke:

```text
data/browser_autonomy/tris_browser_cdp_smoke_20260621T052440Z.md
```

The smoke launched Google Chrome with CDP on port `9222`, attached with
Playwright, opened the local Tris surface at `http://127.0.0.1:8898/`, and
saved a screenshot receipt.

Live source sequence:

```text
data/browser_autonomy/tris_live_site_sequence_20260621T061650Z.md
```

That sequence used Playwright/CDP to visit:

- Quantinuum
- QuEra
- Quantum Machines
- IonQ
- D-Wave
- Nous Research careers
- Renaissance Field Lite public evidence stack

Result:

```text
7/7 targets loaded
```

Trace:

```text
data/browser_autonomy/tris_live_site_sequence_20260621T061650Z.zip
```

Screenshots:

```text
data/browser_autonomy/tris_live_site_sequence_20260621T061650Z/
```

WebArena baseline map:

```text
vendor/webarena/config_files/test.raw.json
vendor/webarena/run.py
vendor/webarena/evaluation_harness/evaluators.py
vendor/webarena/agent/prompts/raw
vendor/BrowserGym/browsergym/webarena
vendor/BrowserGym/browsergym/webarena_verified
```

Browser runtime:

```text
.venv-browser
```

Installed:

- Playwright
- Gymnasium
- BrowserGym core
- BrowserGym WebArena
- BrowserGym experiments

Official repos staged:

- `vendor/webarena`
- `vendor/BrowserGym`

## Truth Boundary

Playwright/CDP readiness means the browser control lane is available. It does
not mean WebArena has a public score until official WebArena tasks run with a
saved task-success receipt.

The live source sequence proves navigation and receipt capture. It is not
outreach, partnership proof, or a scored WebArena benchmark result.

## Chat / Telegram Intent Bridge

As of 2026-06-21, source/browser mission intent is wired into the normal Tris
surfaces:

```text
/api/chat
/api/source-fetch
```

Both routes call the same field-mission path. When the request asks for live
sites, live source, browser mission, Playwright/CDP, NVIDIA quantum partners,
Nous careers, RFL public stack, or WebArena baseline map, Tris runs the live
browser source sequence instead of improvising code in chat.

Patch points:

```text
trismegistus/trismegistus/source_tools.py
trismegistus/trismegistus/field_missions.py
trismegistus/trismegistus/browser_missions.py
```

Tight scoring correction:

```text
OK: False
Loaded: 6/7
```

now remains a partial source receipt instead of being promoted as a pass just
because the process returned `0`.

Latest chat receipt:

```text
data/field_missions/field_mission_20260621T065716Z091596.md
data/browser_autonomy/tris_live_site_sequence_20260621T065716Z.md
```

Latest Telegram/source bridge receipt:

```text
data/field_missions/field_mission_20260621T070136Z596649.md
data/browser_autonomy/tris_live_site_sequence_20260621T070136Z.md
data/browser_autonomy/tris_live_site_sequence_20260621T070136Z.zip
```

Both latest smoke tests loaded `7/7` targets.

## Next Gate

Promote the live-source browser receipts into Tris source/evidence rows with:

- source URL
- support label
- lane
- extracted claim
- extracted evidence
- boundary
- next gate

Then use those rows for relationship-draft missions with margin/profit scoring
and human approval before any outbound action.
