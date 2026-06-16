# Starling memory plugin for OpenClaw

Make Starling the long-term memory behind an OpenClaw agent. The plugin claims
OpenClaw's `plugins.slots.memory` slot and routes every memory operation to a
Starling dashboard over HTTP. It is a thin TypeScript client — the cognitive
memory (statements / consolidation / retrieval) stays in the Starling C++/Python
backend.

> **Just want to use it (not set it up)?** See **[USAGE.md](USAGE.md)** — an
> end-user guide (what your agent can do, how to store / recall / forget, FAQ,
> holder/tenant config). This README is the setup + integration reference.

| OpenClaw capability | Plugin wiring | Starling dashboard API |
| --- | --- | --- |
| `memory_search` (builtin tool) | `registerMemoryCapability` → `runtime.search` | `POST /api/recall` |
| `memory_get` (builtin tool) | `registerMemoryCapability` → `runtime.readFile` | `GET /api/statement/{id}` |
| reindex | `registerMemoryCapability` → `runtime.sync` | `POST /api/tick` (or no-op) |
| auto-recall (context inject) | `before_prompt_build` hook | `GET /api/working_set` |
| `memory_store` (write tool) | `registerTool` | `POST /api/remember` |
| `memory_forget` (delete tool) | `registerTool` | `POST /api/forget` (→ forgotten) |
| auto-capture (pre-compaction) | `registerMemoryFlushPlan` + `before_compaction` | `POST /api/remember` |

---

## Architecture — why the dashboard runs on the host

```
┌─ host (macOS/Linux) ────────────────────────┐        ┌─ docker container ─────────────┐
│ Starling dashboard (FastAPI + uvicorn)      │  HTTP  │ OpenClaw 2026.6.6              │
│   loads native _core.so                     │◀───────│   + @starling/openclaw-memory  │
│   bind 0.0.0.0:8787  (Bearer-token auth)    │ host.  │   plugins.slots.memory=starling│
│   ~/.starling/{starling.json, dashboard.db} │docker. │   → host.docker.internal:<port>│
└─────────────────────────────────────────────┘internal└────────────────────────────────┘
```

On **macOS** the Starling engine `_core.so` is a Mach-O (arm64) binary that
**cannot load inside a Linux container**, so the dashboard runs on the host and
OpenClaw runs in the container, reaching the host via `host.docker.internal`.
(On Linux you *could* run both in containers, but this guide keeps the host
topology so it works everywhere.)

---

## Prerequisites

1. **Starling built on the host.** From the repo root, the venv exists and
   `_core.so` is compiled:
   ```bash
   .venv/bin/python -c "from starling import _core; print('ok')"   # → ok
   ```
   If not, build it: `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python scripts/configure_build.py --build --build-dir build --python-editable`.

2. **An embedder configured** in `~/.starling/starling.json` (the `embedder`
   block with an `api_key`). **This is required for semantic recall** — without
   it the dashboard falls back to an 8-dim stub embedder whose cosine scores are
   not meaningful, so `memory_search` will return rows but not in useful order.
   The dashboard reads `llm` (for capture/extraction) + `embedder` + `token`
   from this file. `GET /api/config` never returns the secrets.

3. **Docker** running (`docker info` succeeds).

4. **Node 18+** on the host only if you want to run the unit tests / rebuild the
   plugin locally (the container builds it itself).

---

## Quick start (docker integration, 5 steps)

All host commands run from the **repo root** unless noted. `cd integrations/openclaw`
where stated.

### Step 1 — Start the Starling dashboard on the host

Bind `0.0.0.0` so the container can reach it (`127.0.0.1` is not reachable from
inside docker). Use a throwaway DB + spare port so you don't touch your real
dashboard, and a short tick interval so captured memories embed quickly:

```bash
STARLING_DASH_HOST=0.0.0.0 \
STARLING_DASH_PORT=8799 \
STARLING_DASH_DB=/tmp/starling-openclaw.db \
STARLING_DASH_TENANT=openclaw \
STARLING_DASH_TICK_INTERVAL=5 \
  .venv/bin/python scripts/run_dashboard.py --no-build
# → "Dashboard ready → http://127.0.0.1:8799/#token=<token>"
```

- `--no-build` skips the SvelteKit UI build (the plugin only needs the JSON API).
- `STARLING_DASH_TICK_INTERVAL=5` runs the background maintenance tick every 5s,
  which embeds + consolidates freshly-captured statements so they become
  searchable. (Default is 30s; see the "capture → search timing" note below.)
- Leave this running in its own terminal.

### Step 2 — Export the dashboard token

The plugin authenticates with the dashboard's Bearer token (stored in
`~/.starling/starling.json`). It is **never** baked into the image or git:

```bash
export STARLING_TOKEN=$(python3 -c \
  "import json,os;print(json.load(open(os.path.expanduser('~/.starling/starling.json')))['token'])")
echo "${STARLING_TOKEN:0:6}…"   # sanity: non-empty
```

### Step 3 — Build + start the OpenClaw container

```bash
cd integrations/openclaw
STARLING_TOKEN=$STARLING_TOKEN STARLING_PORT=8799 \
  docker compose -f docker/docker-compose.yml up --build -d
```

This builds an image (node:22-slim + `openclaw@2026.6.6` + the plugin compiled
inside the image), renders the OpenClaw config from env at runtime, and keeps
the container alive for `docker compose exec`. Only `STARLING_TOKEN` is required;
the rest have defaults (see [Configuration](#configuration)).

### Step 4 — Verify the plugin loaded + claimed the memory slot

```bash
docker compose -f docker/docker-compose.yml exec openclaw \
  openclaw plugins inspect starling
# → Status: loaded ;  slot: memory ;  status {"backend":"qmd","provider":"starling"}
```

If it says "Config path not found" or the plugin is missing, see
[Troubleshooting](#troubleshooting) (almost always `OPENCLAW_CONFIG_PATH`).

### Step 5 — End-to-end: capture → tick → recall

Run the in-container round-trip (it imports the exact compiled `dist/*.js`
OpenClaw loads, and drives `status → remember → sync(tick) → recall` against the
host dashboard):

```bash
docker compose -f docker/docker-compose.yml exec openclaw \
  node /opt/starling-plugin/roundtrip.mjs
```

Then confirm on the host that the memory landed and is searchable:

```bash
# what got written (note the statement id + holder):
curl -s "http://127.0.0.1:8799/api/statements?limit=10" \
  -H "Authorization: Bearer $STARLING_TOKEN" | python3 -m json.tool

# search it back — IMPORTANT: pass the SAME holder the plugin captures under
# (STARLING_HOLDER, default "agent"), else the holder dimension excludes it:
curl -s -X POST "http://127.0.0.1:8799/api/recall" \
  -H "Authorization: Bearer $STARLING_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"<words from what you stored>","k":5,"holder":"agent"}' \
  | python3 -m json.tool
# → {"results":[{"id":"…","subject":"…","predicate":"…","object":"…","score":…}]}
```

The plugin's own `memory_search` already passes `holder=cfg.holder` for you — the
explicit `"holder":"agent"` above is only because you're calling `/api/recall`
by hand. When done: `docker compose -f docker/docker-compose.yml down -v`.

> **Automated version of steps 3-5:** `STARLING_TOKEN=$STARLING_TOKEN STARLING_PORT=8799 ./docker/integration-test.sh`
> runs the build, plugin-load check, round-trip, and the offline degradation +
> retry-queue test in one shot. See [`docker/README.md`](docker/README.md).

---

## Configuration

Container env (compose passes these into `entrypoint.sh`, which renders
`openclaw.json` at runtime — the token is never written to an image layer):

| Var | Default | Purpose |
| --- | --- | --- |
| `STARLING_TOKEN` | — (**required**) | Dashboard Bearer token (from `~/.starling/starling.json`) |
| `STARLING_PORT` | `8787` | Host dashboard port (`host.docker.internal:<port>`) |
| `STARLING_TENANT` | `openclaw` | Tenant for the synthetic `statement://<tenant>/<id>` paths |
| `STARLING_HOLDER` | `agent` | **Holder identity** used for both capture *and* recall (see below) |
| `STARLING_AUTO_RECALL` | `true` | `before_prompt_build` injects the working set as context |
| `STARLING_AUTO_CAPTURE` | `true` | `before_compaction` persists the latest user message |

The plugin's own `configSchema` (`openclaw.plugin.json`) fields are
`dashboardUrl`, `token`, `tenant`, `holder`, `autoCapture`, `autoRecall`;
`dashboardUrl` + `token` are required. In the container these are derived from
the env above.

---

## Key concepts and must-read gotchas

- **Holder dimension must round-trip (the big one).** Starling scopes memory by
  `holder` (who the belief belongs to). The plugin captures under `cfg.holder`
  (`STARLING_HOLDER`, default `"agent"`) **and** recalls under the same holder,
  so it is self-consistent out of the box. The dashboard's own `agent` setting
  (in `starling.json`, default `"self"`) does **not** have to match — the plugin
  passes its holder explicitly on both sides. If you call `/api/recall` by hand,
  you must pass `"holder":"agent"` or you'll get empty results for plugin-written
  memories. (This was the P3.b2 "writes land but search is empty" bug — fixed by
  adding a `holder` override to `/api/recall` + `/api/working_set`.)

- **An embedder is required for useful recall.** `memory_search` → `/api/recall`
  is semantic (vector cosine). Configure a real embedder in `starling.json`; the
  stub fallback returns rows but not by relevance.

- **Capture → search has a tick delay.** A captured statement is searchable only
  after the dashboard's background tick **embeds + consolidates** it
  (`tick_interval_s`). For tests set `STARLING_DASH_TICK_INTERVAL=5` or
  `POST /api/tick` before searching. The plugin's `sync()` (used by the `memory`
  reindex CLI) calls `/api/tick`; `memory_search` itself does not force a tick.

- **`perspective` is case-tolerant now.** `holder_perspective` is stored
  lowercase; `/api/recall` lowercases the query perspective, so `"FIRST_PERSON"`
  and `"first_person"` both match. (Fixed alongside the holder bug.)

- **Don't set `OPENCLAW_HOME`.** OpenClaw 2026.6.6 reads its config from
  `OPENCLAW_CONFIG_PATH` (an explicit file). Setting `OPENCLAW_HOME` makes it
  append `/.openclaw`, silently relocating the config to
  `…/.openclaw/.openclaw/openclaw.json` so the plugin is never discovered. The
  container already sets `OPENCLAW_CONFIG_PATH` correctly.

- **macOS `_core.so` can't run in a Linux container** — that's why the dashboard
  is host-side. Don't try to containerize it on macOS.

---

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `memory_search` / `/api/recall` empty for data you just stored | (1) recalling under a different `holder` than capture — pass `holder=<STARLING_HOLDER>`. (2) no tick yet — wait for `tick_interval_s` or `POST /api/tick`. (3) no embedder configured — set one in `starling.json`. |
| `plugins inspect starling` → "Config path not found" | `OPENCLAW_HOME` is set somewhere; unset it. Config must be at `OPENCLAW_CONFIG_PATH`. |
| Container can't reach the dashboard (connection refused) | Dashboard bound to `127.0.0.1`, not `0.0.0.0`; restart with `STARLING_DASH_HOST=0.0.0.0`. Check `STARLING_PORT` matches the dashboard port. |
| `401`/`StarlingAuthError` in plugin logs | `STARLING_TOKEN` wrong/stale; re-export from `~/.starling/starling.json` (Step 2). |
| `POST /api/remember` returns `statement_ids: []` | Extractor (LLM) found no clear subject/predicate/object in the text. Relational facts ("Bob's favorite DB is Postgres") extract reliably; bare reminders may not. |
| `openclaw plugins doctor` warns "must declare contracts.tools" | Non-fatal under 2026.6.6; the slot + runtime still load. Optional: add `"contracts": {"tools": ["memory_store","memory_forget"]}` to `openclaw.plugin.json` for the two write tools to register without the warning. |

---

## Using it in a real OpenClaw install (without docker)

The docker path is for isolated testing. To wire the plugin into a real
OpenClaw on the same host as the dashboard:

1. Build the plugin: `cd integrations/openclaw && npm install && npm run build`
   (produces `dist/index.js`).
2. Point OpenClaw at it. In your OpenClaw config (`OPENCLAW_CONFIG_PATH`):
   ```json
   {
     "plugins": {
       "enabled": true,
       "load": { "paths": ["<repo>/integrations/openclaw"] },
       "slots": { "memory": "starling" },
       "entries": {
         "starling": {
           "config": {
             "dashboardUrl": "http://127.0.0.1:8787",
             "token": "<token from ~/.starling/starling.json>",
             "tenant": "openclaw",
             "holder": "agent",
             "autoCapture": true,
             "autoRecall": true
           }
         }
       }
     }
   }
   ```
   (Or `openclaw plugins install <repo>/integrations/openclaw`.)
3. Start the dashboard (Step 1, but you can bind `127.0.0.1` since OpenClaw is on
   the same host). The agent now has `memory_search` / `memory_get` /
   `memory_store` / `memory_forget`, and auto-recall/auto-capture per the flags.

---

## Development

```bash
cd integrations/openclaw
npm install
npm test            # vitest — map/client/runtime/config units (86 tests)
npm run typecheck   # tsc --noEmit
npm run build       # tsc → dist/
```

Source layout: `src/config.ts` (config parse) · `src/map.ts` (pure
capability↔dashboard mapping + `statement://` path codec) · `src/client.ts`
(HTTP transport, read-degrade, write retry-queue) · `src/runtime.ts`
(`MemoryPluginRuntime` / `MemorySearchManager`) · `src/index.ts`
(`definePluginEntry` + all `register*` wiring).

## Reference

- [`docker/README.md`](docker/README.md) — docker internals, the integration
  test script, and per-file notes.
- Design: `docs/superpowers/specs/2026-06-15-p3-b2-openclaw-memory-plugin-design.md`
- Contract (OpenClaw plugin-sdk surface): `docs/superpowers/specs/2026-06-15-p3-b2-openclaw-contract.md`
