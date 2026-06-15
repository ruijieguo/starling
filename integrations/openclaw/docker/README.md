# OpenClaw + Starling memory plugin — Docker integration environment

Run OpenClaw in an isolated container with the Starling memory plugin installed,
talking to a Starling dashboard running on your **host**.

## Topology (and why)

```
┌─ macOS host ───────────────────────────────┐        ┌─ docker container ─────────────┐
│ Starling dashboard (FastAPI + uvicorn)      │  HTTP  │ OpenClaw 2026.6.6              │
│   loads native _core.so (Mach-O, arm64)     │◀───────│   + @starling/openclaw-memory  │
│   bind 0.0.0.0:8787  (token-auth)           │ host.  │   plugins.slots.memory=starling│
│   ~/.starling/{starling.json, dashboard.db} │ docker.│   reaches host via             │
│                                             │internal│   host.docker.internal:<port>  │
└─────────────────────────────────────────────┘        └────────────────────────────────┘
```

**The dashboard runs on the host, not in a container, on purpose.** Starling's
engine is a native `_core.so` compiled as a **macOS Mach-O (arm64)** binary. It
**cannot be loaded inside a Linux container.** So:

- **Starling dashboard → host** (your existing venv + already-compiled `_core.so`).
- **OpenClaw → container** (isolated; does not touch your real `~/.openclaw`
  install or the system OpenClaw at `/opt/homebrew/lib/node_modules/openclaw`).
- The plugin reaches the host dashboard over `host.docker.internal:<port>`.

The compose file therefore defines **only** the `openclaw` service.

## Secrets

The dashboard bearer **token is never written into the image or this repo.** It
is read from your host environment at run time and templated into the
container's `~/.openclaw/openclaw.json` by `entrypoint.sh` (inside the running
container's ephemeral filesystem only). `STARLING_TOKEN` is intentionally absent
from the Dockerfile `ENV`; both `entrypoint.sh` and compose fail fast if it is
unset.

---

## 1. Start the Starling dashboard on the host

The dashboard launcher is `scripts/run_dashboard.py` (uvicorn). For the container
to reach it, bind to `0.0.0.0` (the default `127.0.0.1` is not reachable from the
container). The bearer token lives in `~/.starling/starling.json`.

From the repo root (`/Users/jaredguo-mini/develop/memory/starling`):

```bash
# Bind to all interfaces so host.docker.internal resolves to the dashboard.
STARLING_DASH_HOST=0.0.0.0 \
  .venv/bin/python scripts/run_dashboard.py --no-build
# → "Dashboard ready → http://127.0.0.1:8787/#token=<token>"
```

Notes:
- `--no-build` skips the SvelteKit frontend build (the integration test only
  needs the JSON API).
- The dashboard reads `llm` + `embedder` (and the `token`) from
  `~/.starling/starling.json`. With an embedder configured (the repo's config
  uses dashscope `text-embedding-v4`, dim 1024), captured statements get
  embedded by the background tick (`tick_interval_s`, default 30s).
- To avoid touching your normal dashboard DB, point at a throwaway DB and a
  spare port:
  ```bash
  STARLING_DASH_HOST=0.0.0.0 STARLING_DASH_PORT=8799 \
    STARLING_DASH_DB=/tmp/starling-e2e.db STARLING_DASH_TENANT=openclaw \
    STARLING_DASH_TICK_INTERVAL=5 \
    .venv/bin/python scripts/run_dashboard.py --no-build
  ```

### Get the token

```bash
export STARLING_TOKEN=$(python3 -c \
  "import json,os;print(json.load(open(os.path.expanduser('~/.starling/starling.json')))['token'])")
```

---

## 2. Bring up OpenClaw + the plugin

```bash
cd integrations/openclaw
STARLING_TOKEN=$STARLING_TOKEN docker compose -f docker/docker-compose.yml up --build
# default STARLING_PORT=8787; override if the dashboard is on another port:
#   STARLING_TOKEN=$STARLING_TOKEN STARLING_PORT=8799 docker compose -f docker/docker-compose.yml up --build
```

Environment passed through to the container (all overridable; only `STARLING_TOKEN`
is required):

| Var                      | Default                                   | Purpose                              |
| ------------------------ | ----------------------------------------- | ------------------------------------ |
| `STARLING_TOKEN`         | — (required)                              | Dashboard bearer token (host env)    |
| `STARLING_PORT`          | `8787`                                     | Host dashboard port                  |
| `STARLING_TENANT`        | `openclaw`                                 | Tenant for synthetic `statement://`  |
| `STARLING_HOLDER`        | `agent`                                    | Holder identity sent to `/api/remember` |
| `STARLING_AUTO_RECALL`   | `true`                                     | `before_agent_start` context inject  |
| `STARLING_AUTO_CAPTURE`  | `true`                                     | `before_compaction` transcript capture |

The container stays up (`sleep infinity`) so you can drive it with
`docker compose exec`.

### How the plugin is installed (mechanism)

OpenClaw discovers third-party plugins three ways (`docs/plugins/` + `docs/tools/plugin.md`):
`openclaw plugins install <pkg|path>` (ClawHub→npm, or a local dir/tarball), the
workspace/global `extensions/` dirs, or **`plugins.load.paths`** in the config.

This image uses **`plugins.load.paths`**: the Dockerfile builds the plugin to
`/opt/starling-plugin` (manifest `openclaw.plugin.json` at the dir root, entry at
`dist/index.js` via `package.json` → `openclaw.extensions`), and `entrypoint.sh`
writes a config pointing `plugins.load.paths` at it, selecting the slot with
`plugins.slots.memory = "starling"` and supplying `plugins.entries.starling.config`
(`dashboardUrl`, `token`, `tenant`, …).

**Config resolution gotcha:** OpenClaw 2026.6.6 resolves its config from
**`OPENCLAW_CONFIG_PATH`** (an explicit file). The container sets it to
`/root/.openclaw/openclaw.json`. Do **not** set `OPENCLAW_HOME` — OpenClaw treats
it as its own base dir and appends `/.openclaw`, silently relocating the config
to `…/.openclaw/.openclaw/openclaw.json` (the config then appears empty:
`openclaw config get plugins.slots.memory` → "Config path not found"). Verify
discovery with `openclaw plugins inspect starling` (should show `Status: loaded`).

---

## 3. Integration test

```bash
cd integrations/openclaw
STARLING_TOKEN=$STARLING_TOKEN STARLING_PORT=8799 ./docker/integration-test.sh
```

What it does (all assertions against the **host** dashboard):

0. Precondition: host dashboard reachable at `http://127.0.0.1:$STARLING_PORT`.
1. `docker compose up` (builds the image once if missing; `BUILD=1` forces a
   rebuild). Prints the redacted entrypoint config.
2. `openclaw plugins inspect starling` → plugin **discovered + loaded**.
3. Round-trip via `roundtrip.mjs` (runs **inside** the container, importing the
   compiled `dist/*.js` — the exact code OpenClaw loads): `status` → `remember`
   → `sync/tick` → `recall`. Asserts the host statement count **increased**
   (`/api/overview` → `counts.statements`).
4. Downgrade (`downgrade.mjs`): point the client at an unreachable URL → reads
   degrade (`recall` → `[]`, `working_set` → `null`, **no throw**), `remember`
   **enqueues** (queue length grows); then restore the URL and `flushQueue()`
   drains it.

The test tears the container down (`compose down -v`) on exit.

### Driving a single memory operation by hand

```bash
cd integrations/openclaw
docker compose -f docker/docker-compose.yml exec openclaw \
  node /opt/starling-plugin/roundtrip.mjs
# inspect what landed:
curl -s "http://127.0.0.1:8799/api/statements?limit=20" \
  -H "Authorization: Bearer $STARLING_TOKEN" | python3 -m json.tool
```

---

## 4. Observed behavior (self-audit) — read before relying on recall

These were verified during the end-to-end run; some are **Starling-side**
characteristics, not plugin/docker defects.

1. **Write path works end-to-end.** `remember` from inside the container creates
   real statements on the host dashboard across the `host.docker.internal`
   boundary (statement count `0 → 1`, with vectors in `statement_vectors`). The
   plugin's HTTP transport, the slot wiring, and the topology are sound.

2. **`/api/recall` and `/api/working_set` returned empty for freshly-remembered
   data** — even for a near-verbatim query against a statement that exists and is
   embedded (e.g. `team standup located_at room Ada` queried as "team standup
   room Ada"), and reproducible **host-side without docker** (direct
   `DashboardEngine.recall(...)`). So semantic recall through the plugin will
   often surface nothing on just-captured memories. This is a Starling retrieval
   behavior (query-embedding / scope / threshold in `_core.recall`), to be
   chased on the Starling side; it is **out of scope for this integration
   environment**. The plugin already degrades to `[]`/`null` rather than failing,
   so empty recall never interrupts an agent turn.

3. **Auto-recall (`before_agent_start`)** uses `working_set(interlocutor=cfg.holder)`.
   Because `working_set` returned empty in (2) (and the `remember` path does not
   populate `cognizers`/presence — `overview.counts.cognizers` stayed 0), the
   injected context is currently empty/weak. Wiring is correct; the content is
   gated by the same retrieval behavior as (2).

4. **Capture → search timing.** Statements are embedded by the dashboard's
   **background tick** (`tick_interval_s`). For a deterministic test, either set
   a short interval (`STARLING_DASH_TICK_INTERVAL=5`) or `POST /api/tick` before
   searching. `roundtrip.mjs` calls `sync()` (→ `/api/tick`) and waits ~3s.

5. **Extraction is non-deterministic and input-sensitive.** `POST /api/remember`
   returns `200 {outcome:"accepted", statement_ids:[…]}` but `statement_ids` can
   be **empty** when the LLM extractor finds no clear subject/predicate/object
   (e.g. a bare "standup at 9:30" reminder). Interlocutor-attributed, relational
   facts ("Bob's favorite database is Postgres") extract reliably. The plugin's
   `remember(text, holder)` does **not** send an `interlocutor`; consider whether
   capture should pass one.

6. **`autoCapture` (`before_compaction`)** persists the session transcript tail.
   Whether it is signal or noise depends on the conversation; left on by default.

7. **Plugin doctor warnings under 2026.6.6 (follow-up for the plugin, not docker).**
   `openclaw plugins doctor` reports:
   `starling: plugin must declare contracts.tools before registering agent tools`
   (×2, for `memory_store` + `memory_forget`). Under 2026.6.6, registering agent
   tools requires the manifest to declare `contracts.tools`. Add to
   `openclaw.plugin.json`:
   ```json
   "contracts": { "tools": ["memory_store", "memory_forget"] }
   ```
   The plugin still **loads and occupies the memory slot** without it (the
   warnings are non-fatal), and the `registerMemoryRuntime` search/get path is
   unaffected — but the two write tools will not register cleanly until this is
   added. There are also info/warn notes about the legacy `before_agent_start`
   hook and "hook-only / non-capability" mode; both are supported compatibility
   paths.

---

## Files

| File                  | Purpose                                                              |
| --------------------- | ------------------------------------------------------------------- |
| `openclaw.Dockerfile` | node:22-slim + `openclaw@2026.6.6` (pinned) + builds the plugin      |
| `entrypoint.sh`       | Renders `openclaw.json` from env at runtime (token never baked in)  |
| `docker-compose.yml`  | The single `openclaw` service; passes env through; `host.docker.internal` |
| `.dockerignore`       | Keeps host `dist/`, `node_modules/`, and secrets out of the build context |
| `integration-test.sh` | Orchestrates the end-to-end test from the host                      |
| `roundtrip.mjs`       | In-container write/recall round-trip against the host dashboard      |
| `downgrade.mjs`       | In-container degradation + retry-queue-flush check                  |
